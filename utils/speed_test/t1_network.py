"""
Test 1 - Red base: tiempo de conexion TCP (y TLS) a los servidores de cada broker.

- TradeStation: api.tradestation.com:443 (TCP y TCP+TLS).
- IB: detecta a que servidores de IB esta conectado TWS/IB Gateway (conexiones
  salientes del proceso que escucha en IB_PORT) y mide el TCP connect a ellos.

Solo abre y cierra conexiones TCP (no envia datos a IB).

Uso:  python utils/speed_test/t1_network.py [--n 30]
"""

import argparse
import socket
import ssl
import time

import psutil

from common import IB_PORT, ms, now_ns, print_stats, save_csv

TS_HOST = "api.tradestation.com"


def tcp_connect_ns(host: str, port: int, tls: bool = False) -> int:
    t0 = now_ns()
    with socket.create_connection((host, port), timeout=5) as s:
        if tls:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(s, server_hostname=host):
                pass
    return now_ns() - t0


def ib_remote_servers() -> list[tuple[str, int]]:
    """Servidores remotos a los que esta conectado el proceso de TWS / IB Gateway."""
    listeners = [c for c in psutil.net_connections("tcp")
                 if c.status == psutil.CONN_LISTEN and c.laddr.port == IB_PORT and c.pid]
    if not listeners:
        print(f"No hay TWS/Gateway escuchando en el puerto {IB_PORT}")
        return []
    proc = psutil.Process(listeners[0].pid)
    print(f"TWS/Gateway: PID {proc.pid} ({proc.name()})")
    remotes = {(c.raddr.ip, c.raddr.port) for c in proc.net_connections("tcp")
               if c.status == psutil.CONN_ESTABLISHED and c.raddr
               and not c.raddr.ip.startswith(("127.", "::1"))}
    return sorted(remotes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="muestras por destino")
    n = ap.parse_args().n

    targets = [("TS tcp " + TS_HOST, TS_HOST, 443, False),
               ("TS tcp+tls " + TS_HOST, TS_HOST, 443, True)]
    for ip, port in ib_remote_servers():
        try:
            name = socket.gethostbyaddr(ip)[0]
        except OSError:
            name = ip
        targets.append((f"IB tcp {name}:{port}", ip, port, False))

    rows, series = [], {}
    for label, host, port, tls in targets:
        vals = []
        for i in range(n):
            try:
                v = ms(tcp_connect_ns(host, port, tls))
            except OSError as e:
                print(f"{label}: error {e}")
                break
            vals.append(v)
            rows.append({"target": label, "sample": i, "ms": round(v, 3)})
            time.sleep(0.1)
        series[label[:60]] = vals

    print_stats("Conexion TCP / TLS", series)
    save_csv("t1_network", rows)


if __name__ == "__main__":
    main()
