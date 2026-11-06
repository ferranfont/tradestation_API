"""
Comprueba si se puede operar cada tipo de activo en las cuentas SIM.

Por defecto solo valida (orderconfirm): no envia nada.
Con --enviar manda de verdad cada orden, lejos del mercado, y la cancela al momento.

Uso:
    python sim/test_activos.py             # solo validar
    python sim/test_activos.py --enviar    # enviar y cancelar
"""

import argparse
import sys
from datetime import date, timedelta

from lanzar_orden import ver_orden
from ts_sim import ACCOUNT, Sim

CUENTA_FUTUROS = "SIM3347849F"   # las cuentas Margin no operan futuros
FUTURO = "ESZ26"
SUBYACENTE_OPCION = "SPY"


def opcion_otm(sim: Sim) -> str:
    """Call de SPY un 5% fuera del dinero, con al menos una semana de vida."""
    r = sim.get(f"/marketdata/options/expirations/{SUBYACENTE_OPCION}")
    r.raise_for_status()
    minimo = date.today() + timedelta(days=7)
    fechas = sorted(date.fromisoformat(e["Date"][:10]) for e in r.json()["Expirations"])
    venc = next(f for f in fechas if f >= minimo)
    r = sim.get(f"/marketdata/options/strikes/{SUBYACENTE_OPCION}", expiration=venc.strftime("%m-%d-%Y"))
    r.raise_for_status()
    strikes = sorted(float(s[0]) for s in r.json()["Strikes"])
    objetivo = float(sim.quote(SUBYACENTE_OPCION)["Last"]) * 1.05
    strike = min(strikes, key=lambda k: abs(k - objetivo))
    return f"{SUBYACENTE_OPCION} {venc:%y%m%d}C{strike:g}"


def casos() -> list[tuple]:
    margen, futuros = Sim(), Sim(CUENTA_FUTUROS)
    spy = float(margen.quote("SPY")["Bid"])
    es = float(futuros.quote(FUTURO)["Last"])
    opcion = opcion_otm(margen)
    q = margen.quote(opcion)
    prima = max(round(float(q.get("Last") or 0) * 0.5, 2), 0.01)
    return [
        ("Acciones", margen, "SPY", "BUY", round(spy * 0.9, 2)),
        ("Opciones", margen, opcion, "BUYTOOPEN", prima),
        ("Futuros", futuros, FUTURO, "BUY", round(es * 0.9 * 4) / 4),   # tick de ES: 0.25
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enviar", action="store_true", help="enviar de verdad y cancelar")
    enviar = ap.parse_args().enviar
    print(f"Modo: {'ENVIAR Y CANCELAR' if enviar else 'solo validar'}\n")

    fallos = 0
    for nombre, sim, simbolo, accion, precio in casos():
        orden = sim.limit_order(simbolo, accion, 1, precio, "GTC")
        print(f"{nombre}: {sim.account} {accion} 1 {simbolo} limite {orden['LimitPrice']}")
        r = sim.confirm(orden)
        print(f"  validar: HTTP {r.status_code} {'' if r.ok else r.text[:300]}")
        if not r.ok:
            fallos += 1
            continue
        if not enviar:
            continue

        r = sim.place(orden)
        datos = r.json() if r.content else {}
        if not r.ok or not datos.get("Orders"):
            print(f"  enviar: FALLO HTTP {r.status_code} {r.text[:300]}")
            fallos += 1
            continue
        oid = datos["Orders"][0]["OrderID"]
        o = ver_orden(sim, oid) or {}
        print(f"  enviar: OrderID {oid} -> {o.get('Status')} {o.get('StatusDescription')} {o.get('RejectReason') or ''}")
        if o.get("Status") == "REJ":
            fallos += 1
            continue

        r = sim.cancel(oid)
        o = ver_orden(sim, oid) or {}
        print(f"  cancelar: HTTP {r.status_code} -> {o.get('Status')} {o.get('StatusDescription')}")
        if not r.ok or o.get("Status") not in ("CAN", "OUT"):
            fallos += 1

    print(f"\n{'TODO OK' if not fallos else f'{fallos} activo(s) con fallo'}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
