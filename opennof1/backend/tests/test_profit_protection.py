from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.nodes import exit_decision_node as exit_node
from agent.nodes.exit_decision_node import exit_decision_node
from agent.portfolio.position_manager import (
    PROFIT_DRAWDOWN,
    PROFIT_PEAK,
    reset_position_states,
    update_position_state,
)


def _position(profit_pct: float, side: str = "LONG"):
    return SimpleNamespace(
        symbol="BTC",
        side=side,
        size=0.01,
        entry_price=100.0,
        mark_price=101.0,
        unrealized_pnl=profit_pct,
        percentage_pnl=profit_pct,
        leverage=1,
        margin=100.0,
        timestamp=datetime.now(),
    )


@pytest.fixture(autouse=True)
def clean_position_state():
    reset_position_states()


def test_profit_above_one_percent_sets_trailing_stop():
    state = update_position_state(_position(1.2))

    assert state.regime == PROFIT_PEAK
    assert state.trailing_stop == pytest.approx(0.9)
    assert state.should_exit is False


def test_profit_drawdown_over_trailing_stop_exits():
    update_position_state(_position(1.4), datetime.now())

    state = update_position_state(_position(1.0), datetime.now() + timedelta(seconds=30))

    assert state.regime == PROFIT_DRAWDOWN
    assert state.drawdown_from_peak_pct == pytest.approx(0.4)
    assert state.should_exit is True


def test_break_even_stop_loss_is_entry_price_after_half_percent_profit():
    state = update_position_state(_position(0.5))

    assert state.stop_loss == 100.0


@pytest.mark.asyncio
async def test_exit_ai_does_not_override_trailing_stop(monkeypatch):
    update_position_state(_position(1.5))
    trader = SimpleNamespace(get_positions=AsyncMock(return_value=[_position(1.1)]))
    monkeypatch.setattr(exit_node, "get_trader", lambda: trader)
    state = {
        "symbol_decisions": {
            "BTC": {
                "action": "POSITION_HOLD",
                "reasoning": "Exit AI wants to wait.",
                "execution_status": "pending",
                "execution_result": None,
            }
        },
        "overall_summary": None,
        "error": None,
    }

    result = await exit_decision_node(state)

    assert result["symbol_decisions"]["BTC"]["action"] == "CLOSE_LONG"
    assert "利润保护触发" in result["symbol_decisions"]["BTC"]["reasoning"]


@pytest.mark.asyncio
async def test_entry_ai_does_not_manage_existing_position(monkeypatch):
    trader = SimpleNamespace(get_positions=AsyncMock(return_value=[_position(0.2)]))
    monkeypatch.setattr(exit_node, "get_trader", lambda: trader)
    state = {
        "symbol_decisions": {
            "BTC": {
                "action": "OPEN_LONG",
                "reasoning": "Entry AI still sees an entry.",
                "execution_status": "pending",
                "execution_result": None,
            }
        },
        "overall_summary": None,
        "error": None,
    }

    result = await exit_decision_node(state)

    assert result["symbol_decisions"]["BTC"]["action"] == "POSITION_HOLD"


@pytest.mark.asyncio
async def test_hold_semantics_are_split(monkeypatch):
    trader = SimpleNamespace(get_positions=AsyncMock(return_value=[_position(0.2)]))
    monkeypatch.setattr(exit_node, "get_trader", lambda: trader)
    state = {
        "symbol_decisions": {
            "BTC": {
                "action": "HOLD",
                "reasoning": "Legacy hold.",
                "execution_status": "pending",
                "execution_result": None,
            },
            "ETH": {
                "action": "HOLD",
                "reasoning": "Legacy hold.",
                "execution_status": "pending",
                "execution_result": None,
            },
        },
        "overall_summary": None,
        "error": None,
    }

    result = await exit_decision_node(state)

    assert result["symbol_decisions"]["BTC"]["action"] == "POSITION_HOLD"
    assert result["symbol_decisions"]["ETH"]["action"] == "ENTRY_HOLD"
