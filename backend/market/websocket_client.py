"""
WebSocket client module
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Callable, Optional
import websockets

from market.types import Kline, ConnectionStatus
from market.data_cache import kline_cache
from config.settings import config

logger = logging.getLogger("AlphaTransformer")


class BinanceWebSocketClient:
    """Binance WebSocket client"""
    
    def __init__(self):
        self.ws_url = config.exchange.get_websocket_url()
        self.connection: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.is_reconnecting = False
        self.reconnect_count = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 3  # seconds
        
        # Connection status
        self.connection_status = ConnectionStatus(
            exchange="binance",
            connected=False
        )
        
        # Subscription management
        self.subscriptions: Dict[str, List[str]] = {}  # {symbol: [timeframes]}
        
        # Message processing callbacks
        self.message_handlers: List[Callable] = []
    
    async def connect(self) -> bool:
        """Connect WebSocket"""
        try:
            logger.info(f"Connecting to combined stream: {self.ws_url}")
            
            self.connection = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_connected = True
            self.connection_status.connected = True
            self.connection_status.last_message = datetime.now()
            self.reconnect_count = 0
            
            logger.info("WebSocket connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.connection_status.connected = False
            self.connection_status.error_message = str(e)
            return False
    
    async def disconnect(self):
        """Disconnect"""
        self.is_connected = False
        self.is_reconnecting = False
        
        if self.connection:
            await self.connection.close()
            self.connection = None
        
        self.connection_status.connected = False
        logger.info("WebSocket disconnected")
    
    async def subscribe_klines(self, symbol: str, timeframes: List[str]) -> bool:
        """Subscribe kline data"""
        if not self.is_connected:
            logger.error("WebSocket not connected, cannot subscribe")
            return False
        
        # Record subscription
        self.subscriptions[symbol] = timeframes
        
        # Batch subscription
        streams = []
        for tf in timeframes:
            stream = f"{symbol.lower()}@kline_{tf}"
            streams.append(stream)
        
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": int(datetime.now().timestamp() * 1000)
        }
        
        try:
            await self.connection.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed {symbol} kline streams: {streams}")
            return True
            
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            return False
    
    async def subscribe_all(self):
        """Subscribe all configured symbols and timeframes"""
        logger.info("Starting to subscribe all symbols...")
        
        symbols = config.agent.symbols
        timeframes = config.agent.timeframes
        
        for symbol in symbols:
            success = await self.subscribe_klines(symbol, timeframes)
            if not success:
                logger.error(f"Failed to subscribe {symbol}")
            else:
                # Delay between batches to avoid rate limiting
                await asyncio.sleep(0.1)
        
        logger.info("All symbols subscription completed")
    
    async def start_message_loop(self):
        """Start message loop"""
        while self.is_connected or self.is_reconnecting:
            try:
                if not self.connection:
                    await asyncio.sleep(1)
                    continue
                
                # Receive message
                message = await self.connection.recv()
                self.connection_status.last_message = datetime.now()
                
                # Process message
                await self._handle_message(message)
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                break
        
        # Try to reconnect
        if self.is_connected and not self.is_reconnecting:
            await self._handle_reconnect()
    
    async def _handle_message(self, message: str):
        """Handle WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle kline data - combined stream format
            if "stream" in data and "data" in data:
                await self._handle_kline_data(data)
            
            # Handle subscription confirmation
            elif "result" in data:
                logger.debug(f"Subscription confirmation: {data}")
            
            # Handle error
            elif "error" in data:
                logger.error(f"WebSocket error: {data['error']}")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            logger.error(f"Message processing exception: {e}")
    
    async def _handle_kline_data(self, data: dict):
        """Handle kline data"""
        try:
            kline_data = data["data"]
            symbol = kline_data["s"]
            interval = kline_data["k"]["i"]
            
            # Create kline object
            kline = Kline(
                symbol=symbol,
                interval=interval,
                open_time=kline_data["k"]["t"],
                close_time=kline_data["k"]["T"],
                open_price=float(kline_data["k"]["o"]),
                high_price=float(kline_data["k"]["h"]),
                low_price=float(kline_data["k"]["l"]),
                close_price=float(kline_data["k"]["c"]),
                volume=float(kline_data["k"]["v"]),
                quote_volume=float(kline_data["k"]["q"]),
                trades_count=kline_data["k"]["n"],
                taker_buy_base_volume=float(kline_data["k"]["V"]),
                taker_buy_quote_volume=float(kline_data["k"]["Q"]),
                is_final=kline_data["k"]["x"]
            )
            
            # Add to cache
            await kline_cache.add_kline(kline)
            
            # Call message handlers
            for handler in self.message_handlers:
                try:
                    await handler(kline)
                except Exception as e:
                    logger.error(f"Message handler error: {e}")
            
            # Only log when kline is complete
            if kline.is_final:
                logger.debug(f"Received {symbol} {interval} complete kline: {kline.close_price}")
        
        except Exception as e:
            logger.error(f"Kline data processing error: {e}")
    
    async def _handle_reconnect(self):
        """Handle reconnection"""
        if self.is_reconnecting:
            return
        
        self.is_reconnecting = True
        self.reconnect_count += 1
        
        if self.reconnect_count > self.max_reconnect_attempts:
            logger.error(f"Reconnection failed, max attempts reached {self.max_reconnect_attempts}")
            self.is_connected = False
            self.is_reconnecting = False
            return
        
        logger.info(f"Attempting to reconnect (attempt {self.reconnect_count})")
        
        # Disconnect old connection
        await self.disconnect()
        
        # Wait for reconnection delay
        await asyncio.sleep(self.reconnect_delay)
        
        # Try to reconnect
        if await self.connect():
            # Resubscribe
            await self.subscribe_all()
            
            # Restart message loop
            asyncio.create_task(self.start_message_loop())
        
        self.is_reconnecting = False
    
    def get_status(self) -> ConnectionStatus:
        """Get connection status"""
        self.connection_status.reconnect_count = self.reconnect_count
        return self.connection_status
    
    def add_message_handler(self, handler: Callable):
        """Add message handler"""
        self.message_handlers.append(handler)


# Hyperliquid P0 uses a polling lifecycle with the same public interface.
if config.exchange.name.lower() == "hyperliquid":
    from market.api_client import api_client

    ws_client = api_client
else:
    ws_client = BinanceWebSocketClient()
