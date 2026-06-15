from config.agent_config import ExchangeConfig


def test_binance_testnet_uses_demo_trading_instead_of_deprecated_sandbox():
    exchange = ExchangeConfig(
        name="binance_futures",
        api_key="placeholder",
        api_secret="placeholder",
        testnet=True,
        websocket_url="wss://fstream.binance.com/stream",
        rest_api_url="https://fapi.binance.com",
        testnet_websocket_url="wss://stream.binancefuture.com/stream",
        testnet_rest_api_url="https://testnet.binancefuture.com",
    )

    ccxt_config = exchange.get_ccxt_config()

    assert ccxt_config["options"]["enableDemoTrading"] is True
    assert "sandbox" not in ccxt_config
