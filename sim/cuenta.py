"""Foto de una cuenta: la usan test_cuenta.py (terminal) y dashboard.py (HTML)."""

from ts_broker import Broker

SYMBOL = "SPY"


def cotizacion(b: Broker, symbol: str = SYMBOL) -> dict:
    q = b.quote(symbol)
    return {
        "simbolo": q.get("Symbol"), "last": q.get("Last"), "bid": q.get("Bid"), "ask": q.get("Ask"),
        "hora": q.get("TradeTime"), "retrasado": q.get("MarketFlags", {}).get("IsDelayed"),
    }


def foto(b: Broker) -> dict:
    s = b.balances()
    d = s.get("BalanceDetail", {})
    ordenes = []
    for o in b.orders():
        leg = (o.get("Legs") or [{}])[0]
        ordenes.append({
            "id": o.get("OrderID"), "abierta": o.get("OpenedDateTime"), "simbolo": leg.get("Symbol"),
            "lado": leg.get("BuyOrSell"), "cantidad": leg.get("QuantityOrdered"),
            "ejecutado": leg.get("ExecQuantity"), "tipo": o.get("OrderType"),
            "limite": o.get("LimitPrice"), "vigencia": o.get("Duration"), "precio_ejec": o.get("FilledPrice"),
            "codigo": o.get("Status"), "estado": o.get("StatusDescription"), "motivo": o.get("RejectReason"),
        })
    posiciones = [{
        "simbolo": p.get("Symbol"), "lado": p.get("LongShort"), "cantidad": p.get("Quantity"),
        "precio_medio": p.get("AveragePrice"), "ultimo": p.get("Last"), "valor": p.get("MarketValue"),
        "pnl": p.get("UnrealizedProfitLoss"), "pnl_pct": p.get("UnrealizedProfitLossPercent"),
    } for p in b.positions()]
    return {
        "modo": b.modo, "cuenta": b.account, "tipo": s.get("AccountType"),
        "saldo": {
            "equity": s.get("Equity"), "efectivo": s.get("CashBalance"), "poder_compra": s.get("BuyingPower"),
            "poder_opciones": d.get("OptionBuyingPower"), "valor_mercado": s.get("MarketValue"),
            "pnl_hoy": s.get("TodaysProfitLoss"), "pnl_no_realizado": d.get("UnrealizedProfitLoss"),
            "pnl_realizado": d.get("RealizedProfitLoss"),
            # acciones: RequiredMargin; futuros: InitialMargin
            "margen": d.get("RequiredMargin", d.get("InitialMargin")),
            "day_trades": d.get("DayTrades"), "comision": s.get("Commission"),
        },
        "posiciones": posiciones, "ordenes": ordenes,
    }
