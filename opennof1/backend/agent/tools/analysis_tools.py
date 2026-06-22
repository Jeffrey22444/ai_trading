"""
Multi-Timeframe Technical Analysis Tool for AI Agent
Uses TA-Lib for professional technical indicators across multiple timeframes
"""
import numpy as np
import talib
from typing import Dict, Any
from datetime import datetime

from market.derivatives_cache import derivatives_cache
from market.data_cache import kline_cache
from trading.symbols import from_exchange_symbol
from utils.logger import logger


def _generate_overall_signals(multi_timeframe_analysis: Dict[str, Dict]) -> Dict[str, Any]:
    """生成跨时间框架的综合信号"""
    overall_signals = {}
    
    # EMA 趋势分析
    ema20_above_ema50_count = 0
    total_timeframes = 0
    
    for timeframe, data in multi_timeframe_analysis.items():
        if "error" in data:
            continue
            
        if data.get("ema20") and data.get("ema50"):
            total_timeframes += 1
            if data["ema20"] > data["ema50"]:
                ema20_above_ema50_count += 1
    
    # 趋势一致性
    if total_timeframes > 0:
        trend_consistency = ema20_above_ema50_count / total_timeframes
        overall_signals["trend_direction"] = "上涨" if trend_consistency > 0.6 else "下跌" if trend_consistency < 0.4 else "震荡"
        overall_signals["trend_consistency"] = float(trend_consistency)
    
    # RSI 综合分析
    rsi7_values = []
    rsi14_values = []
    for timeframe, data in multi_timeframe_analysis.items():
        if data.get("rsi7") is not None:
            rsi7_values.append(data["rsi7"])
        if data.get("rsi14") is not None:
            rsi14_values.append(data["rsi14"])
    
    if rsi7_values:
        overall_signals["avg_rsi7"] = float(np.mean(rsi7_values))
        overall_signals["rsi7_signal"] = "超买" if overall_signals["avg_rsi7"] > 70 else "超卖" if overall_signals["avg_rsi7"] < 30 else "中性"
    
    if rsi14_values:
        overall_signals["avg_rsi14"] = float(np.mean(rsi14_values))
        overall_signals["rsi14_signal"] = "超买" if overall_signals["avg_rsi14"] > 70 else "超卖" if overall_signals["avg_rsi14"] < 30 else "中性"
    
    # MACD 跨时间框架分析
    macd_histograms = []
    for timeframe, data in multi_timeframe_analysis.items():
        if data.get("macd_histogram") is not None:
            macd_histograms.append(data["macd_histogram"])
    
    if macd_histograms:
        overall_signals["macd_consensus"] = "看涨" if np.mean(macd_histograms) > 0 else "看跌"
    
    return overall_signals


def _requested_symbols(raw_symbol: str) -> list[str]:
    """Normalize single-symbol or multi-symbol tool input from the LLM."""
    from config.settings import config

    requested = (raw_symbol or "").upper()
    configured = list(config.agent.symbols)

    matched = [
        configured_symbol
        for configured_symbol in configured
        if from_exchange_symbol(configured_symbol) in requested
    ]
    if matched:
        return matched

    # ReAct tool calls are occasionally broad or malformed. Defaulting to all
    # configured symbols is safer than inventing a cache key that guarantees an
    # empty-data response and a misleading "no K-line data" summary.
    logger.warning("未能从工具输入中识别标的，回退为分析全部配置标的: %s", raw_symbol)
    return configured


def _nearest_levels(
    highs: np.ndarray, lows: np.ndarray, current_price: float, lookback: int = 20
) -> tuple[float | None, float | None]:
    """Estimate nearby support/resistance from recent candles."""
    recent_highs = highs[-lookback:] if len(highs) >= lookback else highs
    recent_lows = lows[-lookback:] if len(lows) >= lookback else lows

    lower_levels = recent_lows[recent_lows <= current_price]
    upper_levels = recent_highs[recent_highs >= current_price]

    support = float(np.max(lower_levels)) if len(lower_levels) else float(np.min(recent_lows))
    resistance = (
        float(np.min(upper_levels)) if len(upper_levels) else float(np.max(recent_highs))
    )
    return support, resistance


def _derivatives_context(logical_symbol: str) -> Dict[str, Any]:
    snapshot = derivatives_cache.get_snapshot(logical_symbol)
    if snapshot is None:
        return {
            "open_interest": None,
            "funding_rate": None,
            "funding_interval": None,
            "funding_timestamp": None,
            "mark_price": None,
            "index_price": None,
            "premium": None,
        }

    return {
        "open_interest": snapshot.open_interest,
        "funding_rate": snapshot.funding_rate,
        "funding_interval": snapshot.funding_interval,
        "funding_timestamp": (
            snapshot.funding_timestamp.isoformat() if snapshot.funding_timestamp else None
        ),
        "mark_price": snapshot.mark_price,
        "index_price": snapshot.index_price,
        "premium": snapshot.premium,
    }


def _analyze_single_symbol(symbol: str) -> Dict[str, Any]:
    from config.settings import config

    logical_symbol = from_exchange_symbol(symbol)
    logger.info(f"获取 {logical_symbol} 多时间框架技术分析数据")

    multi_timeframe_analysis = {}

    for timeframe in config.agent.timeframes:
        klines = kline_cache.get_klines_snapshot(logical_symbol, timeframe, limit=200)
        logger.info(f"获取到 {logical_symbol} {timeframe} {len(klines)} 根K线数据")

        if not klines:
            logger.warning(f"{logical_symbol} {timeframe} 缓存中无数据")
            multi_timeframe_analysis[timeframe] = {
                "error": "缓存中无数据",
                "data_points": 0
            }
            continue

        closes = np.array([float(kline.close_price) for kline in klines], dtype=np.float64)
        highs = np.array([float(kline.high_price) for kline in klines], dtype=np.float64)
        lows = np.array([float(kline.low_price) for kline in klines], dtype=np.float64)
        current_price = closes[-1]
        price_change = closes[-1] - closes[-2] if len(closes) >= 2 else 0
        price_change_percent = (
            price_change / closes[-2] * 100
            if len(closes) >= 2 and closes[-2] > 0
            else 0
        )

        timeframe_result = {
            "current_price": current_price,
            "price_change": price_change,
            "price_change_percent": price_change_percent,
            "data_points": len(klines),
            "latest_timestamp": (
                klines[-1].timestamp.isoformat() if klines[-1].timestamp else None
            ),
        }

        timeframe_result["ema20"] = (
            talib.EMA(closes, timeperiod=20)[-1] if len(closes) >= 20 else None
        )
        timeframe_result["ema50"] = (
            talib.EMA(closes, timeperiod=50)[-1] if len(closes) >= 50 else None
        )

        macd, macd_signal, macd_hist = talib.MACD(
            closes, fastperiod=12, slowperiod=26, signalperiod=9
        )
        timeframe_result["macd_line"] = (
            macd[-1] if not np.isnan(macd[-1]) else None
        )
        timeframe_result["signal_line"] = (
            macd_signal[-1] if not np.isnan(macd_signal[-1]) else None
        )
        timeframe_result["macd_histogram"] = (
            macd_hist[-1] if not np.isnan(macd_hist[-1]) else None
        )

        rsi7 = talib.RSI(closes, timeperiod=7)
        rsi14 = talib.RSI(closes, timeperiod=14)
        timeframe_result["rsi7"] = rsi7[-1] if not np.isnan(rsi7[-1]) else None
        timeframe_result["rsi14"] = rsi14[-1] if not np.isnan(rsi14[-1]) else None

        atr = talib.ATR(highs, lows, closes, timeperiod=14)
        timeframe_result["atr"] = atr[-1] if not np.isnan(atr[-1]) else None

        natr = talib.NATR(highs, lows, closes, timeperiod=14)
        timeframe_result["natr"] = natr[-1] if not np.isnan(natr[-1]) else None

        support, resistance = _nearest_levels(highs, lows, current_price)
        timeframe_result["nearest_support"] = support
        timeframe_result["nearest_resistance"] = resistance

        multi_timeframe_analysis[timeframe] = timeframe_result

    result = {
        "symbol": logical_symbol,
        "timeframes": multi_timeframe_analysis,
        "derivatives": _derivatives_context(logical_symbol),
        "overall_signals": _generate_overall_signals(multi_timeframe_analysis),
        "analysis_timestamp": datetime.now().isoformat()
    }

    logger.info(f"{logical_symbol} 多时间框架技术分析完成")
    return result


def tech_analysis_tool(symbol: str) -> Dict[str, Any]:
    """
    Multi-timeframe technical analysis tool for AI agent using TA-Lib
    
    Args:
        symbol: Trading symbol (preferred runtime input: "BTC")
    
    Returns:
        Dict containing multi-timeframe technical analysis
    """
    try:
        symbols = _requested_symbols(symbol)
        analyses = {
            logical_symbol: _analyze_single_symbol(logical_symbol)
            for logical_symbol in symbols
        }

        if len(analyses) == 1:
            return next(iter(analyses.values()))

        return {
            "symbols": analyses,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"多时间框架技术分析失败 {symbol}: {e}")
        return {
            "symbol": symbol,
            "error": f"技术分析失败: {str(e)}",
            "timeframes": {},
            "overall_signals": {},
            "analysis_timestamp": datetime.now().isoformat()
        }


# 创建 LangChain 工具实例
def create_tech_analysis_tool():
    """创建技术分析工具供 LangChain 使用"""
    from langchain_core.tools import Tool
    
    tool = Tool(
        name="tech_analysis_tool",
        description="获取交易标的的多时间框架技术分析数据，包括EMA20、EMA50、MACD、RSI7、RSI14、ATR、NATR、最近支撑/阻力位，以及衍生品上下文中的持仓量OI、资金费率Funding、标记价格等，并提供跨时间框架的综合分析",
        func=tech_analysis_tool
    )
    
    return tool
