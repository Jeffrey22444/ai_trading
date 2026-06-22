import pytest

from config.agent_config import ExchangeConfig


def test_non_hyperliquid_exchange_is_rejected():
    with pytest.raises(ValueError, match="仅支持 Hyperliquid"):
        ExchangeConfig(name="another_exchange")


def test_hyperliquid_config_uses_only_wallet_credentials():
    exchange = ExchangeConfig(
        name="hyperliquid",
        wallet_address="0xwallet",
        private_key="0xprivate",
        testnet=True,
    )

    ccxt_config = exchange.get_ccxt_config()

    assert ccxt_config["walletAddress"] == "0xwallet"
    assert ccxt_config["privateKey"] == "0xprivate"
    assert "apiKey" not in ccxt_config
    assert "secret" not in ccxt_config


def test_hyperliquid_required_credentials_are_reported_by_name():
    exchange = ExchangeConfig(name="hyperliquid", testnet=True)

    assert exchange.missing_credential_env_vars() == [
        "HYPERLIQUID_WALLET_ADDRESS",
        "HYPERLIQUID_PRIVATE_KEY",
    ]


def test_placeholder_credentials_are_not_treated_as_configured():
    exchange = ExchangeConfig(
        name="hyperliquid",
        wallet_address="your_hyperliquid_testnet_wallet_address_here",
        private_key="your_hyperliquid_testnet_private_key_here",
    )

    assert exchange.missing_credential_env_vars() == [
        "HYPERLIQUID_WALLET_ADDRESS",
        "HYPERLIQUID_PRIVATE_KEY",
    ]
