import pytest

from agent.nodes.trading_execution_node import _decision_leverage
from trading.risk_guard import normalize_position_size_usd, validate_open_decision


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


def test_position_limit_rounding_is_clamped_down_to_safe_cent():
    normalized = normalize_position_size_usd(
        position_size_usd=199.91,
        available_balance=999.542939,
        max_position_size_percent=0.2,
    )

    assert normalized == 199.9


def test_position_limit_rejects_more_than_one_cent_overage():
    with pytest.raises(ValueError, match="开仓金额超过"):
        normalize_position_size_usd(
            position_size_usd=199.92,
            available_balance=999.542939,
            max_position_size_percent=0.2,
        )


def test_execution_uses_decision_level_quant_leverage():
    assert _decision_leverage({"leverage": 3}) == 3


def test_execution_rejects_leverage_above_quant_config():
    with pytest.raises(ValueError, match="杠杆超过配置上限"):
        _decision_leverage({"leverage": 99})
