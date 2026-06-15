import pytest

from scripts.p0_acceptance import validate_decision


def test_acceptance_rejects_parse_failure_fallback():
    with pytest.raises(RuntimeError, match="JSON 解析失败"):
        validate_decision(
            symbol="ETHUSDT",
            decision={"action": "HOLD", "reasoning": "JSON解析失败，采用保守策略"},
            current_price=100.0,
            available_balance=1_000.0,
        )


def test_acceptance_accepts_valid_open_short():
    saw_hold = validate_decision(
        symbol="ETHUSDT",
        decision={
            "action": "OPEN_SHORT",
            "reasoning": "高信心",
            "position_size_usd": 100.0,
            "stop_loss_price": 105.0,
            "take_profit_price": 90.0,
        },
        current_price=100.0,
        available_balance=1_000.0,
    )

    assert saw_hold is False
