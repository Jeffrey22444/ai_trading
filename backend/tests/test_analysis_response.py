from datetime import datetime

from agent.nodes.analysis_node import (
    SymbolDecision,
    _apply_quant_guardrail,
    parse_json_response,
)
from agent.quant.models import (
    DirectionScore,
    PositionSizingResult,
    QuantGuardrail,
    ScoreResult,
    StopResult,
    StopSide,
)
from trading.interface import Position


def test_hold_decision_accepts_null_optional_trade_fields():
    decision = parse_json_response(
        """
        {
          "symbol_decisions": [
            {
              "symbol": "BTC",
              "action": "HOLD",
              "reasoning": "Signals conflict, wait.",
              "position_size_usd": null,
              "stop_loss_price": null,
              "take_profit_price": null
            }
          ],
          "overall_summary": "Wait for confirmation."
        }
        """
    )

    btc = decision.symbol_decisions[0]
    assert btc.action == "HOLD"
    assert btc.reasoning == "Signals conflict, wait."
    assert btc.position_size_usd == 0.0


def test_open_decision_accepts_quant_leverage_field():
    decision = parse_json_response(
        """
        {
          "symbol_decisions": [
            {
              "symbol": "BTC",
              "action": "OPEN_LONG",
              "reasoning": "Quant guardrail allows long.",
              "position_size_usd": 120,
              "stop_loss_price": 95,
              "take_profit_price": 130,
              "leverage": 3
            }
          ],
          "overall_summary": "BTC has enough quantified edge."
        }
        """
    )

    btc = decision.symbol_decisions[0]
    assert btc.action == "OPEN_LONG"
    assert btc.leverage == 3


def _guardrail(long_score=6.0, short_score=4.0, action_allowed=False):
    direction = "LONG" if long_score > short_score else "SHORT"
    return QuantGuardrail(
        symbol="BTC",
        score=ScoreResult(
            direction_bias=direction,
            total_score=max(long_score, short_score),
            long_score=DirectionScore(
                direction="LONG",
                total_score=long_score,
                breakdown={},
                notes=[],
            ),
            short_score=DirectionScore(
                direction="SHORT",
                total_score=short_score,
                breakdown={},
                notes=[],
            ),
            notes=[],
        ),
        stops=StopResult(
            long=StopSide(None, None, None, None, "none", None),
            short=StopSide(None, None, None, None, "none", None),
            atr_4h=None,
            current_price=100.0,
        ),
        sizing=PositionSizingResult(
            position_size_usd=75.0,
            leverage=1,
            margin_used_usd=75.0,
            winrate=0.5,
            kelly_fraction=0.25,
            fractional_kelly=0.0875,
            capped_fraction=0.0875,
            can_open=action_allowed,
            hold_reason="仓位低于 100 美元下限，强制 HOLD",
        ),
        action_allowed=action_allowed,
        allowed_action="OPEN_LONG" if action_allowed and direction == "LONG" else "HOLD",
        hold_reason=None if action_allowed else "仓位低于 100 美元下限，强制 HOLD",
    )


def _position(side):
    return Position(
        symbol="BTC",
        side=side,
        size=0.01,
        entry_price=100.0,
        mark_price=101.0,
        unrealized_pnl=-1.0,
        percentage_pnl=-1.0,
        leverage=1,
        margin=100.0,
        timestamp=datetime.now(),
    )


def test_existing_short_is_closed_when_opposing_long_score_emerges_even_if_opening_blocked():
    decision = SymbolDecision(
        symbol="BTC",
        action="HOLD",
        reasoning="LONG bias exists, but action_allowed=false.",
    )

    result = _apply_quant_guardrail(
        decision,
        {"BTC": _guardrail(long_score=6.0, short_score=4.0, action_allowed=False)},
        _position("SHORT"),
    )

    assert result.action == "CLOSE_SHORT"
    assert result.position_size_usd == 0.0
    assert result.stop_loss_price is None
    assert result.take_profit_price is None
    assert "持仓退出护栏" in result.reasoning


def test_existing_long_is_closed_when_opposing_short_score_emerges_even_if_opening_blocked():
    decision = SymbolDecision(
        symbol="BTC",
        action="HOLD",
        reasoning="SHORT bias exists, but action_allowed=false.",
    )

    result = _apply_quant_guardrail(
        decision,
        {"BTC": _guardrail(long_score=4.0, short_score=6.0, action_allowed=False)},
        _position("LONG"),
    )

    assert result.action == "CLOSE_LONG"


def test_existing_short_is_not_closed_when_opposing_score_is_below_exit_threshold():
    decision = SymbolDecision(
        symbol="BTC",
        action="HOLD",
        reasoning="Long score is still too weak.",
    )

    result = _apply_quant_guardrail(
        decision,
        {"BTC": _guardrail(long_score=4.9, short_score=4.0, action_allowed=False)},
        _position("SHORT"),
    )

    assert result.action == "HOLD"
