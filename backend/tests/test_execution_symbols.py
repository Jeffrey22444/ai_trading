from trading.symbols import same_symbol


def test_logical_and_hyperliquid_symbols_match():
    assert same_symbol("BTC", "BTC/USDC:USDC")


def test_different_assets_do_not_match():
    assert not same_symbol("BTC", "ETH/USDC:USDC")
