from market.hyperliquid_market import market_data_client
from market.hyperliquid_market import HyperliquidMarketClient


def test_application_uses_hyperliquid_market_data_client():
    assert isinstance(market_data_client, HyperliquidMarketClient)
