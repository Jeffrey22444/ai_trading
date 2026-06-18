"""High-level deterministic guardrail builder for strategy v2."""

from __future__ import annotations

from agent.quant.indicators import build_market_context
from agent.quant.models import QuantGuardrail
from agent.quant.position_sizing import calculate_position_size
from agent.quant.scoring import score_symbol
from agent.quant.stops import calculate_stops


def build_quant_guardrails(symbols: list[str], available_balance: float, config):
    contexts = {
        symbol: build_market_context(symbol, config.agent.timeframes)
        for symbol in symbols
    }
    benchmark = contexts.get(config.scoring.benchmark_symbol)
    return {
        symbol: build_quant_guardrail(context, benchmark, available_balance, config)
        for symbol, context in contexts.items()
    }


def build_quant_guardrail(
    context, benchmark_context, available_balance: float, config
) -> QuantGuardrail:
    score = score_symbol(context, benchmark_context, config.scoring)
    stops = calculate_stops(
        context, config.stop, config.scoring, payoff_ratio=config.kelly.payoff_ratio_b
    )
    sizing = calculate_position_size(
        score, available_balance, config.kelly, config.leverage, config.scoring
    )
    allowed_action = (
        f"OPEN_{score.direction_bias}" if score.direction_bias in {"LONG", "SHORT"} else "HOLD"
    )
    hold_reason = None
    action_allowed = sizing.can_open and stops.current_price is not None
    if not sizing.can_open:
        hold_reason = sizing.hold_reason
        action_allowed = False
        allowed_action = "HOLD"
    elif score.direction_bias == "LONG" and (
        stops.long.stop_loss is None or stops.long.take_profit is None
    ):
        hold_reason = "多头止损止盈数据不足，强制 HOLD"
        action_allowed = False
        allowed_action = "HOLD"
    elif score.direction_bias == "SHORT" and (
        stops.short.stop_loss is None or stops.short.take_profit is None
    ):
        hold_reason = "空头止损止盈数据不足，强制 HOLD"
        action_allowed = False
        allowed_action = "HOLD"

    return QuantGuardrail(
        symbol=context.symbol,
        score=score,
        stops=stops,
        sizing=sizing,
        action_allowed=action_allowed,
        allowed_action=allowed_action,
        hold_reason=hold_reason,
    )
