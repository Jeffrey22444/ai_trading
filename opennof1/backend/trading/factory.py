"""Configured exchange trader selection."""

from config.settings import config
from trading.hyperliquid_trader import HyperliquidTrader


_trader_instance: HyperliquidTrader | None = None


def get_trader() -> HyperliquidTrader:
    """Return the singleton trader selected by exchange.name."""
    global _trader_instance
    if _trader_instance is None:
        if config.exchange.name.lower() != "hyperliquid":
            raise ValueError(f"当前版本仅支持 Hyperliquid: {config.exchange.name}")
        _trader_instance = HyperliquidTrader()
    return _trader_instance


def reset_trader() -> None:
    """Reset the singleton after configuration changes or in tests."""
    global _trader_instance
    _trader_instance = None
