import time
from datetime import datetime

from agent.nodes.analysis_node import (
    RegimeClassification,
    SymbolDecision,
    SymbolRegimeDecision,
    _apply_quant_guardrail,
    build_deterministic_symbol_decisions,
    parse_json_response,
    parse_regime_response,
)
from agent.regime.models import IndicatorSet, Regime
from agent.quant.models import (
    DirectionScore,
    EntryQualityResult,
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
            long=StopSide(95.0, 110.0, 5.0, None, "test", 2.0),
            short=StopSide(105.0, 90.0, 5.0, None, "test", 2.0),
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
        entry_quality=EntryQualityResult(
            can_enter=action_allowed,
            hold_reason=None if action_allowed else "仓位低于 100 美元下限，强制 HOLD",
            checks={"enabled": True},
        ),
        reference_price=100.0,
        reference_timeframe="3m",
        reference_timestamp=datetime.now(),
        action_allowed=action_allowed,
        allowed_action=(
            f"OPEN_{direction}" if action_allowed and direction in {"LONG", "SHORT"} else "ENTRY_HOLD"
        ),
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


def _regime_indicators(**overrides):
    values = {
        "close": 120.0,
        "ema_fast": 115.0,
        "ema_slow": 100.0,
        "ema_fast_previous": 110.0,
        "ema_mean": 118.0,
        "atr": 5.0,
        "atr_history": [3.0] * 40 + [4.0] * 40 + [5.0] * 20,
        "highs": list(range(90, 122)),
        "lows": list(range(70, 102)),
        "closes": list(range(90, 121)),
        "macd_histogram": 2.0,
        "previous_macd_histogram": 1.0,
    }
    values.update(overrides)
    return IndicatorSet(**values)


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


def test_regime_parse_failure_degrades_to_unknown_only():
    result = parse_regime_response("not json")

    assert all(item.regime == Regime.UNKNOWN for item in result.symbol_regimes)


def test_unknown_regime_blocks_new_entry_even_when_guardrail_allows_open():
    decisions = build_deterministic_symbol_decisions(
        symbols=["BTC"],
        total_balance=1000,
        positions_by_symbol={},
        quant_guardrails={"BTC": _guardrail(action_allowed=True)},
        regime_indicators={"BTC": _regime_indicators()},
        regime_classification=RegimeClassification(
            symbol_regimes=[
                SymbolRegimeDecision(
                    symbol="BTC",
                    regime=Regime.UNKNOWN,
                    confidence=0.99,
                    expires_at=int(time.time()) + 60,
                    reasoning="unknown",
                )
            ],
            overall_summary="unknown",
        ),
    )

    assert decisions["BTC"]["action"] == "ENTRY_HOLD"


def test_regime_path_builds_open_from_code_not_ai_trade_action():
    decisions = build_deterministic_symbol_decisions(
        symbols=["BTC"],
        total_balance=1000,
        positions_by_symbol={},
        quant_guardrails={"BTC": _guardrail(action_allowed=True)},
        regime_indicators={"BTC": _regime_indicators()},
        regime_classification=RegimeClassification(
            symbol_regimes=[
                SymbolRegimeDecision(
                    symbol="BTC",
                    regime=Regime.RANGE,
                    confidence=0.99,
                    expires_at=int(time.time()) + 60,
                    reasoning="trend",
                )
            ],
            overall_summary="trend",
        ),
    )

    assert decisions["BTC"]["action"] == "OPEN_LONG"
    assert decisions["BTC"]["position_size_usd"] == 75.0
    assert decisions["BTC"]["stop_loss_price"] == 95.0
    assert decisions["BTC"]["take_profit_price"] == 110.0


def test_regime_path_blocks_when_risk_gate_blocks():
    decisions = build_deterministic_symbol_decisions(
        symbols=["BTC"],
        total_balance=100,
        positions_by_symbol={},
        quant_guardrails={"BTC": _guardrail(action_allowed=True)},
        regime_indicators={"BTC": _regime_indicators()},
        regime_classification=RegimeClassification(
            symbol_regimes=[
                SymbolRegimeDecision(
                    symbol="BTC",
                    regime=Regime.RANGE,
                    confidence=0.99,
                    expires_at=int(time.time()) + 60,
                    reasoning="trend",
                )
            ],
            overall_summary="trend",
        ),
    )

    assert decisions["BTC"]["action"] == "ENTRY_HOLD"
    assert "risk gate" in decisions["BTC"]["reasoning"]


def test_regime_path_blocks_when_f1_f4_q_blocks():
    decisions = build_deterministic_symbol_decisions(
        symbols=["BTC"],
        total_balance=1000,
        positions_by_symbol={},
        quant_guardrails={"BTC": _guardrail(action_allowed=True)},
        regime_indicators={"BTC": _regime_indicators(atr=None)},
        regime_classification=RegimeClassification(
            symbol_regimes=[
                SymbolRegimeDecision(
                    symbol="BTC",
                    regime=Regime.RANGE,
                    confidence=0.99,
                    expires_at=int(time.time()) + 60,
                    reasoning="trend",
                )
            ],
            overall_summary="trend",
        ),
    )

    assert decisions["BTC"]["action"] == "ENTRY_HOLD"
    assert "Q below threshold" in decisions["BTC"]["reasoning"]


def test_trend_regime_blocks_until_setup_selector_is_defined():
    decisions = build_deterministic_symbol_decisions(
        symbols=["BTC"],
        total_balance=1000,
        positions_by_symbol={},
        quant_guardrails={"BTC": _guardrail(action_allowed=True)},
        regime_indicators={"BTC": _regime_indicators()},
        regime_classification=RegimeClassification(
            symbol_regimes=[
                SymbolRegimeDecision(
                    symbol="BTC",
                    regime=Regime.TREND,
                    confidence=0.99,
                    expires_at=int(time.time()) + 60,
                    reasoning="trend",
                )
            ],
            overall_summary="trend",
        ),
    )

    assert decisions["BTC"]["action"] == "ENTRY_HOLD"
    assert "regime router has no setup" in decisions["BTC"]["reasoning"]


def test_existing_position_is_not_reopened_by_regime_path():
    decisions = build_deterministic_symbol_decisions(
        symbols=["BTC"],
        total_balance=1000,
        positions_by_symbol={"BTC": _position("LONG")},
        quant_guardrails={"BTC": _guardrail(action_allowed=True)},
        regime_indicators={"BTC": _regime_indicators()},
        regime_classification=RegimeClassification(
            symbol_regimes=[
                SymbolRegimeDecision(
                    symbol="BTC",
                    regime=Regime.TREND,
                    confidence=0.99,
                    expires_at=int(time.time()) + 60,
                    reasoning="trend",
                )
            ],
            overall_summary="trend",
        ),
    )

    assert decisions["BTC"]["action"] == "POSITION_HOLD"
