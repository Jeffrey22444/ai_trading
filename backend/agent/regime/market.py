"""Adapters from existing market context into regime indicators."""

from __future__ import annotations

import numpy as np
import talib

from agent.quant.models import SymbolMarketContext
from agent.regime.models import IndicatorSet


def indicator_set_from_context(context: SymbolMarketContext, config) -> IndicatorSet | None:
    reference = context.get_reference_frame()
    if reference is None:
        return None

    _timeframe, frame = reference
    closes = np.array(frame.closes, dtype=np.float64)
    highs = np.array(frame.highs, dtype=np.float64)
    lows = np.array(frame.lows, dtype=np.float64)
    if len(closes) == 0 or len(highs) != len(closes) or len(lows) != len(closes):
        return None

    ema_fast = talib.EMA(closes, timeperiod=config.scoring.ema_fast_window)
    ema_slow = talib.EMA(closes, timeperiod=config.scoring.ema_slow_window)
    ema_mean = talib.EMA(closes, timeperiod=config.scoring.mean_window_bars)
    atr = talib.ATR(highs, lows, closes, timeperiod=config.scoring.atr_window_bars)
    slope_index = len(ema_fast) - 1 - config.scoring.slope_lookback_bars

    return IndicatorSet(
        close=float(closes[-1]),
        ema_fast=_last_valid(ema_fast),
        ema_slow=_last_valid(ema_slow),
        ema_fast_previous=_valid_at(ema_fast, slope_index),
        ema_mean=_last_valid(ema_mean),
        atr=_last_valid(atr),
        atr_history=_valid_tail(atr, config.scoring.atr_percentile_window_bars),
        highs=[float(value) for value in highs],
        lows=[float(value) for value in lows],
        closes=[float(value) for value in closes],
        macd_histogram=frame.macd_histogram,
        previous_macd_histogram=frame.previous_macd_histogram,
    )


def _last_valid(values) -> float | None:
    if len(values) == 0 or np.isnan(values[-1]):
        return None
    return float(values[-1])


def _valid_at(values, index: int) -> float | None:
    if index < 0 or index >= len(values) or np.isnan(values[index]):
        return None
    return float(values[index])


def _valid_tail(values, limit: int) -> list[float]:
    valid = [float(value) for value in values if not np.isnan(value)]
    return valid[-limit:]
