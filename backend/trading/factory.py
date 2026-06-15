"""Configured exchange trader selection."""

from typing import Type

from config.settings import config
from trading.interface import ExchangeTrader


def _binance_trader_class() -> Type[ExchangeTrader]:
    from trading.binance_futures import BinanceFuturesTrader

    return BinanceFuturesTrader


def _hyperliquid_trader_class() -> Type[ExchangeTrader]:
    from trading.hyperliquid_trader import HyperliquidTrader

    return HyperliquidTrader


TRADER_CLASSES = {
    "binance_futures": _binance_trader_class,
    "hyperliquid": _hyperliquid_trader_class,
}

_trader_instance: ExchangeTrader | None = None


def get_trader() -> ExchangeTrader:
    """Return the singleton trader selected by exchange.name."""
    global _trader_instance
    if _trader_instance is None:
        provider = TRADER_CLASSES.get(config.exchange.name.lower())
        if provider is None:
            raise ValueError(f"不支持的交易所: {config.exchange.name}")
        _trader_instance = provider()()
    return _trader_instance


def reset_trader() -> None:
    """Reset the singleton after configuration changes or in tests."""
    global _trader_instance
    _trader_instance = None
