"""
Genera sim/sim_dashboard.html con la foto actual de la cuenta SIM y lo abre.
La pagina es estatica: vuelve a ejecutar este script para actualizarla.

Uso:  python sim/dashboard.py [--no-open]
"""

import argparse
import json
import webbrowser
from pathlib import Path

from cuenta import foto
from ts_sim import Sim

AQUI = Path(__file__).resolve().parent
PLANTILLA = AQUI / "dashboard_plantilla.html"
SALIDA = AQUI / "sim_dashboard.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-open", action="store_true", help="no abrir el navegador")
    a = ap.parse_args()

    # "<" escapado: un texto de la API no puede cerrar el <script> de la plantilla
    datos = json.dumps(foto(Sim()), separators=(",", ":")).replace("<", "\\u003c")
    SALIDA.write_text(PLANTILLA.read_text(encoding="utf-8").replace("/*__DATOS__*/null", datos), encoding="utf-8")
    print(f"Pagina: {SALIDA}")
    if not a.no_open:
        webbrowser.open(SALIDA.as_uri())


if __name__ == "__main__":
    main()
