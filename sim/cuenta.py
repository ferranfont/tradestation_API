"""Foto de la cuenta SIM: la usan test_cuenta.py (terminal) y dashboard.py (HTML)."""

from datetime import datetime, timezone

from ts_sim import Sim

SYMBOL = "SPY"


def foto(sim: Sim) -> dict:
    b = sim.balances()
    d = b.get("BalanceDetail", {})
    q = sim.quote(SYMBOL)
    ordenes = []
    for o in sim.orders():
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
    } for p in sim.positions()]
    return {
        "cuenta": sim.account, "tipo": b.get("AccountType"),
        "hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "saldo": {
            "equity": b.get("Equity"), "efectivo": b.get("CashBalance"), "poder_compra": b.get("BuyingPower"),
            "poder_opciones": d.get("OptionBuyingPower"), "valor_mercado": b.get("MarketValue"),
            "pnl_hoy": b.get("TodaysProfitLoss"), "pnl_no_realizado": d.get("UnrealizedProfitLoss"),
            "pnl_realizado": d.get("RealizedProfitLoss"), "margen": d.get("RequiredMargin"),
            "day_trades": d.get("DayTrades"), "comision": b.get("Commission"),
        },
        "cotizacion": {
            "simbolo": q.get("Symbol"), "last": q.get("Last"), "bid": q.get("Bid"), "ask": q.get("Ask"),
            "hora": q.get("TradeTime"), "retrasado": q.get("MarketFlags", {}).get("IsDelayed"),
        },
        "posiciones": posiciones, "ordenes": ordenes,
    }
