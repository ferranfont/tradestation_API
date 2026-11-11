"""
Test de conexion: acceso a la cuenta, datos en tiempo real y permiso de ordenes.
NO envia ninguna orden: orderconfirm solo valida.

Uso:
    python sim/test_conexion.py                          # SIM
    python sim/test_conexion.py --real                   # REAL, solo lectura
    python sim/test_conexion.py --real --confirmo 12083744
                                                         # REAL + validar una orden (sin enviarla)
"""

import argparse
import sys

from ts_broker import Broker, args_modo

SYMBOL = "SPY"
resultados = []


def check(nombre: str, ok: bool, detalle: str = ""):
    resultados.append(ok)
    print(f"[{'OK' if ok else 'FALLO'}] {nombre}: {detalle}")


def main():
    ap = argparse.ArgumentParser()
    args_modo(ap, operar=True)
    a = ap.parse_args()
    modo = "real" if a.real else "sim"
    # En REAL solo se carga el token de operar si se confirma la cuenta
    operar = not a.real or a.confirmo is not None
    b = Broker(modo, a.cuenta, operar, a.confirmo)
    print(f"[{b.etiqueta}]\nServidor: {b.base}\nCuenta:   {b.account}\n")

    r = b.get("/brokerage/accounts")
    cuentas = {x["AccountID"]: x for x in r.json().get("Accounts", [])} if r.ok else {}
    x = cuentas.get(b.account)
    check("Cuenta visible", x is not None, f"{x.get('AccountType')} / {x.get('Status')}" if x else r.text[:200])
    if x is None:
        sys.exit(1)

    s = b.balances()
    check("Saldo", True, f"Equity {s['Equity']}  BuyingPower {s['BuyingPower']}")

    q = b.quote(SYMBOL)
    check(f"Datos {SYMBOL}", not q["MarketFlags"]["IsDelayed"],
          f"Last {q['Last']}  Bid {q['Bid']}  Ask {q['Ask']}  Delayed {q['MarketFlags']['IsDelayed']}")

    if operar:
        precio = round(float(q["Bid"]) * 0.90, 2)
        r = b.confirm(b.limit_order(SYMBOL, "BUY", 1, precio))
        check("Permiso de ordenes (orderconfirm, sin enviar)", r.ok, f"HTTP {r.status_code} {r.text[:300]}")
    else:
        print("[--] Permiso de ordenes: no comprobado (en REAL hace falta --confirmo <cuenta>)")

    print(f"\n{sum(resultados)}/{len(resultados)} comprobaciones OK")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
