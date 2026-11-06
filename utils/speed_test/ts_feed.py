"""Cliente TradeStation para el speed test (async, httpx con conexion keep-alive)."""

import json
import time

import httpx

import common  # noqa: F401  (configura sys.path y .env)
from common import now_ns
from test_conection import API_BASE, get_access_token


class TSClient:
    TOKEN_TTL = 15 * 60  # el access token dura 20 min; se renueva a los 15

    def __init__(self):
        self._token = None
        self._token_time = 0.0
        # Una sola conexion reutilizada: no se mide el handshake TLS en cada peticion
        self.http = httpx.AsyncClient(base_url=API_BASE, timeout=30,
                                      limits=httpx.Limits(max_keepalive_connections=2))

    def headers(self) -> dict:
        if not self._token or time.time() - self._token_time > self.TOKEN_TTL:
            self._token = get_access_token()
            self._token_time = time.time()
        return {"Authorization": f"Bearer {self._token}"}

    async def quote(self, symbol: str) -> tuple[dict, int, int]:
        """Snapshot de cotizacion. Devuelve (quote, ns_red, ns_parseo)."""
        h = self.headers()
        t0 = now_ns()
        r = await self.http.get(f"/marketdata/quotes/{symbol}", headers=h)
        t1 = now_ns()
        r.raise_for_status()
        q = r.json()["Quotes"][0]
        t2 = now_ns()
        return q, t1 - t0, t2 - t1

    async def bars(self, symbol: str, **params) -> tuple[list, int]:
        h = self.headers()
        t0 = now_ns()
        r = await self.http.get(f"/marketdata/barcharts/{symbol}", headers=h, params=params)
        r.raise_for_status()
        bars = r.json().get("Bars", [])
        return bars, now_ns() - t0

    async def stream_quotes(self, symbol: str, on_msg):
        """Stream de quotes. Llama on_msg(t_ns_llegada, dict) por cada mensaje."""
        h = self.headers()
        async with httpx.AsyncClient(base_url=API_BASE, timeout=None) as c:
            async with c.stream("GET", f"/marketdata/stream/quotes/{symbol}", headers=h) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"TS stream {r.status_code}: {await r.aread()}")
                async for line in r.aiter_lines():
                    t = now_ns()          # timestamp nada mas llegar la linea
                    if line:
                        on_msg(t, json.loads(line))

    async def close(self):
        await self.http.aclose()
