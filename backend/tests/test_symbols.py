import pytest

from trading.symbols import from_exchange_symbol, to_exchange_symbol


@pytest.mark.parametrize("symbol", ["BTC", "btc", "BTCUSDT", "BTC/USDT:USDT"])
def test_hyperliquid_symbol_mapping_uses_usdc_perpetual(symbol):
    assert to_exchange_symbol(symbol, "hyperliquid") == "BTC/USDC:USDC"


def test_binance_symbol_mapping_keeps_usdt_perpetual():
    assert to_exchange_symbol("BTC", "binance_futures") == "BTC/USDT:USDT"


@pytest.mark.parametrize(
    "symbol",
    ["BTC", "BTCUSDT", "BTC/USDT:USDT", "BTC/USDC:USDC"],
)
def test_exchange_symbols_are_normalized_to_logical_base(symbol):
    assert from_exchange_symbol(symbol) == "BTC"


def test_unknown_symbol_format_is_rejected():
    with pytest.raises(ValueError, match="无效交易标的"):
        from_exchange_symbol("")
