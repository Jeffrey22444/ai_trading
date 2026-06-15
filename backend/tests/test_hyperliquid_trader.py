from datetime import datetime

import pytest

from trading.hyperliquid_trader import HyperliquidTrader


class FakeHyperliquidExchange:
    def __init__(self):
        self.sandbox = False
        self.orders = []
        self.cancelled = []
        self.open_orders = [{"id": "sl"}, {"id": "tp"}]
        self.fail_protection = False
        self.reject_opening = False

    def set_sandbox_mode(self, enabled):
        self.sandbox = enabled

    def load_markets(self):
        return {}

    def fetch_ticker(self, symbol):
        return {"last": 100.0}

    def create_order(self, symbol, order_type, side, amount, price, params):
        if self.reject_opening and not params:
            return {"id": None, "status": "rejected"}
        if self.fail_protection and (
            "stopLossPrice" in params or "takeProfitPrice" in params
        ):
            raise RuntimeError("protection rejected")
        order = {
            "id": str(len(self.orders) + 1),
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "price": price,
            "params": params,
        }
        self.orders.append(order)
        return order

    def fetch_open_orders(self, symbol):
        return self.open_orders

    def cancel_order(self, order_id, symbol):
        self.cancelled.append((order_id, symbol))

    def amount_to_precision(self, symbol, quantity):
        return f"{quantity:.3f}"

    def fetch_balance(self):
        return {"USDC": {"total": 1_000.0, "free": 900.0}}

    def fetch_positions(self):
        return [
            {
                "symbol": "BTC/USDC:USDC",
                "side": "long",
                "contracts": 0.1,
                "entryPrice": 90.0,
                "markPrice": 100.0,
                "unrealizedPnl": 1.0,
                "percentage": 1.1,
                "leverage": 2,
                "initialMargin": 5.0,
                "timestamp": int(datetime.now().timestamp() * 1000),
            }
        ]

    def set_leverage(self, leverage, symbol, params=None):
        return {"leverage": leverage, "symbol": symbol, "params": params}

    def set_margin_mode(self, mode, symbol, params=None):
        return {"mode": mode, "symbol": symbol, "params": params}


@pytest.fixture
def trader():
    return HyperliquidTrader(exchange=FakeHyperliquidExchange(), testnet=True)


def test_hyperliquid_trader_enables_sandbox(trader):
    assert trader.exchange.sandbox is True


@pytest.mark.asyncio
async def test_open_long_uses_market_price_and_distinct_protection_params(trader):
    await trader.open_long("BTC", 0.1, 2, 95.0, 110.0)

    opening, stop_loss, take_profit = trader.exchange.orders
    assert opening["symbol"] == "BTC/USDC:USDC"
    assert opening["type"] == "market"
    assert opening["price"] == 100.0
    assert stop_loss["params"] == {"stopLossPrice": 95.0, "reduceOnly": True}
    assert take_profit["params"] == {"takeProfitPrice": 110.0, "reduceOnly": True}


@pytest.mark.asyncio
async def test_direct_open_rejects_missing_protection(trader):
    with pytest.raises(ValueError, match="必须同时设置止损价和止盈价"):
        await trader.open_long("BTC", 0.1, 2)


@pytest.mark.asyncio
async def test_direct_open_rejects_wrong_protection_direction(trader):
    with pytest.raises(ValueError, match="止损止盈方向无效"):
        await trader.open_long("BTC", 0.1, 2, 105.0, 110.0)


@pytest.mark.asyncio
async def test_protection_failure_attempts_immediate_reduce_only_close(trader):
    trader.exchange.fail_protection = True

    with pytest.raises(RuntimeError, match="保护单失败"):
        await trader.open_short("BTC", 0.1, 2, 105.0, 90.0)

    emergency_close = trader.exchange.orders[-1]
    assert emergency_close["side"] == "buy"
    assert emergency_close["params"] == {"reduceOnly": True}


@pytest.mark.asyncio
async def test_rejected_opening_order_does_not_place_protection_orders(trader):
    trader.exchange.reject_opening = True

    with pytest.raises(RuntimeError, match="开仓订单被拒绝"):
        await trader.open_long("BTC", 0.1, 2, 95.0, 110.0)

    assert trader.exchange.orders == []


@pytest.mark.asyncio
async def test_cancel_all_orders_cancels_each_open_order(trader):
    assert await trader.cancel_all_orders("BTC") is True
    assert trader.exchange.cancelled == [
        ("sl", "BTC/USDC:USDC"),
        ("tp", "BTC/USDC:USDC"),
    ]


@pytest.mark.asyncio
async def test_partial_close_rejects_quantity_above_position(trader):
    with pytest.raises(ValueError, match="超过持仓数量"):
        await trader.close_long("BTC", 0.2)


@pytest.mark.asyncio
async def test_positions_and_balance_use_logical_symbols_and_usdc(trader):
    balance = await trader.get_balance()
    positions = await trader.get_positions()

    assert balance.currency == "USDC"
    assert balance.available_balance == 900.0
    assert positions[0].symbol == "BTC"
    assert positions[0].side == "LONG"


@pytest.mark.asyncio
async def test_set_margin_mode_supplies_required_leverage(trader):
    assert await trader.set_margin_mode("BTC", True) is True
