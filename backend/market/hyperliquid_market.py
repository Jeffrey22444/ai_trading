"""Hyperliquid public market data and polling lifecycle."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, List

import ccxt

from config.settings import config
from market.data_cache import kline_cache
from market.types import ConnectionStatus, Kline
from trading.symbols import from_exchange_symbol, to_exchange_symbol

logger = logging.getLogger("AlphaTransformer")


class HyperliquidMarketClient:
    """Fetch Hyperliquid testnet OHLCV and keep the shared cache current."""

    def __init__(
        self,
        exchange=None,
        testnet: bool | None = None,
        poll_interval=30,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.testnet = config.exchange.testnet if testnet is None else testnet
        self.exchange = exchange or ccxt.hyperliquid(
            {"enableRateLimit": True, "options": {"defaultType": "swap"}}
        )
        self.exchange.set_sandbox_mode(self.testnet)
        self.poll_interval = poll_interval
        self.clock = clock
        self.freshness_threshold = max(poll_interval * 3, 90)
        self.symbols = config.agent.symbols
        self.timeframes = config.agent.timeframes
        self.is_connected = False
        self.connection_status = ConnectionStatus(
            exchange="hyperliquid-testnet" if self.testnet else "hyperliquid",
            connected=False,
        )

    async def get_klines(
        self, symbol: str, interval: str, limit: int = 100
    ) -> List[Kline]:
        exchange_symbol = to_exchange_symbol(symbol, "hyperliquid")
        rows = await asyncio.to_thread(
            self.exchange.fetch_ohlcv, exchange_symbol, interval, limit=limit
        )
        duration_ms = self.exchange.parse_timeframe(interval) * 1000
        now_ms = int(self.clock().timestamp() * 1000)
        logical_symbol = from_exchange_symbol(symbol)
        return [
            Kline(
                symbol=logical_symbol,
                interval=interval,
                open_time=row[0],
                close_time=row[0] + duration_ms - 1,
                open_price=float(row[1]),
                high_price=float(row[2]),
                low_price=float(row[3]),
                close_price=float(row[4]),
                volume=float(row[5]),
                quote_volume=0.0,
                trades_count=0,
                taker_buy_base_volume=0.0,
                taker_buy_quote_volume=0.0,
                is_final=row[0] + duration_ms <= now_ms,
            )
            for row in rows
        ]

    async def refresh_once(self, limit: int = 100) -> None:
        requests = [
            self.get_klines(symbol, timeframe, limit)
            for symbol in self.symbols
            for timeframe in self.timeframes
        ]
        for klines in await asyncio.gather(*requests):
            for kline in klines:
                await kline_cache.add_kline(kline)
        self.connection_status.connected = True
        self.connection_status.error_message = None
        self.connection_status.last_message = self.clock()

    async def initialize_historical_data(self) -> None:
        await self.refresh_once(limit=100)

    async def connect(self) -> bool:
        try:
            await self.refresh_once(limit=2)
            self.is_connected = True
            self.connection_status.connected = True
            self.connection_status.error_message = None
            return True
        except Exception as exc:
            logger.error("Hyperliquid 行情轮询连接失败: %s", exc)
            self.connection_status.connected = False
            self.connection_status.error_message = str(exc)
            return False

    async def run_polling_loop(self) -> None:
        """Refresh configured Hyperliquid markets until disconnected."""
        while self.is_connected:
            try:
                await asyncio.sleep(self.poll_interval)
                if self.is_connected:
                    await self.refresh_once(limit=2)
            except Exception as exc:
                logger.error("Hyperliquid 行情轮询失败: %s", exc)
                self.connection_status.error_message = str(exc)
                self.connection_status.reconnect_count += 1

    async def disconnect(self) -> None:
        self.is_connected = False
        self.connection_status.connected = False

    async def close(self) -> None:
        await self.disconnect()

    def get_status(self) -> ConnectionStatus:
        last_message = self.connection_status.last_message
        self.connection_status.connected = bool(
            self.is_connected
            and last_message
            and self.clock() - last_message
            <= timedelta(seconds=self.freshness_threshold)
        )
        return self.connection_status
