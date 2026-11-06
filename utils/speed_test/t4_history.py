"""
Test 4 - Descarga de historicos del SPX: tiempo total y barras/segundo.

Mismas peticiones en ambos brokers, alternadas, repetidas --reps veces:
  - 1 minuto: 1 dia, 5 dias, 1 mes
  - diario:   10 anos

Uso:  python utils/speed_test/t4_history.py [--reps 3]
"""

import argparse
import asyncio
import statistics
from datetime import datetime, timedelta, timezone

import ib_feed
from common import TS_SYMBOL, ms, now_ns, save_csv
from ts_feed import TSClient

CASES = [
    # nombre,      params TS (relativos),                IB duration, IB barSize
    ("1min x 1D",  dict(unit="Minute", days=1),           "1 D",  "1 min"),
    ("1min x 5D",  dict(unit="Minute", days=7),           "5 D",  "1 min"),
    ("1min x 1M",  dict(unit="Minute", days=31),          "1 M",  "1 min"),
    ("1day x 10Y", dict(unit="Daily",  days=3653),        "10 Y", "1 day"),
]


async def ts_case(ts: TSClient, p: dict):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=p["days"])
    return await ts.bars(TS_SYMBOL, unit=p["unit"], interval=1,
                         firstdate=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         lastdate=end.strftime("%Y-%m-%dT%H:%M:%SZ"))


async def ib_case(ib, contract, duration: str, bar: str):
    t0 = now_ns()
    bars = await ib.reqHistoricalDataAsync(contract, endDateTime="", durationStr=duration,
                                           barSizeSetting=bar, whatToShow="TRADES",
                                           useRTH=True, formatDate=2, timeout=120)
    return bars, now_ns() - t0


async def main(reps: int):
    ts = TSClient()
    ib = await ib_feed.connect()
    contract = await ib_feed.spx_contract(ib)

    rows = []
    for name, ts_p, ib_dur, ib_bar in CASES:
        for r in range(reps):
            bars, t = await ts_case(ts, ts_p)
            rows.append({"case": name, "rep": r, "broker": "TS", "bars": len(bars), "ms": round(ms(t), 1)})
            print(f"{name:<11} rep {r}  TS {len(bars):>6} barras  {ms(t):>8.1f} ms")

            bars, t = await ib_case(ib, contract, ib_dur, ib_bar)
            rows.append({"case": name, "rep": r, "broker": "IB", "bars": len(bars), "ms": round(ms(t), 1)})
            print(f"{name:<11} rep {r}  IB {len(bars):>6} barras  {ms(t):>8.1f} ms")
            await asyncio.sleep(2)

    print(f"\n=== Resumen (mediana de {reps} repeticiones) ===")
    print(f"{'caso':<12}{'TS barras':>10}{'TS ms':>10}{'TS bar/s':>11}"
          f"{'IB barras':>11}{'IB ms':>10}{'IB bar/s':>11}")
    for name, *_ in CASES:
        line = f"{name:<12}"
        for b in ("TS", "IB"):
            rs = sorted((x for x in rows if x["case"] == name and x["broker"] == b), key=lambda x: x["ms"])
            med = rs[len(rs) // 2]
            bps = med["bars"] / (med["ms"] / 1000) if med["ms"] else 0
            line += f"{med['bars']:>10}{med['ms']:>10.0f}{bps:>11.0f}" if b == "TS" else \
                    f"{med['bars']:>11}{med['ms']:>10.0f}{bps:>11.0f}"
        print(line)
    save_csv("t4_history", rows)

    ib.disconnect()
    await ts.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    asyncio.run(main(ap.parse_args().reps))
