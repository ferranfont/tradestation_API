"""
Lanza una orden limitada (o cancela una existente). Por defecto en la cuenta SIM.

Por defecto compra 1 SPY un 10% por debajo del bid, valida solo hoy (DAY): queda
abierta sin ejecutarse. Pide validacion (orderconfirm) antes de enviarla y luego
lee el estado real de la orden en la cuenta.

Siempre DAY: si no se ejecuta, TradeStation la cancela al final del dia. Nunca GTC.
Fuera de horario (despues de las 16:00 ET) TradeStation rechaza las DAY: lanzala con el mercado abierto.

Uso:
    python sim/lanzar_orden.py                                # 1 SPY, -10%
    python sim/lanzar_orden.py --symbol AAPL --qty 2 --pct 5  # 2 AAPL, -5%
    python sim/lanzar_orden.py --cancel 123456789             # cancelar por OrderID

REAL (dinero real): hay que pedirlo y repetir el numero de cuenta:
    python sim/lanzar_orden.py --real --confirmo 12083744
    python sim/lanzar_orden.py --real --confirmo 12083744 --cancel 123456789
"""

import argparse
import sys
import time

from ts_broker import Broker, args_modo, broker_desde_args

FINALES = {"FLL", "CAN", "REJ", "EXP", "OUT", "BRO"}   # estados en los que no hace falta esperar mas


def ver_orden(sim: Broker, order_id: str, intentos: int = 5) -> dict | None:
    orden = None
    for _ in range(intentos):
        orden = next((o for o in sim.orders() if o.get("OrderID") == order_id), None)
        if orden and orden.get("Status") in FINALES:
            return orden
        time.sleep(1)
    return orden


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--side", default="BUY", choices=["BUY", "SELL"])
    ap.add_argument("--pct", type=float, default=10.0, help="%% de distancia al bid (BUY) o al ask (SELL)")
    ap.add_argument("--cancel", metavar="ORDER_ID", help="cancela esta orden y sale")
    args_modo(ap, operar=True)
    a = ap.parse_args()
    sim = broker_desde_args(a, operar=True)

    if a.cancel:
        r = sim.cancel(a.cancel)
        print(f"Cancelar {a.cancel}: HTTP {r.status_code} {r.text[:300]}")
        orden = ver_orden(sim, a.cancel)
        print(f"Estado: {orden.get('Status')} - {orden.get('StatusDescription')}" if orden else "Orden no encontrada")
        sys.exit(0 if r.ok else 1)

    q = sim.quote(a.symbol)
    if a.side == "BUY":
        precio = float(q["Bid"]) * (1 - a.pct / 100)
    else:
        precio = float(q["Ask"]) * (1 + a.pct / 100)
    orden = sim.limit_order(a.symbol, a.side, a.qty, precio)
    print(f"[{sim.etiqueta}] {sim.account}: {a.side} {a.qty} {a.symbol} limite {orden['LimitPrice']} "
          f"(Bid {q['Bid']} / Ask {q['Ask']}, DAY)")

    r = sim.confirm(orden)
    if not r.ok:
        sys.exit(f"Validacion rechazada: HTTP {r.status_code} {r.text}")
    c = r.json()["Confirmations"][0]
    print(f"Validada: coste estimado {c.get('EstimatedCost')}  comision {c.get('EstimatedCommission')}")

    r = sim.place(orden)
    datos = r.json() if r.content else {}
    if not r.ok or datos.get("Errors") or not datos.get("Orders"):
        sys.exit(f"Orden rechazada: HTTP {r.status_code} {r.text}")
    enviada = datos["Orders"][0]
    print(f"Respuesta: OrderID {enviada['OrderID']} - {enviada.get('Message')}")

    o = ver_orden(sim, enviada["OrderID"])
    if o is None:
        sys.exit("La orden se envio pero no aparece todavia en la cuenta")
    print(f"Estado en la cuenta: {o.get('Status')} - {o.get('StatusDescription')}")
    if o.get("Status") == "REJ":
        sys.exit("ORDEN RECHAZADA por TradeStation")
    if o.get("Status") not in FINALES:
        print(f"Para cancelarla:  python sim/lanzar_orden.py --cancel {enviada['OrderID']}")


if __name__ == "__main__":
    main()
