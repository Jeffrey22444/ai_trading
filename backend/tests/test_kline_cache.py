import asyncio
from datetime import datetime
from decimal import Decimal

import pytest

from market.data_cache import KlineCache
from market.types import Kline


def make_kline(symbol: str = "BTC", interval: str = "3m") -> Kline:
    now = int(datetime.now().timestamp() * 1000)
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=now,
        close_time=now,
        open_price=Decimal("1"),
        high_price=Decimal("2"),
        low_price=Decimal("0.5"),
        close_price=Decimal("1.5"),
        volume=Decimal("10"),
        quote_volume=Decimal("15"),
        trades_count=1,
        taker_buy_base_volume=Decimal("4"),
        taker_buy_quote_volume=Decimal("6"),
        is_final=True,
    )


@pytest.mark.asyncio
async def test_sync_snapshot_can_read_cache_while_async_loop_is_running():
    cache = KlineCache()
    await cache.add_kline(make_kline())

    snapshots = await asyncio.gather(
        *[asyncio.to_thread(cache.get_klines_snapshot, "BTC", "3m", 1) for _ in range(3)]
    )

    assert [len(snapshot) for snapshot in snapshots] == [1, 1, 1]
