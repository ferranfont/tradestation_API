"""
Test de conexión con la API de TradeStation (v3).

Imprime la cotización "Last" de Apple (AAPL).

Autenticación (Auth0 / OAuth2 Authorization Code):
  - La primera vez abre el navegador para que hagas login en TradeStation.
    El script levanta un servidor local en http://localhost:3000 para recibir
    el "code", lo cambia por tokens (usando API_Key + API_SECRET_KEY) y guarda
    el refresh token en .env como TS_REFRESH_TOKEN.
  - Las siguientes veces usa directamente el refresh token (sin navegador).

Uso:
    python utils/test_conection.py
"""

import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv, set_key
import os

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

CLIENT_ID = os.getenv("API_Key")
CLIENT_SECRET = os.getenv("API_SECRET_KEY")
REFRESH_TOKEN = os.getenv("TS_REFRESH_TOKEN")

AUTH_URL = "https://signin.tradestation.com/authorize"
TOKEN_URL = "https://signin.tradestation.com/oauth/token"
API_BASE = "https://api.tradestation.com/v3"
REDIRECT_URI = "http://localhost:3000"
SCOPES = "openid offline_access profile MarketData ReadAccount OptionSpreads"

SYMBOL = "BA"


def get_auth_code() -> str:
    """Abre el navegador para login y captura el authorization code en localhost:3000."""
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                result["code"] = params["code"][0]
                msg = "Autenticacion completada. Puedes cerrar esta ventana."
            else:
                result["error"] = params.get("error_description", params.get("error", ["desconocido"]))[0]
                msg = f"Error de autenticacion: {result['error']}"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h3>{msg}</h3>".encode("utf-8"))

        def log_message(self, *args):
            pass

    url = AUTH_URL + "?" + urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "audience": "https://api.tradestation.com",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    })

    print("Abriendo navegador para login en TradeStation...")
    print(f"Si no se abre, visita:\n{url}\n")
    webbrowser.open(url)

    server = HTTPServer(("localhost", 3000), Handler)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()

    if "error" in result:
        sys.exit(f"Error en login: {result['error']}")
    return result["code"]


def get_access_token() -> str:
    """Obtiene un access token usando el refresh token, o con login si no existe."""
    global REFRESH_TOKEN

    if REFRESH_TOKEN:
        r = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
        }, timeout=15)
        if r.ok:
            data = r.json()
            # Si TradeStation rota el refresh token, guardamos el nuevo
            if data.get("refresh_token") and data["refresh_token"] != REFRESH_TOKEN:
                set_key(str(ENV_PATH), "TS_REFRESH_TOKEN", data["refresh_token"])
            return data["access_token"]
        print(f"Refresh token no valido ({r.status_code}): {r.text}\nSe requiere login de nuevo.")

    code = get_auth_code()
    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }, timeout=15)
    if not r.ok:
        sys.exit(f"Error obteniendo token ({r.status_code}): {r.text}")

    data = r.json()
    if data.get("refresh_token"):
        REFRESH_TOKEN = data["refresh_token"]
        set_key(str(ENV_PATH), "TS_REFRESH_TOKEN", REFRESH_TOKEN)
        print("Refresh token guardado en .env (TS_REFRESH_TOKEN)\n")
    return data["access_token"]


def get_last_price(symbol: str, access_token: str) -> dict:
    r = requests.get(
        f"{API_BASE}/marketdata/quotes/{symbol}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not r.ok:
        sys.exit(f"Error obteniendo cotizacion ({r.status_code}): {r.text}")
    data = r.json()
    if data.get("Errors"):
        sys.exit(f"Error de la API: {data['Errors']}")
    return data["Quotes"][0]


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        sys.exit("Faltan API_Key o API_SECRET_KEY en el archivo .env")

    token = get_access_token()
    quote = get_last_price(SYMBOL, token)

    print(f"Conexion OK con TradeStation")
    print(f"{quote['Symbol']}  Last: {quote.get('Last')}  "
          f"(Bid: {quote.get('Bid')}  Ask: {quote.get('Ask')})  "
          f"Hora: {quote.get('TradeTime')}")


if __name__ == "__main__":
    main()
