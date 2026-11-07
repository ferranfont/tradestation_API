"""
Estado de una cuenta en tablas: saldo, posiciones y ordenes. Solo lectura.

Uso:
    python sim/test_cuenta.py                       # SIM (cuenta del .env)
    python sim/test_cuenta.py --real                # REAL (cuenta del .env)
    python sim/test_cuenta.py --real --cuenta TSE01900
"""

import argparse
from datetime import datetime

from cuenta import cotizacion, foto
from ts_broker import args_modo, broker_desde_args


def tabla(titulo: str, filas: list[dict], columnas: list[tuple[str, str]]):
    print(f"\n=== {titulo} ===")
    if not filas:
        print("(ninguna)")
        return
    celdas = [[str(f.get(k) if f.get(k) is not None else "-") for k, _ in columnas] for f in filas]
    anchos = [max(len(n), *(len(c[i]) for c in celdas)) for i, (_, n) in enumerate(columnas)]
    print("  ".join(n.ljust(a) for (_, n), a in zip(columnas, anchos)))
    print("  ".join("-" * a for a in anchos))
    for c in celdas:
        print("  ".join(v.ljust(a) for v, a in zip(c, anchos)))


def main():
    ap = argparse.ArgumentParser()
    args_modo(ap)
    b = broker_desde_args(ap.parse_args())
    f = foto(b)
    print(f"Cuenta {f['cuenta']} ({f['tipo']})  |  {datetime.now():%Y-%m-%d %H:%M:%S}")
    c = cotizacion(b)
    print(f"{c['simbolo']}: Last {c['last']}  Bid {c['bid']}  Ask {c['ask']}  Retrasado {c['retrasado']}")

    tabla("Saldo", [{"campo": k, "valor": v} for k, v in f["saldo"].items()],
          [("campo", "Campo"), ("valor", "Valor")])
    tabla("Posiciones", f["posiciones"],
          [("simbolo", "Simbolo"), ("lado", "Lado"), ("cantidad", "Cant"), ("precio_medio", "Medio"),
           ("ultimo", "Ultimo"), ("valor", "Valor"), ("pnl", "P&L")])
    tabla("Ordenes", f["ordenes"],
          [("id", "OrderID"), ("simbolo", "Simbolo"), ("lado", "Lado"), ("cantidad", "Cant"), ("ejecutado", "Ejec"),
           ("tipo", "Tipo"), ("limite", "Limite"), ("vigencia", "Vigencia"), ("estado", "Estado"), ("motivo", "Motivo")])


if __name__ == "__main__":
    main()
