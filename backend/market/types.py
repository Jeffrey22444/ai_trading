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
    def timestamp(self) -> datetime:
        """Return timestamp"""
        return datetime.fromtimestamp(self.open_time / 1000)


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
