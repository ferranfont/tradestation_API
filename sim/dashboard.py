"""
Genera sim/sim_dashboard.html con la foto de las cuentas SIM y REAL, y lo abre.
Arriba hay un conmutador SIMULACION / REAL; el modo se recuerda en la URL (#real).

Solo lectura: usa el token sin permiso Trade, asi que esta pagina no puede operar.
La pagina es estatica: vuelve a ejecutar este script para actualizarla.

Uso:  python sim/dashboard.py [--no-open] [--real]   (--real: abrir en modo REAL)
"""

import argparse
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from cuenta import cotizacion, foto
from ts_broker import CUENTA_DEFECTO, Broker, cuentas

AQUI = Path(__file__).resolve().parent
PLANTILLA = AQUI / "dashboard_plantilla.html"
SALIDA = AQUI / "sim_dashboard.html"


def datos_modo(modo: str) -> dict:
    try:
        ids = [a["AccountID"] for a in cuentas(modo)]
        ids.sort(key=lambda i: i != CUENTA_DEFECTO[modo])     # la del .env primero
        fotos = []
        for i in ids:
            try:
                fotos.append(foto(Broker(modo, i)))
            except Exception as e:                          # una cuenta rota no tumba las demas
                fotos.append({"modo": modo, "cuenta": i, "error": str(e)[:300]})
        return {"cotizacion": cotizacion(Broker(modo, ids[0])) if ids else None, "cuentas": fotos}
    except Exception as e:
        return {"error": str(e)[:300], "cuentas": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-open", action="store_true", help="no abrir el navegador")
    ap.add_argument("--real", action="store_true", help="abrir la pagina en modo REAL")
    a = ap.parse_args()

    datos = {
        "hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modos": {m: datos_modo(m) for m in ("sim", "real")},
    }
    for m, d in datos["modos"].items():
        print(f"{m.upper():5s} {d.get('error') or ', '.join(c['cuenta'] for c in d['cuentas'])}")

    # "<" escapado: un texto de la API no puede cerrar el <script> de la plantilla
    js = json.dumps(datos, separators=(",", ":")).replace("<", "\\u003c")
    SALIDA.write_text(PLANTILLA.read_text(encoding="utf-8").replace("/*__DATOS__*/null", js), encoding="utf-8")
    print(f"Pagina: {SALIDA}")
    if not a.no_open:
        webbrowser.open(SALIDA.as_uri() + ("#real" if a.real else ""))


if __name__ == "__main__":
    main()
