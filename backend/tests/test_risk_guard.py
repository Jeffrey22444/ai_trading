from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.nodes.trading_execution_node import (
    _decision_leverage,
    _execute_open_long,
    _execute_open_short,
    _mark_confirmed_closed,
)
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


def test_open_long_rejects_directional_chase_above_reference_price():
    with pytest.raises(ValueError, match="追价保护"):
        validate_open_decision(
            action="OPEN_LONG",
            position_size_usd=100.0,
            current_price=100.2,
            reference_price=100.0,
            max_entry_price_drift_pct=0.1,
            max_chase_price_drift_pct=0.0015,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            available_balance=1_000.0,
            max_position_size_percent=0.2,
            testnet=True,
            allow_live_trading=False,
        )


def test_open_short_rejects_directional_chase_below_reference_price():
    with pytest.raises(ValueError, match="追价保护"):
        validate_open_decision(
            action="OPEN_SHORT",
            position_size_usd=100.0,
            current_price=99.8,
            reference_price=100.0,
            max_entry_price_drift_pct=0.1,
            max_chase_price_drift_pct=0.0015,
            stop_loss_price=105.0,
            take_profit_price=90.0,
            available_balance=1_000.0,
            max_position_size_percent=0.2,
            testnet=True,
            allow_live_trading=False,
        )


def test_open_rejects_absolute_drift_above_threshold():
    with pytest.raises(ValueError, match="偏离过大"):
        validate_open_decision(
            action="OPEN_LONG",
            position_size_usd=100.0,
            current_price=100.31,
            reference_price=100.0,
            max_entry_price_drift_pct=0.003,
            max_chase_price_drift_pct=0.1,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            available_balance=1_000.0,
            max_position_size_percent=0.2,
            testnet=True,
            allow_live_trading=False,
        )


def test_open_allows_price_drift_inside_thresholds():
    normalized = validate_open_decision(
        action="OPEN_LONG",
        position_size_usd=100.0,
        current_price=100.1,
        reference_price=100.0,
        max_entry_price_drift_pct=0.003,
        max_chase_price_drift_pct=0.0015,
        stop_loss_price=95.0,
        take_profit_price=110.0,
        available_balance=1_000.0,
        max_position_size_percent=0.2,
        testnet=True,
        allow_live_trading=False,
    )

    assert normalized == 100.0


def test_open_rejects_invalid_reference_price():
    with pytest.raises(ValueError, match="参考价格"):
        validate_open_decision(
            action="OPEN_LONG",
            position_size_usd=100.0,
            current_price=100.0,
            reference_price=0.0,
            max_entry_price_drift_pct=0.003,
            max_chase_price_drift_pct=0.0015,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            available_balance=1_000.0,
            max_position_size_percent=0.2,
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


@pytest.mark.asyncio
async def test_execution_blocks_long_drift_without_calling_trader():
    trader = SimpleNamespace(open_long=AsyncMock())
    balance = SimpleNamespace(available_balance=1_000.0)
    decision = {
        "position_size_usd": 100.0,
        "stop_loss_price": 95.0,
        "take_profit_price": 110.0,
        "leverage": 1,
        "quant_guardrail": {"reference_price": 100.0},
    }

    result = await _execute_open_long(
        "BTC", decision, trader, current_price=101.0, balance=balance
    )

    assert result["status"] == "blocked"
    assert result["reject_reason"]
    assert result["reference_price"] == 100.0
    assert result["current_price"] == 101.0
    assert result["drift_pct"] == 0.01
    trader.open_long.assert_not_called()


@pytest.mark.asyncio
async def test_execution_blocks_short_drift_without_calling_trader():
    trader = SimpleNamespace(open_short=AsyncMock())
    balance = SimpleNamespace(available_balance=1_000.0)
    decision = {
        "position_size_usd": 100.0,
        "stop_loss_price": 105.0,
        "take_profit_price": 90.0,
        "leverage": 1,
        "quant_guardrail": {"reference_price": 100.0},
    }

    result = await _execute_open_short(
        "BTC", decision, trader, current_price=99.0, balance=balance
    )

    assert result["status"] == "blocked"
    assert result["reject_reason"]
    assert result["reference_price"] == 100.0
    assert result["current_price"] == 99.0
    assert result["drift_pct"] == 0.01
    trader.open_short.assert_not_called()


@pytest.mark.asyncio
async def test_execution_result_exposes_post_fill_protection_status():
    trader = SimpleNamespace(
        open_long=AsyncMock(
            return_value={
                "protection_verified": True,
                "protection_orders": [{"id": "sl"}, {"id": "tp"}],
            }
        )
    )
    balance = SimpleNamespace(available_balance=1_000.0)
    decision = {
        "position_size_usd": 100.0,
        "stop_loss_price": 95.0,
        "take_profit_price": 110.0,
        "leverage": 1,
        "quant_guardrail": {"reference_price": 100.0},
    }

    result = await _execute_open_long(
        "BTC", decision, trader, current_price=100.0, balance=balance
    )

    assert result["status"] == "success"
    assert result["protection_verified"] is True
    assert result["protection_order_count"] == 2
    assert result["position_state"]["state"] == "ACTIVE"
    assert result["position_state"]["capital_released"] is False


def test_capital_releases_only_after_exchange_confirms_flat():
    decision = {
        "execution_status": "completed",
        "execution_result": {"status": "success"},
    }

    _mark_confirmed_closed({"BTC": decision}, positions=[])

    assert decision["execution_result"]["position_state"]["state"] == "CLOSED"
    assert decision["execution_result"]["position_state"]["capital_released"] is True
