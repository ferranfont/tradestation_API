"""
Cliente de la cuenta SIMULADA de TradeStation.

Seguridad:
  - La URL base es sim-api.tradestation.com, fija: este cliente no habla con live.
  - Toda ruta o cuerpo con una cuenta exige que empiece por "SIM".
  - Usa su propio token (TS_SIM_REFRESH_TOKEN), con permiso Trade. El token principal
    (TS_REFRESH_TOKEN) sigue siendo de solo lectura.

OJO: un token con Trade tambien es valido contra la API real. Las protecciones de
aqui viven en este codigo, no en el token: no lo uses fuera de este cliente.
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import set_key

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "utils"))
import test_conection as tc  # noqa: E402  (carga el .env)

SIM_BASE = "https://sim-api.tradestation.com/v3"
ENV_PATH = ROOT / ".env"
SCOPES = tc.SCOPES + " Trade"
ACCOUNT = os.getenv("SIM_TRADESTATION_ACCOUNT_NUMBER", "").strip()


def exige_sim(account: str) -> str:
    if not str(account).startswith("SIM"):
        raise ValueError(f"Cuenta rechazada: {account!r} no es una cuenta SIM")
    return account


def _token_post(**data) -> requests.Response:
    return requests.post(tc.TOKEN_URL, timeout=15, data={
        "client_id": tc.CLIENT_ID, "client_secret": tc.CLIENT_SECRET, **data})


def access_token() -> str:
    refresh = os.getenv("TS_SIM_REFRESH_TOKEN")
    if refresh:
        r = _token_post(grant_type="refresh_token", refresh_token=refresh)
        if r.ok:
            return r.json()["access_token"]
        print(f"Refresh token SIM no valido ({r.status_code}). Hace falta login.")

    tc.SCOPES = SCOPES                     # get_auth_code usa este valor para el login
    code = tc.get_auth_code()
    r = _token_post(grant_type="authorization_code", code=code, redirect_uri=tc.REDIRECT_URI)
    if not r.ok:
        sys.exit(f"Error obteniendo token SIM ({r.status_code}): {r.text}")
    data = r.json()
    if "Trade" not in data.get("scope", "").split():
        sys.exit(f"TradeStation no ha concedido el permiso Trade. Concedidos: {data.get('scope')}")
    set_key(str(ENV_PATH), "TS_SIM_REFRESH_TOKEN", data["refresh_token"])
    os.environ["TS_SIM_REFRESH_TOKEN"] = data["refresh_token"]
    print("Token SIM guardado en .env (TS_SIM_REFRESH_TOKEN)")
    return data["access_token"]


class Sim:
    def __init__(self, account: str = ACCOUNT):
        self.account = exige_sim(account)
        self.http = requests.Session()
        self.http.headers["Authorization"] = f"Bearer {access_token()}"

    def _send(self, method: str, path: str, **kw) -> requests.Response:
        return self.http.request(method, SIM_BASE + path, timeout=20, **kw)

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

    def limit_order(self, symbol: str, side: str, qty: int, price: float, tif: str = "DAY") -> dict:
        return {
            "AccountID": exige_sim(self.account), "Symbol": symbol, "Quantity": str(qty),
            "OrderType": "Limit", "LimitPrice": f"{price:.2f}", "TradeAction": side,
            "TimeInForce": {"Duration": tif}, "Route": "Intelligent",
        }

    def confirm(self, order: dict) -> requests.Response:
        """Valida la orden sin enviarla al mercado."""
        exige_sim(order["AccountID"])
        return self._send("POST", "/orderexecution/orderconfirm", json=order)

    def place(self, order: dict) -> requests.Response:
        exige_sim(order["AccountID"])
        return self._send("POST", "/orderexecution/orders", json=order)

    def cancel(self, order_id: str) -> requests.Response:
        return self._send("DELETE", f"/orderexecution/orders/{order_id}")
