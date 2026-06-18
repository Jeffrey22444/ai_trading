"""Indicator snapshots used by deterministic strategy modules."""

from __future__ import annotations

import numpy as np
import talib

from agent.quant.models import IndicatorFrame, SymbolMarketContext
from market.data_cache import kline_cache
from market.derivatives_cache import derivatives_cache
from trading.symbols import from_exchange_symbol


def build_market_context(symbol: str, timeframes: list[str]) -> SymbolMarketContext:
    logical_symbol = from_exchange_symbol(symbol)
    frames: dict[str, IndicatorFrame] = {}
    for timeframe in timeframes:
        klines = kline_cache.get_klines_snapshot(logical_symbol, timeframe, limit=200)
        if not klines:
            continue

        closes = np.array([float(kline.close_price) for kline in klines], dtype=np.float64)
        highs = np.array([float(kline.high_price) for kline in klines], dtype=np.float64)
        lows = np.array([float(kline.low_price) for kline in klines], dtype=np.float64)
        macd, _macd_signal, macd_hist = talib.MACD(
            closes, fastperiod=12, slowperiod=26, signalperiod=9
        )
        atr = talib.ATR(highs, lows, closes, timeperiod=14)
        natr = talib.NATR(highs, lows, closes, timeperiod=14)
        rsi14 = talib.RSI(closes, timeperiod=14)
        ema20 = talib.EMA(closes, timeperiod=20)
        ema50 = talib.EMA(closes, timeperiod=50)

        frames[timeframe] = IndicatorFrame(
            current_price=float(closes[-1]),
            ema20=_last_valid(ema20),
            ema50=_last_valid(ema50),
            macd_histogram=_last_valid(macd_hist),
            previous_macd_histogram=_previous_valid(macd_hist),
            rsi14=_last_valid(rsi14),
            atr=_last_valid(atr),
            natr=_last_valid(natr),
            highs=[float(value) for value in highs],
            lows=[float(value) for value in lows],
            closes=[float(value) for value in closes],
        )

    current = derivatives_cache.get_snapshot(logical_symbol)
    previous = derivatives_cache.get_previous_snapshot(logical_symbol)
    return SymbolMarketContext(
        symbol=logical_symbol,
        timeframes=frames,
        derivatives=_derivatives_dict(current),
        previous_derivatives=_derivatives_dict(previous),
    )


def _last_valid(values) -> float | None:
    if len(values) == 0 or np.isnan(values[-1]):
        return None
    return float(values[-1])


def _previous_valid(values) -> float | None:
    if len(values) < 2 or np.isnan(values[-2]):
        return None
    return float(values[-2])


def _derivatives_dict(snapshot) -> dict:
    if snapshot is None:
        return {}
    return {
        "open_interest": snapshot.open_interest,
        "funding_rate": snapshot.funding_rate,
        "mark_price": snapshot.mark_price,
        "index_price": snapshot.index_price,
        "premium": snapshot.premium,
        "timestamp": snapshot.timestamp.isoformat() if snapshot.timestamp else None,
    }

