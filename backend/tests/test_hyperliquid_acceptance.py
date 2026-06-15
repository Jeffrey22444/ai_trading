import pytest

from scripts.hyperliquid_acceptance import verify_protection_orders, wait_for_position
from trading.interface import Position


class PositionTrader:
    def __init__(self, positions):
        self.positions = positions

    async def get_positions(self):
        return self.positions


class ProtectionExchange:
    def __init__(self, orders):
        self.orders = orders

    def fetch_open_orders(self, symbol):
        return self.orders


class ProtectionTrader:
    def __init__(self, orders):
        self.exchange = ProtectionExchange(orders)


def position(symbol, side):
    return Position(
        symbol=symbol,
        side=side,
        size=1,
        entry_price=1,
        mark_price=1,
        unrealized_pnl=0,
        percentage_pnl=0,
        leverage=1,
        margin=1,
        timestamp=None,
    )


@pytest.mark.asyncio
async def test_wait_for_position_matches_logical_symbol():
    found = await wait_for_position(
        PositionTrader([position("BTC/USDC:USDC", "LONG")]),
        "BTC",
        "LONG",
        attempts=1,
    )

    assert found.side == "LONG"


@pytest.mark.asyncio
async def test_wait_for_no_position_returns_when_clear():
    assert await wait_for_position(PositionTrader([]), "BTC", None, attempts=1) is None


@pytest.mark.asyncio
async def test_protection_verifier_requires_stop_loss_and_take_profit():
    trader = ProtectionTrader(
        [
            {"reduceOnly": True, "triggerPrice": 95.0, "side": "sell"},
            {"reduceOnly": True, "triggerPrice": 110.0, "side": "sell"},
        ]
    )

    await verify_protection_orders(trader, "BTC", "LONG", 100.0, attempts=1)


@pytest.mark.asyncio
async def test_protection_verifier_rejects_two_orders_on_same_side_of_price():
    trader = ProtectionTrader(
        [
            {"reduceOnly": True, "triggerPrice": 95.0, "side": "sell"},
            {"reduceOnly": True, "triggerPrice": 90.0, "side": "sell"},
        ]
    )

    with pytest.raises(RuntimeError, match="未观察到有效止损和止盈保护单"):
        await verify_protection_orders(trader, "BTC", "LONG", 100.0, attempts=1)
