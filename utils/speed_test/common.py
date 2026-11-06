"""
Utilidades comunes del speed test: reloj, estadisticas, CSV y configuracion.

Todas las medidas usan time.perf_counter_ns(): reloj monotonico de alta
resolucion del propio PC. Como TradeStation e IB se miden en el mismo proceso
con el mismo reloj, las diferencias entre ambos son comparables al milisegundo
sin necesidad de sincronizar relojes con NTP.
"""

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # .../tradestation_API
UTILS = ROOT / "utils"
RESULTS = Path(__file__).resolve().parent / "results"

if str(UTILS) not in sys.path:
    sys.path.insert(0, str(UTILS))

load_dotenv(ROOT / ".env")

now_ns = time.perf_counter_ns

# --- Simbolo SPX en cada broker ---------------------------------------------
TS_SYMBOL = "$SPX.X"
IB_SYMBOL, IB_EXCHANGE, IB_CURRENCY = "SPX", "CBOE", "USD"

# --- Conexion IB (lee el .env) ----------------------------------------------
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7497"))
# clientId propio para no expulsar al collector ni al visor (43 / 143)
IB_CLIENT_ID = int(os.getenv("IB_SPEEDTEST_CLIENT_ID",
                             int(os.getenv("IB_CLIENT_ID", "1")) + 200))


def ms(ns: int | float) -> float:
    return ns / 1e6


def stats(values_ms) -> dict:
    a = np.asarray([v for v in values_ms if v is not None], dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "min": a.min(),
        "p50": np.percentile(a, 50),
        "p90": np.percentile(a, 90),
        "p99": np.percentile(a, 99),
        "max": a.max(),
        "mean": a.mean(),
        "std": a.std(),
    }


def print_stats(title: str, series: dict[str, list[float]], unit: str = "ms"):
    """Imprime una tabla comparativa: una fila por serie (p. ej. TS / IB)."""
    cols = ["n", "min", "p50", "p90", "p99", "max", "mean", "std"]
    w = max([22] + [len(k) + 2 for k in series])
    print(f"\n=== {title} ({unit}) ===")
    print(f"{'':<{w}}" + "".join(f"{c:>10}" for c in cols))
    for label, values in series.items():
        s = stats(values)
        row = f"{label:<{w}}"
        for c in cols:
            v = s.get(c)
            row += f"{'-':>10}" if v is None else (f"{v:>10d}" if c == "n" else f"{v:>10.2f}")
        print(row)


def save_csv(name: str, rows: list[dict]) -> Path | None:
    if not rows:
        return None
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"CSV: {path}")
    return path
