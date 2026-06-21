"""Conservative entry-quality filters for strategy v2."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.quant.models import EntryQualityResult, SymbolMarketContext


def evaluate_entry_quality(
    context: SymbolMarketContext, direction: str, config
) -> EntryQualityResult:
    if not config.entry_quality.enabled:
        return EntryQualityResult(
            can_enter=True,
            hold_reason=None,
            checks={"enabled": False},
        )

    reference = context.get_reference_frame()
    if reference is None:
        return _hold("缺少参考行情帧", {"enabled": True, "reference_frame": None})

    timeframe, frame = reference
    checks: dict[str, Any] = {
        "enabled": True,
        "reference_timeframe": timeframe,
        "reference_price": frame.current_price,
        "reference_timestamp": frame.timestamp.isoformat() if frame.timestamp else None,
        "direction": direction,
    }

    missing = [
        name
        for name, value in {
            "current_price": frame.current_price,
            "rsi14": frame.rsi14,
            "ema20": frame.ema20,
            "atr": frame.atr,
            "macd_histogram": frame.macd_histogram,
            "previous_macd_histogram": frame.previous_macd_histogram,
            "timestamp": frame.timestamp,
        }.items()
        if value is None
    ]
    if missing:
        checks["missing_fields"] = missing
        return _hold(f"入场质量字段缺失: {', '.join(missing)}", checks)

    age_seconds = _age_seconds(frame.timestamp)
    checks["market_data_age_seconds"] = age_seconds
    if age_seconds > config.entry_quality.max_market_data_age_seconds:
        return _hold("参考行情数据过期，强制 HOLD", checks)

    if frame.atr <= 0:
        return _hold("ATR 无效，无法评估追价距离", checks)

    distance_atr = abs(frame.current_price - frame.ema20) / frame.atr
    checks["price_ema20_distance_atr"] = distance_atr

    if direction == "LONG":
        if frame.rsi14 > config.entry_quality.max_rsi_long:
            return _hold("LONG RSI 过热，强制 HOLD", checks)
        if (
            frame.current_price > frame.ema20
            and distance_atr > config.entry_quality.max_price_ema20_distance_atr
        ):
            return _hold("LONG 价格远离 EMA20，疑似追高", checks)
        if (
            config.entry_quality.require_momentum_not_decaying
            and frame.macd_histogram <= frame.previous_macd_histogram
        ):
            return _hold("LONG MACD 动能未扩张，强制 HOLD", checks)
        return EntryQualityResult(True, None, checks)

    if direction == "SHORT":
        if frame.rsi14 < config.entry_quality.min_rsi_short:
            return _hold("SHORT RSI 过冷，强制 HOLD", checks)
        if (
            frame.current_price < frame.ema20
            and distance_atr > config.entry_quality.max_price_ema20_distance_atr
        ):
            return _hold("SHORT 价格远离 EMA20，疑似追空", checks)
        if (
            config.entry_quality.require_momentum_not_decaying
            and frame.macd_histogram >= frame.previous_macd_histogram
        ):
            return _hold("SHORT MACD 动能未扩张，强制 HOLD", checks)
        return EntryQualityResult(True, None, checks)

    return EntryQualityResult(True, None, checks)


def _age_seconds(timestamp: datetime) -> float:
    now = datetime.now(tz=timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
    return max(0.0, (now - timestamp).total_seconds())


def _hold(reason: str, checks: dict[str, Any]) -> EntryQualityResult:
    return EntryQualityResult(can_enter=False, hold_reason=reason, checks=checks)
