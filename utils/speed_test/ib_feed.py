"""Cliente Interactive Brokers para el speed test (ib_async, SOLO LECTURA)."""

from ib_async import IB, Index

import common
from common import IB_CLIENT_ID, IB_HOST, IB_PORT


async def connect() -> IB:
    ib = IB()
    # readonly=True: la conexion no puede enviar ordenes (cuenta real)
    await ib.connectAsync(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, readonly=True, timeout=15)
    ib.reqMarketDataType(1)  # 1 = datos en tiempo real (no delayed)
    print(f"IB conectado a {IB_HOST}:{IB_PORT} (clientId {IB_CLIENT_ID}, solo lectura)")
    return ib


async def spx_contract(ib: IB) -> Index:
    c = Index(common.IB_SYMBOL, common.IB_EXCHANGE, common.IB_CURRENCY)
    await ib.qualifyContractsAsync(c)
    return c
