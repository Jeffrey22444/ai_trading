import asyncio
from datetime import datetime, timedelta

import pytest

from market.hyperliquid_market import HyperliquidMarketClient


class FakePublicExchange:
    def __init__(self):
        self.sandbox = False
        self.calls = []

    def set_sandbox_mode(self, enabled):
        self.sandbox = enabled

    def fetch_ohlcv(self, symbol, timeframe, limit):
        self.calls.append((symbol, timeframe, limit))
        return [[1_000, 10, 12, 9, 11, 5]]

    def parse_timeframe(self, timeframe):
        return {"1h": 3_600}[timeframe]


class TransientFailureExchange(FakePublicExchange):
    def __init__(self):
        super().__init__()
        self.fail_next = False

    def fetch_ohlcv(self, symbol, timeframe, limit):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("temporary network error")
        return super().fetch_ohlcv(symbol, timeframe, limit)


@pytest.mark.asyncio
async def test_hyperliquid_market_client_maps_symbol_and_kline():
    exchange = FakePublicExchange()
    client = HyperliquidMarketClient(exchange=exchange, testnet=True)

    klines = await client.get_klines("BTC", "1h", 1)

    assert exchange.sandbox is True
    assert exchange.calls == [("BTC/USDC:USDC", "1h", 1)]
    assert klines[0].symbol == "BTC"
    assert klines[0].close_price == 11
    assert klines[0].close_time == 3_600_999
    assert klines[0].is_final is True


@pytest.mark.asyncio
async def test_current_candle_is_not_marked_final():
    now = datetime.fromtimestamp(2)
    client = HyperliquidMarketClient(
        exchange=FakePublicExchange(), testnet=True, clock=lambda: now
    )

    klines = await client.get_klines("BTC", "1h", 1)

    assert klines[0].is_final is False


@pytest.mark.asyncio
async def test_polling_connect_marks_connection_healthy(monkeypatch):
    client = HyperliquidMarketClient(exchange=FakePublicExchange(), testnet=True)
    monkeypatch.setattr(client, "symbols", ["BTC"])
    monkeypatch.setattr(client, "timeframes", ["1h"])

    assert await client.connect() is True
    assert client.get_status().connected is True
    await client.disconnect()


@pytest.mark.asyncio
async def test_polling_disconnect_stops_message_loop(monkeypatch):
    client = HyperliquidMarketClient(
        exchange=FakePublicExchange(), testnet=True, poll_interval=0.001
    )
    monkeypatch.setattr(client, "symbols", ["BTC"])
    monkeypatch.setattr(client, "timeframes", ["1h"])
    assert await client.connect() is True

    task = asyncio.create_task(client.run_polling_loop())
    await asyncio.sleep(0.005)
    await client.disconnect()
    await asyncio.wait_for(task, timeout=1)

    assert client.get_status().connected is False


@pytest.mark.asyncio
async def test_polling_recovers_after_transient_failure(monkeypatch):
    exchange = TransientFailureExchange()
    client = HyperliquidMarketClient(exchange=exchange, testnet=True, poll_interval=0.001)
    monkeypatch.setattr(client, "symbols", ["BTC"])
    monkeypatch.setattr(client, "timeframes", ["1h"])
    assert await client.connect() is True
    exchange.fail_next = True

    task = asyncio.create_task(client.run_polling_loop())
    await asyncio.sleep(0.01)
    assert client.get_status().connected is True
    assert client.get_status().reconnect_count == 1
    await client.disconnect()
    await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_stale_market_data_is_reported_unhealthy(monkeypatch):
    now = datetime.now()
    client = HyperliquidMarketClient(
        exchange=FakePublicExchange(), testnet=True, clock=lambda: now
    )
    monkeypatch.setattr(client, "symbols", ["BTC"])
    monkeypatch.setattr(client, "timeframes", ["1h"])
    assert await client.connect() is True

    now += timedelta(seconds=client.freshness_threshold + 1)

    assert client.get_status().connected is False
    await client.disconnect()
