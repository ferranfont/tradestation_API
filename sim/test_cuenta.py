"""
Estado de la cuenta SIM en tablas: saldo, posiciones y ordenes.

Uso:  python sim/test_cuenta.py
"""

from cuenta import foto
from ts_sim import Sim


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
    f = foto(Sim())
    print(f"Cuenta {f['cuenta']} ({f['tipo']})  |  {f['hora']}")
    c = f["cotizacion"]
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
