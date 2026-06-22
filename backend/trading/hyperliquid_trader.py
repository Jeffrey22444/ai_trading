"""Hyperliquid perpetual trader implemented through CCXT."""

import logging
from datetime import datetime
from typing import List

import ccxt

from config.settings import config
from trading.interface import Balance, Position
from trading.symbols import from_exchange_symbol, to_exchange_symbol

logger = logging.getLogger("AlphaTransformer")


class HyperliquidTrader:
    """Hyperliquid USDC perpetual trader with testnet-first safety."""

    def __init__(self, exchange=None, testnet: bool | None = None):
        self.testnet = config.exchange.testnet if testnet is None else testnet
        self.exchange = exchange or ccxt.hyperliquid(config.exchange.get_ccxt_config())
        self.exchange.set_sandbox_mode(self.testnet)
        if not self.testnet and not config.exchange.allow_live_trading:
            raise ValueError("Hyperliquid 实盘交易未显式启用")
        self.exchange.load_markets()

    def _symbol(self, symbol: str) -> str:
        return to_exchange_symbol(symbol, "hyperliquid")

    @staticmethod
    def _ensure_order_accepted(order, description: str):
        if not order or order.get("status") == "rejected":
            raise RuntimeError(f"Hyperliquid {description}被拒绝")
        return order

    async def get_balance(self) -> Balance:
        balance = self.exchange.fetch_balance()
        usdc = balance.get("USDC", {})
        positions = await self.get_positions()
        unrealized_pnl = sum(position.unrealized_pnl for position in positions)
        total = float(usdc.get("total") or 0)
        return Balance(
            total_balance=total,
            available_balance=float(usdc.get("free") or 0),
            margin_balance=total + unrealized_pnl,
            unrealized_pnl=unrealized_pnl,
            currency="USDC",
            timestamp=datetime.now(),
        )

    async def get_positions(self) -> List[Position]:
        active_positions = []
        for raw in self.exchange.fetch_positions():
            contracts = float(raw.get("contracts") or 0)
            if contracts <= 0:
                continue
            leverage = raw.get("leverage") or 1
            if isinstance(leverage, dict):
                leverage = leverage.get("value") or 1
            active_positions.append(
                Position(
                    symbol=from_exchange_symbol(raw["symbol"]),
                    side=str(raw.get("side") or "").upper(),
                    size=contracts,
                    entry_price=float(raw.get("entryPrice") or 0),
                    mark_price=float(raw.get("markPrice") or 0),
                    unrealized_pnl=float(raw.get("unrealizedPnl") or 0),
                    percentage_pnl=float(raw.get("percentage") or 0),
                    leverage=float(leverage),
                    margin=float(raw.get("initialMargin") or 0),
                    timestamp=(
                        datetime.fromtimestamp(raw["timestamp"] / 1000)
                        if raw.get("timestamp")
                        else datetime.now()
                    ),
                )
            )
        return active_positions

    async def _open(
        self,
        symbol: str,
        quantity: float,
        leverage: int,
        side: str,
        stop_loss_price: float | None,
        take_profit_price: float | None,
    ):
        if stop_loss_price is None or take_profit_price is None:
            raise ValueError("Hyperliquid 开仓必须同时设置止损价和止盈价")
        exchange_symbol = self._symbol(symbol)
        current_price = await self.get_market_price(symbol)
        if side == "buy" and not stop_loss_price < current_price < take_profit_price:
            raise ValueError("Hyperliquid 多头止损止盈方向无效")
        if side == "sell" and not take_profit_price < current_price < stop_loss_price:
            raise ValueError("Hyperliquid 空头止损止盈方向无效")
        if not await self.set_leverage(symbol, leverage):
            raise RuntimeError(f"无法设置 {symbol} 杠杆")
        opening = self._ensure_order_accepted(
            self.exchange.create_order(
                exchange_symbol, "market", side, quantity, current_price, {}
            ),
            "开仓订单",
        )
        filled = opening.get("filled")
        if filled is not None:
            filled = float(filled)
            if filled <= 0:
                raise RuntimeError("Hyperliquid 开仓订单未成交")
            protection_quantity = filled
        else:
            protection_quantity = quantity
        close_side = "sell" if side == "buy" else "buy"
        try:
            if stop_loss_price is not None:
                self._ensure_order_accepted(
                    self.exchange.create_order(
                        exchange_symbol,
                        "market",
                        close_side,
                        protection_quantity,
                        stop_loss_price,
                        {"stopLossPrice": stop_loss_price, "reduceOnly": True},
                    ),
                    "止损保护单",
                )
            if take_profit_price is not None:
                self._ensure_order_accepted(
                    self.exchange.create_order(
                        exchange_symbol,
                        "market",
                        close_side,
                        protection_quantity,
                        take_profit_price,
                        {"takeProfitPrice": take_profit_price, "reduceOnly": True},
                    ),
                    "止盈保护单",
                )
        except Exception as exc:
            logger.error("Hyperliquid 保护单失败，正在立即减仓平仓")
            try:
                latest_price = await self.get_market_price(symbol)
                self.exchange.create_order(
                    exchange_symbol,
                    "market",
                    close_side,
                    protection_quantity,
                    latest_price,
                    {"reduceOnly": True},
                )
            except Exception:
                logger.exception("保护单失败后的紧急平仓也失败")
            raise RuntimeError("Hyperliquid 保护单失败，已尝试立即平仓") from exc
        return opening

    async def open_long(
        self,
        symbol: str,
        quantity: float,
        leverage: int = 1,
        stop_loss_price: float = None,
        take_profit_price: float = None,
    ):
        return await self._open(
            symbol, quantity, leverage, "buy", stop_loss_price, take_profit_price
        )

    async def open_short(
        self,
        symbol: str,
        quantity: float,
        leverage: int = 1,
        stop_loss_price: float = None,
        take_profit_price: float = None,
    ):
        return await self._open(
            symbol, quantity, leverage, "sell", stop_loss_price, take_profit_price
        )

    async def _close(self, symbol: str, quantity: float, side: str, expected_side: str):
        position = next(
            (
                item
                for item in await self.get_positions()
                if item.symbol == from_exchange_symbol(symbol)
                and item.side == expected_side
            ),
            None,
        )
        if position is None:
            raise ValueError(f"没有找到 {symbol} 的{expected_side}持仓")
        if quantity == 0:
            quantity = position.size
        if quantity > position.size:
            raise ValueError(f"平仓数量 {quantity} 超过持仓数量 {position.size}")
        await self.cancel_all_orders(symbol)
        price = await self.get_market_price(symbol)
        return self._ensure_order_accepted(
            self.exchange.create_order(
                self._symbol(symbol),
                "market",
                side,
                quantity,
                price,
                {"reduceOnly": True},
            ),
            "平仓订单",
        )

    async def close_long(self, symbol: str, quantity: float = 0):
        return await self._close(symbol, quantity, "sell", "LONG")

    async def close_short(self, symbol: str, quantity: float = 0):
        return await self._close(symbol, quantity, "buy", "SHORT")

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        try:
            self.exchange.set_leverage(
                leverage,
                self._symbol(symbol),
                {"marginMode": config.exchange.margin_mode},
            )
            return True
        except Exception:
            logger.exception("设置 Hyperliquid 杠杆失败: %s", symbol)
            return False

    async def set_margin_mode(self, symbol: str, is_cross_margin: bool) -> bool:
        try:
            mode = "cross" if is_cross_margin else "isolated"
            self.exchange.set_margin_mode(
                mode,
                self._symbol(symbol),
                {"leverage": config.exchange.default_leverage},
            )
            return True
        except Exception:
            logger.exception("设置 Hyperliquid 保证金模式失败: %s", symbol)
            return False

    async def get_market_price(self, symbol: str) -> float:
        ticker = self.exchange.fetch_ticker(self._symbol(symbol))
        return float(ticker["last"])

    async def cancel_all_orders(self, symbol: str) -> bool:
        exchange_symbol = self._symbol(symbol)
        try:
            for order in self.exchange.fetch_open_orders(exchange_symbol):
                self.exchange.cancel_order(order["id"], exchange_symbol)
            return True
        except Exception:
            logger.exception("取消 Hyperliquid 挂单失败: %s", symbol)
            return False

    def format_quantity(self, symbol: str, quantity: float) -> str:
        return self.exchange.amount_to_precision(self._symbol(symbol), quantity)

    def get_exchange_name(self) -> str:
        return "hyperliquid"
