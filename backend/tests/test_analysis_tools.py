from collections import deque

from agent.tools.analysis_tools import tech_analysis_tool
from market.data_cache import kline_cache
from market.types import Kline


def _sample_klines(count=60):
    return deque(
        [
            Kline(
                symbol="BTC",
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
    monkeypatch.setattr(kline_cache, "cache", {"BTC": {"3m": _sample_klines()}})
    monkeypatch.setattr("config.settings.config.agent.symbols", ["BTC"])
    monkeypatch.setattr("config.settings.config.agent.timeframes", ["3m"])

    result = tech_analysis_tool("请分析 BTC, ETH, SOL")

    assert result["symbol"] == "BTC"
    assert result["timeframes"]["3m"]["data_points"] == 60
