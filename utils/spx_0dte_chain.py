"""
Descarga la cadena de opciones 0DTE del SPX (vencimiento de hoy) desde TradeStation,
con precios, IV y griegas, la guarda en CSV y muestra en terminal los strikes
cercanos al dinero.

Requiere el scope OptionSpreads (ya incluido en SCOPES de test_conection.py).

Uso:
    python utils/spx_0dte_chain.py                  # vencimiento de hoy
    python utils/spx_0dte_chain.py 2026-11-06       # otro vencimiento (YYYY-MM-DD)
"""

import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_conection import API_BASE, get_access_token  # noqa: E402

UNDERLYING = "$SPX.X"      # precio del indice
OPTION_ROOT = "$SPXW.X"    # opciones SPXW (diarias/semanales); "$SPX.X" solo da las mensuales AM
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STREAM_TIMEOUT = 60      # segundos máximos esperando la foto inicial de la cadena
IDLE_TIMEOUT = 5         # segundos sin datos nuevos para dar la foto por completa
SHOW_STRIKES = 10        # strikes a cada lado del precio que se imprimen en terminal


def api_get(path, token, **params):
    r = requests.get(f"{API_BASE}{path}", headers={"Authorization": f"Bearer {token}"},
                     params=params, timeout=30)
    if not r.ok:
        sys.exit(f"Error {r.status_code} en {path}: {r.text}")
    return r.json()


def find_expiration(token, target: date) -> str:
    """Devuelve la fecha de vencimiento tal como la espera la API (MM-DD-YYYY)."""
    data = api_get(f"/marketdata/options/expirations/{OPTION_ROOT}", token)
    dates = [datetime.fromisoformat(e["Date"].replace("Z", "+00:00")).date()
             for e in data.get("Expirations", [])]
    if target not in dates:
        proximos = ", ".join(str(d) for d in sorted(dates)[:5])
        sys.exit(f"No hay vencimiento del SPX el {target}. Proximos: {proximos}")
    return target.strftime("%m-%d-%Y")


def get_strikes(token, expiration: str) -> list[float]:
    data = api_get(f"/marketdata/options/strikes/{OPTION_ROOT}", token, expiration=expiration)
    return sorted(float(s[0]) for s in data.get("Strikes", []))


def stream_chain(token, expiration: str, n_strikes: int) -> list[dict]:
    """Lee la foto inicial del stream de la cadena (todas las calls y puts)."""
    params = {
        "expiration": expiration,
        "strikeProximity": n_strikes,   # strikes a cada lado del precio -> cadena completa
        "optionType": "All",
        "spreadType": "Single",
        "enableGreeks": "true",
    }
    expected = n_strikes * 2            # calls + puts
    rows: dict[tuple, dict] = {}
    start = last_new = time.time()

    with requests.get(f"{API_BASE}/marketdata/stream/options/chains/{OPTION_ROOT}",
                      headers={"Authorization": f"Bearer {token}"}, params=params,
                      stream=True, timeout=(10, IDLE_TIMEOUT)) as r:
        if not r.ok:
            sys.exit(f"Error {r.status_code} en el stream de la cadena: {r.text}")
        try:
            for line in r.iter_lines():
                now = time.time()
                if line:
                    msg = json.loads(line)
                    if "Error" in msg:
                        sys.exit(f"Error del stream: {msg}")
                    if "Legs" in msg:
                        key = (msg["Legs"][0]["Symbol"],)
                        if key not in rows:
                            last_new = now
                        rows[key] = msg
                print(f"\rRecibidas {len(rows)}/{expected} opciones...", end="", flush=True)
                if len(rows) >= expected or now - start > STREAM_TIMEOUT \
                        or (rows and now - last_new > IDLE_TIMEOUT):
                    break
        except requests.exceptions.ConnectionError:
            pass  # read timeout: no llegan más datos nuevos
    print()
    return list(rows.values())


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    def f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    records = []
    for m in rows:
        leg = m["Legs"][0]
        records.append({
            "Symbol": leg["Symbol"],
            "Type": leg.get("OptionType", m.get("Side")),
            "Strike": f(leg.get("StrikePrice")),
            "Bid": f(m.get("Bid")),
            "Ask": f(m.get("Ask")),
            "Mid": f(m.get("Mid")),
            "Last": f(m.get("Last")),
            "IV": f(m.get("ImpliedVolatility")),
            "Delta": f(m.get("Delta")),
            "Gamma": f(m.get("Gamma")),
            "Theta": f(m.get("Theta")),
            "Vega": f(m.get("Vega")),
            "Rho": f(m.get("Rho")),
            "Intrinsic": f(m.get("IntrinsicValue")),
            "Extrinsic": f(m.get("ExtrinsicValue")),
            "ProbITM": f(m.get("ProbabilityITM")),
            "Volume": f(m.get("Volume")),
            "OpenInterest": f(m.get("DailyOpenInterest")),
            "BidSize": f(m.get("BidSize")),
            "AskSize": f(m.get("AskSize")),
        })
    return pd.DataFrame(records).sort_values(["Strike", "Type"]).reset_index(drop=True)


def print_near_money(df: pd.DataFrame, spot: float):
    calls = df[df["Type"].str.lower() == "call"].set_index("Strike")
    puts = df[df["Type"].str.lower() == "put"].set_index("Strike")
    strikes = sorted(set(calls.index) | set(puts.index), key=lambda k: abs(k - spot))
    strikes = sorted(strikes[: SHOW_STRIKES * 2])

    cols = ["Bid", "Ask", "IV", "Delta", "Gamma", "Theta"]
    header = " | ".join(f"{c:>7}" for c in cols)
    print(f"\n{'CALLS':^{len(header)}}   {'':^8}   {'PUTS':^{len(header)}}")
    print(f"{header}   {'STRIKE':^8}   {header}")

    def fmt(side, k):
        if k not in side.index:
            return " | ".join(f"{'':>7}" for _ in cols)
        r = side.loc[k]
        vals = [r["Bid"], r["Ask"], r["IV"], r["Delta"], r["Gamma"], r["Theta"]]
        out = []
        for c, v in zip(cols, vals):
            if v is None or pd.isna(v):
                out.append(f"{'-':>7}")
            elif c == "IV":
                out.append(f"{v * 100:>6.1f}%")
            elif c == "Gamma":
                out.append(f"{v:>7.4f}")
            else:
                out.append(f"{v:>7.2f}")
        return " | ".join(out)

    for k in strikes:
        marker = "<" if abs(k - spot) == min(abs(s - spot) for s in strikes) else " "
        print(f"{fmt(calls, k)}   {k:^8.0f}{marker}  {fmt(puts, k)}")


def main():
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()

    token = get_access_token()
    spot = float(api_get(f"/marketdata/quotes/{UNDERLYING}", token)["Quotes"][0]["Last"])
    expiration = find_expiration(token, target)
    strikes = get_strikes(token, expiration)
    print(f"SPX = {spot:.2f} | Vencimiento {target} | {len(strikes)} strikes "
          f"({strikes[0]:.0f} - {strikes[-1]:.0f})")

    rows = stream_chain(token, expiration, len(strikes))
    if not rows:
        sys.exit("No se recibieron datos de la cadena.")
    df = to_dataframe(rows)

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"spx_chain_{target:%Y%m%d}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    df.to_csv(out, index=False)

    print_near_money(df, spot)
    print(f"\n{len(df)} opciones guardadas en {out}")


if __name__ == "__main__":
    main()
