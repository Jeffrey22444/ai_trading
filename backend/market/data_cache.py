"""
Kline data cache module
"""
from collections import deque
from threading import RLock
from typing import Dict, List, Optional, Deque

from market.types import Kline
from config.settings import config


class KlineCache:
    """Kline data cache"""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Deque[Kline]]] = {}
        self.lock = RLock()
        self.max_klines = 100  # 默认值，可以从配置文件中读取
        
        # Initialize cache structure
        self._initialize_cache()
    
    def _initialize_cache(self):
        """Initialize cache structure"""
        symbols = config.agent.symbols
        timeframes = config.agent.timeframes
        
        for symbol in symbols:
            self.cache[symbol] = {}
            for timeframe in timeframes:
                self.cache[symbol][timeframe] = deque(maxlen=self.max_klines)
    
    async def add_kline(self, kline: Kline) -> None:
        """Add kline data"""
        with self.lock:
            if kline.symbol not in self.cache:
                self.cache[kline.symbol] = {}
                for timeframe in config.agent.timeframes:
                    self.cache[kline.symbol][timeframe] = deque(maxlen=self.max_klines)
            
            if kline.interval not in self.cache[kline.symbol]:
                self.cache[kline.symbol][kline.interval] = deque(maxlen=self.max_klines)
            
            kline_deque = self.cache[kline.symbol][kline.interval]
            
            # Check if this is updating current kline or adding new kline
            if kline_deque and kline_deque[-1].open_time == kline.open_time:
                # Update current kline
                kline_deque[-1] = kline
            else:
                # Add new kline
                kline_deque.append(kline)
    
    async def get_klines(self, symbol: str, timeframe: str, limit: Optional[int] = None) -> List[Kline]:
        """Get kline data"""
        return self.get_klines_snapshot(symbol, timeframe, limit)

    def get_klines_snapshot(
        self, symbol: str, timeframe: str, limit: Optional[int] = None
    ) -> List[Kline]:
        """Get a thread-safe K-line snapshot for synchronous analysis tools."""
        with self.lock:
            if symbol not in self.cache or timeframe not in self.cache[symbol]:
                return []
            
            klines = list(self.cache[symbol][timeframe])
            
            if limit and limit > 0:
                klines = klines[-limit:]
            
            return klines
    
    async def get_latest_kline(self, symbol: str, timeframe: str) -> Optional[Kline]:
        """Get latest kline"""
        with self.lock:
            if symbol not in self.cache or timeframe not in self.cache[symbol]:
                return None
            
            kline_deque = self.cache[symbol][timeframe]
            return kline_deque[-1] if kline_deque else None
    
    async def get_cache_info(self) -> Dict:
        """Get cache information"""
        with self.lock:
            info = {
                "total_symbols": len(self.cache),
                "max_klines_per_timeframe": self.max_klines,
                "symbol_details": {}
            }
            
            for symbol, timeframes in self.cache.items():
                symbol_info = {}
                total_klines = 0
                
                for timeframe, kline_deque in timeframes.items():
                    count = len(kline_deque)
                    symbol_info[timeframe] = count
                    total_klines += count
                
                symbol_info["total_klines"] = total_klines
                info["symbol_details"][symbol] = symbol_info
            
            return info


# Global cache instance
kline_cache = KlineCache()
