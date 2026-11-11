"""
Cliente de TradeStation con conmutador SIM / REAL.

El modo decide a la vez la URL y el tipo de cuenta, y se comprueban entre si:
  sim   -> sim-api.tradestation.com   y solo cuentas que empiezan por "SIM"
  real  -> api.tradestation.com       y solo cuentas que NO empiezan por "SIM"
Si no cuadran, se lanza un error antes de hablar con la API.

Tokens. Comprobado el 2026-11-07: TradeStation NO separa los tokens por entorno, los
dos valen contra SIM y contra REAL. La separacion es por permisos:
  TS_REFRESH_TOKEN        solo lectura (sin Trade). Lo usa todo lo que solo mira:
                          panel, tablas, cotizaciones. Con el no se puede operar.
  TS_TRADE_REFRESH_TOKEN  con Trade. Solo se carga con operar=True. Opera en SIM y en REAL.

Operar en REAL exige ademas confirmo=<numero de cuenta>, escrito a mano.

Vigencia: SIEMPRE DAY (se cancela sola al final del dia). Nunca GTC: una orden olvidada
no puede quedar viva de un dia para otro. Fuera de horario TradeStation rechaza las DAY.
"""

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import set_key

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "utils"))
import test_conection as tc  # noqa: E402  (carga el .env)

BASES = {
    "sim": "https://sim-api.tradestation.com/v3",
    "real": "https://api.tradestation.com/v3",
}
CUENTA_DEFECTO = {
    "sim": os.getenv("SIM_TRADESTATION_ACCOUNT_NUMBER", "").strip(),
    "real": os.getenv("TRADESTATION_ACCOUNT_NUMBER", "").strip(),
}
ENV_PATH = ROOT / ".env"
TRADE_VAR = "TS_TRADE_REFRESH_TOKEN"
SCOPES_TRADE = tc.SCOPES + " Trade"


def comprueba_cuenta(modo: str, account: str) -> str:
    es_sim = str(account).startswith("SIM")
    if modo == "sim" and not es_sim:
        raise ValueError(f"Modo SIM con la cuenta {account!r}, que no es SIM. Parado.")
    if modo == "real" and es_sim:
        raise ValueError(f"Modo REAL con la cuenta {account!r}, que es SIM. Parado.")
    return account


def _token_post(**data) -> requests.Response:
    return requests.post(tc.TOKEN_URL, timeout=15, data={
        "client_id": tc.CLIENT_ID, "client_secret": tc.CLIENT_SECRET, **data})


def token_trade() -> str:
    """Access token con permiso Trade. Si no hay refresh token valido, abre el login."""
    refresh = os.getenv(TRADE_VAR)
    if refresh:
        r = _token_post(grant_type="refresh_token", refresh_token=refresh)
        if r.ok:
            return r.json()["access_token"]
        print(f"Refresh token de operar no valido ({r.status_code}). Hace falta login.")

    tc.SCOPES = SCOPES_TRADE               # get_auth_code usa este valor para el login
    code = tc.get_auth_code()
    r = _token_post(grant_type="authorization_code", code=code, redirect_uri=tc.REDIRECT_URI)
    if not r.ok:
        sys.exit(f"Error obteniendo token de operar ({r.status_code}): {r.text}")
    data = r.json()
    if "Trade" not in data.get("scope", "").split():
        sys.exit(f"TradeStation no ha concedido el permiso Trade. Concedidos: {data.get('scope')}")
    set_key(str(ENV_PATH), TRADE_VAR, data["refresh_token"])
    os.environ[TRADE_VAR] = data["refresh_token"]
    print(f"Token de operar guardado en .env ({TRADE_VAR})")
    return data["access_token"]


_lectura = {"token": None, "hasta": 0.0}


def token_lectura() -> str:
    """Access token de solo lectura, reutilizado mientras le queden minutos (dura 20)."""
    if time.monotonic() > _lectura["hasta"]:
        _lectura["token"] = tc.get_access_token()
        _lectura["hasta"] = time.monotonic() + 15 * 60
    return _lectura["token"]


def cuentas(modo: str) -> list[dict]:
    """Cuentas que ve la API en ese modo (con el token de solo lectura)."""
    r = requests.get(BASES[modo] + "/brokerage/accounts", timeout=20,
                     headers={"Authorization": f"Bearer {token_lectura()}"})
    r.raise_for_status()
    return [a for a in r.json().get("Accounts", [])
            if a["AccountID"].startswith("SIM") == (modo == "sim")]


class Broker:
    def __init__(self, modo: str = "sim", account: str | None = None,
                 operar: bool = False, confirmo: str | None = None):
        if modo not in BASES:
            raise ValueError(f"Modo desconocido: {modo!r}. Usa 'sim' o 'real'.")
        self.modo = modo
        self.base = BASES[modo]
        self.account = comprueba_cuenta(modo, account or CUENTA_DEFECTO[modo])
        self.operar = operar
        if operar and modo == "real" and confirmo != self.account:
            raise PermissionError(
                f"Operar en REAL exige confirmar la cuenta: confirmo={self.account!r}. Parado.")
        self.http = requests.Session()
        token = token_trade() if operar else token_lectura()
        self.http.headers["Authorization"] = f"Bearer {token}"

    @property
    def etiqueta(self) -> str:
        return "*** REAL: DINERO REAL ***" if self.modo == "real" else "SIMULACION"

    def _send(self, method: str, path: str, **kw) -> requests.Response:
        return self.http.request(method, self.base + path, timeout=20, **kw)

    def get(self, path: str, **params) -> requests.Response:
        return self._send("GET", path, params=params)

    def quote(self, symbol: str) -> dict:
        r = self.get(f"/marketdata/quotes/{symbol}")
        r.raise_for_status()
        return r.json()["Quotes"][0]

    def balances(self) -> dict:
        return self._cuenta("balances", "Balances")[0]

    def positions(self) -> list[dict]:
        return self._cuenta("positions", "Positions")

    def orders(self) -> list[dict]:
        return self._cuenta("orders", "Orders")

    def _cuenta(self, recurso: str, clave: str) -> list[dict]:
        r = self.get(f"/brokerage/accounts/{self.account}/{recurso}")
        r.raise_for_status()
        return r.json().get(clave, [])

    # ---- Ordenes: solo con operar=True ----

    def _exige_operar(self, order: dict | None = None):
        if not self.operar:
            raise PermissionError("Este cliente es de solo lectura: crealo con operar=True.")
        if order is not None and order["AccountID"] != self.account:
            raise ValueError(f"La orden es de {order['AccountID']!r} y el cliente de {self.account!r}.")

    def limit_order(self, symbol: str, side: str, qty: int, price: float) -> dict:
        """Orden limitada, siempre DAY: nunca GTC."""
        return {
            "AccountID": self.account, "Symbol": symbol, "Quantity": str(qty),
            "OrderType": "Limit", "LimitPrice": f"{price:.2f}", "TradeAction": side,
            "TimeInForce": {"Duration": "DAY"}, "Route": "Intelligent",
        }

    def confirm(self, order: dict) -> requests.Response:
        """Valida la orden sin enviarla al mercado."""
        self._exige_operar(order)
        return self._send("POST", "/orderexecution/orderconfirm", json=order)

    def place(self, order: dict) -> requests.Response:
        self._exige_operar(order)
        return self._send("POST", "/orderexecution/orders", json=order)

    def cancel(self, order_id: str) -> requests.Response:
        self._exige_operar()
        if not any(o.get("OrderID") == order_id for o in self.orders()):
            raise ValueError(f"La orden {order_id} no es de la cuenta {self.account}. No se cancela.")
        return self._send("DELETE", f"/orderexecution/orders/{order_id}")


# ---- Linea de comandos comun a los scripts ----

def args_modo(ap, operar: bool = False):
    ap.add_argument("--real", action="store_true", help="cuenta REAL (por defecto: SIM)")
    ap.add_argument("--cuenta", help="numero de cuenta (por defecto: el del .env para ese modo)")
    if operar:
        ap.add_argument("--confirmo", metavar="CUENTA", help="obligatorio en REAL: repite el numero de cuenta")


def broker_desde_args(a, operar: bool = False) -> Broker:
    b = Broker("real" if a.real else "sim", a.cuenta, operar, getattr(a, "confirmo", None))
    print(f"[{b.etiqueta}]  {b.account}  {b.base}\n")
    return b
