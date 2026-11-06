"""
Test 2 - Cotizacion bajo demanda (request/response) del SPX.

Alterna peticiones TS / IB para que ambos se midan en las mismas condiciones.
- TS: GET /v3/marketdata/quotes/$SPX.X sobre conexion keep-alive.
      Se separa tiempo de red y tiempo de parseo JSON.
- IB: reqMktData(snapshot=True) -> tiempo hasta recibir el primer precio valido.
- IB: reqCurrentTime -> ida y vuelta app <-> TWS.

OJO al interpretar: los tiempos de IB (0.3-2 ms) los responde TWS desde tu PC, sin
ir a los servidores de IB (estan a ~100 ms, ver t1_network). No son comparables
con la peticion de TS, que si llega a su servidor por HTTPS. Miden el coste local
de pedirle a TWS un dato que ya tiene. Para comparar frescura real usa t3_stream_race.

reqCurrentTime a veces no responde nunca: lleva timeout y se cuentan los fallos.

Rate limit TS: 500 quotes / 5 min -> por defecto 1 peticion cada 0.7 s.

Uso:  python utils/speed_test/t2_snapshot.py [--n 100] [--pause 0.7]
"""

import argparse
import asyncio
import math

import ib_feed
from common import TS_SYMBOL, ms, now_ns, print_stats, save_csv
from ts_feed import TSClient


async def ib_snapshot_ns(ib, contract, timeout=5.0) -> int | None:
    done = asyncio.Event()
    t0 = now_ns()
    t_first = None

    def on_update(tk):
        nonlocal t_first
        price = tk.last if not math.isnan(tk.last) else tk.close
        if t_first is None and price and not math.isnan(price):
            t_first = now_ns()
            done.set()

    ticker = ib.reqMktData(contract, "", snapshot=True)
    ticker.updateEvent += on_update
    try:
        await asyncio.wait_for(done.wait(), timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        ticker.updateEvent -= on_update
    return None if t_first is None else t_first - t0


async def ib_current_time_ms(ib, timeout=2.0) -> float | None:
    t0 = now_ns()
    try:
        await asyncio.wait_for(ib.reqCurrentTimeAsync(), timeout)
    except asyncio.TimeoutError:
        return None
    return ms(now_ns() - t0)


async def main(n: int, pause: float):
    ts = TSClient()
    ib = await ib_feed.connect()
    contract = await ib_feed.spx_contract(ib)

    # Calentamiento (DNS, TLS, primera respuesta) - no se mide
    await ts.quote(TS_SYMBOL)
    await ib_snapshot_ns(ib, contract)
    await ib_current_time_ms(ib)

    rows = []
    ts_net, ts_parse, ib_snap, ib_rtt = [], [], [], []
    for i in range(n):
        _, net, parse = await ts.quote(TS_SYMBOL)
        ts_net.append(ms(net)); ts_parse.append(ms(parse))

        snap = await ib_snapshot_ns(ib, contract)
        ib_snap.append(ms(snap) if snap else None)

        ib_rtt.append(await ib_current_time_ms(ib))

        rows.append({"sample": i, "ts_net_ms": round(ts_net[-1], 3),
                     "ts_parse_ms": round(ts_parse[-1], 3),
                     "ib_snapshot_ms": round(ib_snap[-1], 3) if ib_snap[-1] else "",
                     "ib_currenttime_ms": round(ib_rtt[-1], 3) if ib_rtt[-1] else ""})
        print(f"\r{i + 1}/{n}  TS {ts_net[-1]:7.1f} ms | IB snapshot "
              f"{(ib_snap[-1] or float('nan')):7.1f} ms | IB rtt {(ib_rtt[-1] or float('nan')):6.1f} ms",
              end="", flush=True)
        await asyncio.sleep(pause)
    print()

    print_stats("Snapshot SPX: peticion -> respuesta", {
        "TS quote (servidor)": ts_net,
        "TS parseo JSON": ts_parse,
        "IB snapshot (TWS local)": ib_snap,
        "IB currentTime (TWS local)": ib_rtt,
    })
    for label, vals in (("snapshots sin precio", ib_snap), ("reqCurrentTime sin respuesta", ib_rtt)):
        fails = sum(v is None for v in vals)
        if fails:
            print(f"IB: {fails}/{len(vals)} {label}")
    save_csv("t2_snapshot", rows)

    ib.disconnect()
    await ts.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--pause", type=float, default=0.7)
    a = ap.parse_args()
    asyncio.run(main(a.n, a.pause))
