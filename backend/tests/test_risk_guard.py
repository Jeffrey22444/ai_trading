import pytest

from trading.risk_guard import validate_open_decision


def test_live_opening_requires_explicit_opt_in():
    with pytest.raises(ValueError, match="实盘开仓已禁用"):
        validate_open_decision(
            action="OPEN_LONG",
            position_size_usd=100.0,
            current_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            available_balance=1_000.0,
            max_position_size_percent=0.1,
            testnet=False,
            allow_live_trading=False,
        )


def test_testnet_opening_enforces_position_limit():
    with pytest.raises(ValueError, match="开仓金额超过"):
        validate_open_decision(
            action="OPEN_LONG",
            position_size_usd=101.0,
            current_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            available_balance=1_000.0,
            max_position_size_percent=0.1,
            testnet=True,
            allow_live_trading=False,
        )


def test_testnet_opening_requires_valid_long_exit_prices():
    with pytest.raises(ValueError, match="多头止损止盈方向无效"):
        validate_open_decision(
            action="OPEN_LONG",
            position_size_usd=100.0,
            current_price=100.0,
            stop_loss_price=105.0,
            take_profit_price=110.0,
            available_balance=1_000.0,
            max_position_size_percent=0.1,
            testnet=True,
            allow_live_trading=False,
        )


def test_valid_testnet_opening_is_accepted():
    validate_open_decision(
        action="OPEN_SHORT",
        position_size_usd=100.0,
        current_price=100.0,
        stop_loss_price=105.0,
        take_profit_price=90.0,
        available_balance=1_000.0,
        max_position_size_percent=0.1,
        testnet=True,
        allow_live_trading=False,
    )
