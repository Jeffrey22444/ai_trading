"""Configured exchange trader selection."""

from config.settings import config
from trading.interface import ExchangeTrader


def _hyperliquid_trader_class() -> type[ExchangeTrader]:
    from trading.hyperliquid_trader import HyperliquidTrader

    return HyperliquidTrader


TRADER_CLASSES = {
    "hyperliquid": _hyperliquid_trader_class,
}

_trader_instance: ExchangeTrader | None = None


def get_trader() -> ExchangeTrader:
    """Return the singleton trader selected by exchange.name."""
    global _trader_instance
    if _trader_instance is None:
        if config.exchange.name.lower() != "hyperliquid":
            raise ValueError(f"当前版本仅支持 Hyperliquid: {config.exchange.name}")
        provider = TRADER_CLASSES["hyperliquid"]
        _trader_instance = provider()()
    return _trader_instance


def reset_trader() -> None:
    """Reset the singleton after configuration changes or in tests."""
    global _trader_instance
    _trader_instance = None
