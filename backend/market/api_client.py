"""
REST API client module
Used for getting historical data and initialization
"""
import logging
from typing import List, Optional
import httpx

from market.types import Kline
from config.settings import config

logger = logging.getLogger("AlphaTransformer")


class BinanceAPIClient:
    """Binance REST API client"""
    
    def __init__(self):
        self.base_url = config.exchange.get_rest_api_url()
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[Kline]:
        """Get kline data"""
        url = f"{self.base_url}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            klines = []
            
            for item in data:
                kline = Kline(
                    symbol=symbol,
                    interval=interval,
                    open_time=item[0],
                    close_time=item[6],
                    open_price=float(item[1]),
                    high_price=float(item[2]),
                    low_price=float(item[3]),
                    close_price=float(item[4]),
                    volume=float(item[5]),
                    quote_volume=float(item[7]),
                    trades_count=item[8],
                    taker_buy_base_volume=float(item[9]),
                    taker_buy_quote_volume=float(item[10]),
                    is_final=True
                )
                klines.append(kline)
            
            logger.info(f"Got {symbol} {interval} historical klines {len(klines)} items")
            return klines
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get {symbol} {interval} historical data: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to parse {symbol} {interval} historical data: {e}")
            return []
    
    async def initialize_historical_data(self):
        """Initialize historical data"""
        logger.info("Starting historical data initialization...")
        
        symbols = config.agent.symbols
        timeframes = config.agent.timeframes
        
        for symbol in symbols:
            for timeframe in timeframes:
                klines = await self.get_klines(symbol, timeframe, 100)
                
                # Add historical data to cache
                from market.data_cache import kline_cache
                for kline in klines:
                    await kline_cache.add_kline(kline)
                
                logger.info(f"Initialized {symbol} {timeframe} with {len(klines)} historical klines")
        
        logger.info("Historical data initialization completed")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global instance selected by exchange configuration.
if config.exchange.name.lower() == "hyperliquid":
    from market.hyperliquid_market import HyperliquidMarketClient

    api_client = HyperliquidMarketClient()
else:
    api_client = BinanceAPIClient()
