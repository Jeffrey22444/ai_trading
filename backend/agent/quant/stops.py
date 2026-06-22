"""Objective stop-loss and take-profit calculation for strategy v2."""

from __future__ import annotations

from agent.quant.models import StopResult, StopSide, SymbolMarketContext


def calculate_stops(
    context: SymbolMarketContext, stop_config, scoring_config, payoff_ratio: float = 2.0
) -> StopResult:
    frame = context.timeframes.get(stop_config.timeframe) or context.timeframes.get(
        stop_config.fallback_timeframe
    )
    current_price = context.current_price
    if not frame or current_price is None or frame.atr is None:
        empty = StopSide(None, None, None, None, "missing_data", None)
        return StopResult(empty, empty, None, current_price)

    multiplier = (
        stop_config.high_volatility_atr_stop_multiplier
        if frame.natr is not None and frame.natr >= scoring_config.high_volatility_natr
        else stop_config.atr_stop_multiplier
    )
    atr = frame.atr
    buffer = atr * stop_config.swing_buffer_atr_fraction
    long_atr_stop = current_price - multiplier * atr
    short_atr_stop = current_price + multiplier * atr
    swing_low = _latest_swing_low(
        frame.lows, stop_config.swing_lookback, stop_config.swing_strength_m
    )
    swing_high = _latest_swing_high(
        frame.highs, stop_config.swing_lookback, stop_config.swing_strength_m
    )
    long_swing_stop = swing_low - buffer if swing_low is not None else None
    short_swing_stop = swing_high + buffer if swing_high is not None else None

    long_stop, long_source = _choose_long_stop(long_atr_stop, long_swing_stop)
    short_stop, short_source = _choose_short_stop(short_atr_stop, short_swing_stop)
    long_take_profit = (
        current_price + payoff_ratio * (current_price - long_stop)
        if long_stop < current_price
        else None
    )
    short_take_profit = (
        current_price - payoff_ratio * (short_stop - current_price)
        if short_stop > current_price
        else None
    )

    return StopResult(
        long=StopSide(
            stop_loss=round(long_stop, 8),
            take_profit=round(long_take_profit, 8) if long_take_profit else None,
            atr_stop=round(long_atr_stop, 8),
            swing_level=swing_low,
            stop_source=long_source,
            risk_reward=payoff_ratio if long_take_profit else None,
        ),
        short=StopSide(
            stop_loss=round(short_stop, 8),
            take_profit=round(short_take_profit, 8) if short_take_profit else None,
            atr_stop=round(short_atr_stop, 8),
            swing_level=swing_high,
            stop_source=short_source,
            risk_reward=payoff_ratio if short_take_profit else None,
        ),
        atr_4h=atr,
        current_price=current_price,
    )


def _latest_swing_low(lows: list[float], lookback: int, strength: int) -> float | None:
    recent = lows[-lookback:] if len(lows) >= lookback else lows
    for index in range(len(recent) - strength - 1, strength - 1, -1):
        value = recent[index]
        left = recent[index - strength:index]
        right = recent[index + 1:index + 1 + strength]
        if len(left) == strength and len(right) == strength and all(
            value < other for other in left + right
        ):
            return value
    return min(recent) if recent else None


def _latest_swing_high(highs: list[float], lookback: int, strength: int) -> float | None:
    recent = highs[-lookback:] if len(highs) >= lookback else highs
    for index in range(len(recent) - strength - 1, strength - 1, -1):
        value = recent[index]
        left = recent[index - strength:index]
        right = recent[index + 1:index + 1 + strength]
        if len(left) == strength and len(right) == strength and all(
            value > other for other in left + right
        ):
            return value
    return max(recent) if recent else None


def _choose_long_stop(atr_stop: float, swing_stop: float | None) -> tuple[float, str]:
    if swing_stop is None:
        return atr_stop, "atr"
    if swing_stop < atr_stop:
        return swing_stop, "swing"
    return atr_stop, "atr"


def _choose_short_stop(atr_stop: float, swing_stop: float | None) -> tuple[float, str]:
    if swing_stop is None:
        return atr_stop, "atr"
    if swing_stop > atr_stop:
        return swing_stop, "swing"
    return atr_stop, "atr"
