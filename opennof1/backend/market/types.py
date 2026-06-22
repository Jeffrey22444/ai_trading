"""
Market data type definitions
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from decimal import Decimal


@dataclass
class Kline:
    """Kline data structure"""
    symbol: str
    interval: str
    open_time: int
    close_time: int
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    quote_volume: Decimal
    trades_count: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal
    is_final: bool = False

    @property
    def open_timestamp(self) -> datetime:
        """Return the candle open timestamp."""
        return datetime.fromtimestamp(self.open_time / 1000)

    @property
    def close_timestamp(self) -> datetime:
        """Return the candle close timestamp, falling back to open time if invalid."""
        if self.close_time and self.close_time > 0:
            return datetime.fromtimestamp(self.close_time / 1000)
        return self.open_timestamp
    
    @property
    def timestamp(self) -> datetime:
        """Legacy timestamp: candle open time. Prefer open_timestamp/close_timestamp."""
        return self.open_timestamp


@dataclass
class ConnectionStatus:
    """Connection status"""
    exchange: str
    connected: bool
    last_ping: Optional[datetime] = None
    last_message: Optional[datetime] = None
    reconnect_count: int = 0
    error_message: Optional[str] = None


@dataclass
class SystemStatus:
    """System status"""
    uptime_seconds: int
    memory_usage_mb: float
    active_connections: int
    total_symbols: int
    active_timeframes: int
    last_update: datetime


@dataclass
class TechnicalIndicator:
    """Technical indicator data"""
    symbol: str
    timeframe: str
    indicator_name: str
    timestamp: datetime
    value: float
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MarketSnapshot:
    """Market snapshot for a symbol"""
    symbol: str
    timestamp: datetime
    price: float
    volume_24h: float
    price_change_24h: float
    price_change_percent_24h: float
    high_24h: float
    low_24h: float
    
    # Technical indicators
    indicators: dict[str, TechnicalIndicator] = None
    
    def __post_init__(self):
        if self.indicators is None:
            self.indicators = {}


@dataclass
class DerivativesSnapshot:
    """Derivative market context for one symbol."""

    symbol: str
    timestamp: datetime
    open_interest: Optional[float] = None
    funding_rate: Optional[float] = None
    funding_interval: Optional[str] = None
    funding_timestamp: Optional[datetime] = None
    mark_price: Optional[float] = None
    index_price: Optional[float] = None
    premium: Optional[float] = None
