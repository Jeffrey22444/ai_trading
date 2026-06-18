"""Deterministic long/short scoring for strategy v2."""

from __future__ import annotations

from agent.quant.models import DirectionScore, ScoreResult, SymbolMarketContext


def score_symbol(
    context: SymbolMarketContext,
    benchmark_context: SymbolMarketContext | None,
    scoring_config,
) -> ScoreResult:
    long_score = _score_direction(context, benchmark_context, "LONG", scoring_config)
    short_score = _score_direction(context, benchmark_context, "SHORT", scoring_config)
    edge = abs(long_score.total_score - short_score.total_score)
    threshold = scoring_config.entry_score_threshold
    notes: list[str] = []

    if long_score.total_score < threshold and short_score.total_score < threshold:
        direction = "NEUTRAL"
        total = max(long_score.total_score, short_score.total_score)
        notes.append("多空评分均低于入场阈值")
    elif edge < scoring_config.min_direction_edge:
        direction = "NEUTRAL"
        total = max(long_score.total_score, short_score.total_score)
        notes.append("多空分差不足，方向优势不清晰")
    elif long_score.total_score > short_score.total_score:
        direction = "LONG"
        total = long_score.total_score
    else:
        direction = "SHORT"
        total = short_score.total_score

    return ScoreResult(
        direction_bias=direction,
        total_score=round(total, 2),
        long_score=long_score,
        short_score=short_score,
        notes=notes,
    )


def _score_direction(
    context: SymbolMarketContext,
    benchmark_context: SymbolMarketContext | None,
    direction: str,
    scoring_config,
) -> DirectionScore:
    breakdown = {
        "D1": _score_configured_trend(context, direction, scoring_config),
        "D2": _score_configured_momentum(context, direction, scoring_config),
        "D3": _score_volatility(context, scoring_config),
        "D4": _score_derivatives(context, direction, scoring_config),
        "D5": _score_benchmark_context(
            context, benchmark_context, direction, scoring_config
        ),
    }
    weights = scoring_config.score_weights
    weighted_total = sum(
        breakdown[key] * float(weights.get(key, 1.0)) for key in breakdown
    )
    weight_total = sum(float(weights.get(key, 1.0)) for key in breakdown)
    normalized_total = weighted_total / weight_total * 5 if weight_total else 0.0
    return DirectionScore(
        direction=direction,
        total_score=round(normalized_total, 2),
        breakdown=breakdown,
        notes=_score_notes(breakdown),
    )


def _score_configured_trend(
    context: SymbolMarketContext, direction: str, scoring_config
) -> float:
    aligned = 0
    usable = 0
    for timeframe in scoring_config.trend_timeframes:
        frame = context.timeframes.get(timeframe)
        if not frame or frame.ema20 is None or frame.ema50 is None:
            continue
        usable += 1
        if direction == "LONG" and frame.current_price > frame.ema20 > frame.ema50:
            aligned += 1
        if direction == "SHORT" and frame.current_price < frame.ema20 < frame.ema50:
            aligned += 1
    if usable == 0:
        return 0
    if aligned == usable and usable >= 2:
        return 2
    if aligned >= 1:
        return 1
    return 0


def _score_configured_momentum(
    context: SymbolMarketContext, direction: str, scoring_config
) -> float:
    frame = context.timeframes.get(
        scoring_config.momentum_timeframe
    ) or context.timeframes.get(scoring_config.fallback_momentum_timeframe)
    if not frame or frame.macd_histogram is None:
        return 0
    hist = frame.macd_histogram
    prev = frame.previous_macd_histogram
    rsi = frame.rsi14
    sign_ok = hist > 0 if direction == "LONG" else hist < 0
    expanding = prev is not None and (
        hist > prev if direction == "LONG" else hist < prev
    )
    rsi_extreme = rsi is not None and (rsi > 75 or rsi < 25)
    if sign_ok and expanding and not rsi_extreme:
        return 2
    if sign_ok:
        return 1
    return 0


def _score_volatility(context: SymbolMarketContext, scoring_config) -> float:
    frame = context.timeframes.get(scoring_config.volatility_timeframe)
    if not frame or frame.natr is None:
        return 1
    if frame.natr >= scoring_config.extreme_volatility_natr:
        return 0
    if frame.natr >= scoring_config.high_volatility_natr:
        return 1
    return 2


def _score_derivatives(
    context: SymbolMarketContext, direction: str, scoring_config
) -> float:
    current_oi = context.derivatives.get("open_interest")
    previous_oi = context.previous_derivatives.get("open_interest")
    funding = context.derivatives.get("funding_rate")
    frame = context.timeframes.get(
        scoring_config.fallback_momentum_timeframe
    ) or context.timeframes.get(scoring_config.momentum_timeframe)
    if funding is not None and abs(funding) >= scoring_config.extreme_funding_abs:
        return 0
    if current_oi is None or previous_oi is None or not frame:
        return 1

    price_delta = (
        frame.closes[-1] - frame.closes[-2] if len(frame.closes) >= 2 else 0.0
    )
    oi_delta = current_oi - previous_oi
    price_same_direction = price_delta > 0 if direction == "LONG" else price_delta < 0
    funding_ok = (
        funding is None
        or (funding >= 0 if direction == "LONG" else funding <= 0)
        or abs(funding) < scoring_config.extreme_funding_abs / 4
    )
    if oi_delta > 0 and price_same_direction and funding_ok:
        return 2
    if oi_delta >= 0 or funding_ok:
        return 1
    return 0


def _score_benchmark_context(
    context: SymbolMarketContext,
    benchmark_context: SymbolMarketContext | None,
    direction: str,
    scoring_config,
) -> float:
    # BTC/ETH/SOL are treated as core markets. BTC context is a risk backdrop,
    # not a hard altcoin-style veto for ETH/SOL.
    if context.symbol in scoring_config.core_symbols:
        return max(_score_configured_trend(context, direction, scoring_config), 1)
    if not benchmark_context:
        return 1
    benchmark_direction = _simple_configured_direction(
        benchmark_context, scoring_config
    )
    if benchmark_direction == direction:
        return 2
    if benchmark_direction == "NEUTRAL":
        return 1
    return 0


def _simple_configured_direction(
    context: SymbolMarketContext, scoring_config
) -> str:
    long_trend = _score_configured_trend(context, "LONG", scoring_config)
    short_trend = _score_configured_trend(context, "SHORT", scoring_config)
    if long_trend > short_trend:
        return "LONG"
    if short_trend > long_trend:
        return "SHORT"
    return "NEUTRAL"


def _score_notes(breakdown: dict[str, float]) -> list[str]:
    return [f"{key}={value}" for key, value in breakdown.items()]
