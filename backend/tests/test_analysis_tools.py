from collections import deque
from datetime import datetime

from agent.tools.analysis_tools import tech_analysis_tool
from market.data_cache import kline_cache
from market.derivatives_cache import derivatives_cache
from market.types import DerivativesSnapshot, Kline


def _sample_klines(count=60, symbol="BTC"):
    return deque(
        [
            Kline(
                symbol=symbol,
                interval="3m",
                open_time=1_000 + index * 180_000,
                close_time=1_000 + (index + 1) * 180_000 - 1,
                open_price=100 + index,
                high_price=101 + index,
                low_price=99 + index,
                close_price=100.5 + index,
                volume=10,
                quote_volume=0,
                trades_count=0,
                taker_buy_base_volume=0,
                taker_buy_quote_volume=0,
                is_final=True,
            )
            for index in range(count)
        ],
        maxlen=100,
    )


def test_tech_analysis_tool_normalizes_exchange_symbol(monkeypatch):
    monkeypatch.setattr(kline_cache, "cache", {"BTC": {"3m": _sample_klines()}})
    monkeypatch.setattr("config.settings.config.agent.timeframes", ["3m"])

    result = tech_analysis_tool("BTCUSDT")

    assert result["symbol"] == "BTC"
    assert result["timeframes"]["3m"]["data_points"] == 60
    assert "error" not in result["timeframes"]["3m"]


def test_tech_analysis_tool_handles_multi_symbol_llm_input(monkeypatch):
    monkeypatch.setattr(kline_cache, "cache", {"BTC": {"3m": _sample_klines(symbol="BTC")}})
    monkeypatch.setattr("config.settings.config.agent.symbols", ["BTC"])
    monkeypatch.setattr("config.settings.config.agent.timeframes", ["3m"])

    result = tech_analysis_tool("请分析 BTC, ETH, SOL")

    assert result["symbol"] == "BTC"
    assert result["timeframes"]["3m"]["data_points"] == 60


def test_tech_analysis_tool_falls_back_to_configured_symbols_for_ambiguous_input(
    monkeypatch,
):
    monkeypatch.setattr(
        kline_cache,
        "cache",
        {
            "BTC": {"3m": _sample_klines(symbol="BTC")},
            "ETH": {"3m": _sample_klines(symbol="ETH")},
        },
    )
    monkeypatch.setattr("config.settings.config.agent.symbols", ["BTC", "ETH"])
    monkeypatch.setattr("config.settings.config.agent.timeframes", ["3m"])

    result = tech_analysis_tool("请分析当前市场并给出决策")

    assert sorted(result["symbols"].keys()) == ["BTC", "ETH"]
    assert result["symbols"]["BTC"]["timeframes"]["3m"]["data_points"] == 60
    assert result["symbols"]["ETH"]["timeframes"]["3m"]["data_points"] == 60


def test_tech_analysis_tool_reports_extended_strategy_indicators(monkeypatch):
    monkeypatch.setattr(kline_cache, "cache", {"BTC": {"3m": _sample_klines(symbol="BTC")}})
    monkeypatch.setattr(
        derivatives_cache,
        "cache",
        {
            "BTC": DerivativesSnapshot(
                symbol="BTC",
                timestamp=datetime(2026, 6, 16, 12, 0, 0),
                open_interest=12345.6,
                funding_rate=0.0001,
                funding_interval="1h",
                funding_timestamp=datetime(2026, 6, 16, 13, 0, 0),
                mark_price=160.2,
                index_price=160.0,
                premium=0.0004,
            )
        },
    )
    monkeypatch.setattr("config.settings.config.agent.timeframes", ["3m"])

    result = tech_analysis_tool("BTC")

    timeframe = result["timeframes"]["3m"]
    assert timeframe["atr"] is not None
    assert timeframe["natr"] is not None
    assert timeframe["nearest_support"] is not None
    assert timeframe["nearest_resistance"] is not None
    assert result["derivatives"]["open_interest"] == 12345.6
    assert result["derivatives"]["funding_rate"] == 0.0001
    assert result["derivatives"]["mark_price"] == 160.2
