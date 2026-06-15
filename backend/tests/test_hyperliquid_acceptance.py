import pytest

from scripts.hyperliquid_acceptance import wait_for_position
from trading.interface import Position


class PositionTrader:
    def __init__(self, positions):
        self.positions = positions

    async def get_positions(self):
        return self.positions


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
