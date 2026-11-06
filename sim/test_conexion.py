"""
Test de conexion a la cuenta SIM: acceso, datos en tiempo real y permiso de ordenes.
NO envia ninguna orden: orderconfirm solo valida.

Uso:  python sim/test_conexion.py
"""

import sys

from ts_sim import ACCOUNT, SIM_BASE, Sim

SYMBOL = "SPY"
resultados = []


def check(nombre: str, ok: bool, detalle: str = ""):
    resultados.append(ok)
    print(f"[{'OK' if ok else 'FALLO'}] {nombre}: {detalle}")


def main():
    print(f"Servidor: {SIM_BASE}\nCuenta:   {ACCOUNT}\n")
    sim = Sim()

    r = sim.get("/brokerage/accounts")
    cuentas = {a["AccountID"]: a for a in r.json().get("Accounts", [])} if r.ok else {}
    a = cuentas.get(ACCOUNT)
    check("Cuenta visible", a is not None, f"{a.get('AccountType')} / {a.get('Status')}" if a else r.text[:200])
    if a is None:
        sys.exit(1)

    b = sim.balances()
    check("Saldo", True, f"Equity {b['Equity']}  BuyingPower {b['BuyingPower']}")

    q = sim.quote(SYMBOL)
    check(f"Datos {SYMBOL}", not q["MarketFlags"]["IsDelayed"],
          f"Last {q['Last']}  Bid {q['Bid']}  Ask {q['Ask']}  Delayed {q['MarketFlags']['IsDelayed']}")

    precio = round(float(q["Bid"]) * 0.90, 2)
    r = sim.confirm(sim.limit_order(SYMBOL, "BUY", 1, precio))
    check("Permiso de ordenes (orderconfirm, sin enviar)", r.ok, f"HTTP {r.status_code} {r.text[:300]}")

    print(f"\n{sum(resultados)}/{len(resultados)} comprobaciones OK")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
