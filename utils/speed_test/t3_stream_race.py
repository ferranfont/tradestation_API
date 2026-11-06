"""
Test 3 - CARRERA DE STREAMING: que broker entrega antes el mismo tick del SPX.

Se suscribe a la vez al SPX en TradeStation (stream de quotes) y en IB
(reqMktData; IB no ofrece tick-by-tick para el indice SPX: error 10189).
Cada vez que cambia el Last se guarda (hora de llegada en ns, valor). Despues se
emparejan los mismos valores entre ambos feeds (dentro de una ventana de tiempo)
y se calcula:

    delta = llegada_IB - llegada_TS
    delta > 0  -> TradeStation llego antes
    delta < 0  -> IB llego antes

Mismo proceso y mismo reloj (perf_counter_ns): no hace falta sincronizar con NTP.
Ejecutar con el mercado abierto (9:30-16:00 ET): fuera de horario el SPX no cambia.

Uso:  python utils/speed_test/t3_stream_race.py [--duration 300]
"""

import argparse
import asyncio
import math
from collections import defaultdict

import numpy as np

import ib_feed
from common import TS_SYMBOL, ms, now_ns, print_stats, save_csv
from ts_feed import TSClient

WARMUP_S = 5          # se descartan los primeros segundos (snapshot inicial)
MATCH_WINDOW_MS = 3000


def match(ts_ev, ib_ev, window_ms=MATCH_WINDOW_MS):
    """Empareja cada cambio de TS con el cambio de IB del mismo valor mas cercano en el tiempo."""
    by_value = defaultdict(list)
    for j, (t, v) in enumerate(ib_ev):
        by_value[v].append(j)
    used = set()
    pairs = []
    for t_ts, v in ts_ev:
        best, best_d = None, None
        for j in by_value.get(v, []):
            if j in used:
                continue
            d = ib_ev[j][0] - t_ts
            if abs(d) <= window_ms * 1e6 and (best is None or abs(d) < abs(best_d)):
                best, best_d = j, d
        if best is not None:
            used.add(best)
            pairs.append((t_ts, ib_ev[best][0], v, ms(best_d)))
    return pairs


async def main(duration: int):
    ts = TSClient()
    ib = await ib_feed.connect()
    contract = await ib_feed.spx_contract(ib)

    t_start = now_ns()
    ts_ev, ib_ev = [], []          # (t_ns, valor) solo cuando cambia el Last
    msgs = {"TS": 0, "IB": 0}      # mensajes totales recibidos
    last = {"TS": None, "IB": None}

    def record(src, t, value, events):
        msgs[src] += 1
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return
        value = round(float(value), 2)
        if value != last[src]:
            last[src] = value
            if t - t_start > WARMUP_S * 1e9:
                events.append((t, value))

    # --- TradeStation ---
    def on_ts(t, msg):
        if "Last" in msg:
            record("TS", t, msg["Last"], ts_ev)
        elif "Error" in msg:
            print(f"\nTS error: {msg}")

    # --- IB ---
    ticker = ib.reqMktData(contract, "", snapshot=False)

    def on_ib(tk):
        record("IB", now_ns(), tk.last, ib_ev)
    ticker.updateEvent += on_ib

    ts_task = asyncio.create_task(ts.stream_quotes(TS_SYMBOL, on_ts))
    print(f"Carrera durante {duration} s...")
    for s in range(duration):
        await asyncio.sleep(1)
        if ts_task.done():
            ts_task.result()  # propaga el error del stream de TS
        print(f"\r{s + 1}/{duration} s | cambios TS {len(ts_ev)}  IB {len(ib_ev)} | "
              f"last TS {last['TS']}  IB {last['IB']}", end="", flush=True)
    print()

    ts_task.cancel()
    ticker.updateEvent -= on_ib
    ib.cancelMktData(contract)
    ib.disconnect()
    await ts.close()

    # --- Resultados ---
    pairs = match(ts_ev, ib_ev)
    deltas = [p[3] for p in pairs]
    secs = duration - WARMUP_S
    print(f"\nMensajes recibidos: TS {msgs['TS']}  IB {msgs['IB']}")
    print(f"Cambios de precio: TS {len(ts_ev)} ({len(ts_ev) / secs:.2f}/s)  "
          f"IB {len(ib_ev)} ({len(ib_ev) / secs:.2f}/s)")
    print(f"Emparejados: {len(pairs)}  ({100 * len(pairs) / max(len(ts_ev), 1):.0f}% de TS, "
          f"{100 * len(pairs) / max(len(ib_ev), 1):.0f}% de IB)")

    if deltas:
        d = np.asarray(deltas)
        print_stats("Delta llegada IB - TS (positivo = TS antes)", {"delta": deltas})
        print(f"TS llega antes: {100 * (d > 0).mean():.1f}%   IB llega antes: {100 * (d < 0).mean():.1f}%   "
              f"mediana de ventaja: {np.median(d):+.1f} ms")

    def gaps(ev):
        return [ms(b[0] - a[0]) for a, b in zip(ev, ev[1:])]
    print_stats("Tiempo entre cambios de precio", {"TS": gaps(ts_ev), "IB": gaps(ib_ev)})

    save_csv("t3_race_pairs", [{"t_ts_ms": round(ms(a - t_start), 3), "t_ib_ms": round(ms(b - t_start), 3),
                                "value": v, "delta_ms": round(dl, 3)} for a, b, v, dl in pairs])
    save_csv("t3_race_events", [{"src": "TS", "t_ms": round(ms(t - t_start), 3), "value": v} for t, v in ts_ev]
             + [{"src": "IB", "t_ms": round(ms(t - t_start), 3), "value": v} for t, v in ib_ev])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=300, help="segundos de carrera")
    a = ap.parse_args()
    asyncio.run(main(a.duration))
