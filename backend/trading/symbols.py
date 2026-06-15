"""Translate stable logical symbols to exchange-specific CCXT symbols."""


def from_exchange_symbol(symbol: str) -> str:
    """Return the base asset used by AI, API routes, cache, and storage."""
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("无效交易标的: 空字符串")

    base = normalized.split("/", 1)[0]
    for quote in ("USDT", "USDC", "USD"):
        if base.endswith(quote) and len(base) > len(quote):
            return base[: -len(quote)]
    return base


def to_exchange_symbol(symbol: str, exchange_name: str) -> str:
    """Return the CCXT perpetual symbol for the configured exchange."""
    base = from_exchange_symbol(symbol)
    name = exchange_name.lower()
    if name == "hyperliquid":
        return f"{base}/USDC:USDC"
    raise ValueError(f"当前版本仅支持 Hyperliquid: {exchange_name}")


def same_symbol(left: str, right: str) -> bool:
    """Compare logical or exchange-formatted symbols by base asset."""
    return from_exchange_symbol(left) == from_exchange_symbol(right)
