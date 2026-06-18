from agent.quant.models import (
    DirectionScore,
    IndicatorFrame,
    ScoreResult,
    SymbolMarketContext,
)
from agent.quant.position_sizing import calculate_position_size
from agent.quant.scoring import score_symbol
from agent.quant.stops import calculate_stops
from config.agent_config import KellyConfig, LeverageConfig, ScoringConfig, StopConfig


def _score_result(total=8.0, direction="LONG"):
    return ScoreResult(
        direction_bias=direction,
        total_score=total,
        long_score=DirectionScore(
            direction="LONG", total_score=total, breakdown={}, notes=[]
        ),
        short_score=DirectionScore(
            direction="SHORT", total_score=3.0, breakdown={}, notes=[]
        ),
        notes=[],
    )


def _frame(
    *,
    price=120.0,
    ema20=110.0,
    ema50=100.0,
    macd=2.0,
    previous_macd=1.0,
    rsi=55.0,
    atr=5.0,
    natr=3.0,
):
    return IndicatorFrame(
        current_price=price,
        ema20=ema20,
        ema50=ema50,
        macd_histogram=macd,
        previous_macd_histogram=previous_macd,
        rsi14=rsi,
        atr=atr,
        natr=natr,
        highs=[
            100,
            103,
            108,
            112,
            116,
            121,
            124,
            122,
            125,
            126,
            123,
            122,
            121,
            120,
            119,
            121,
            122,
            123,
            124,
            125,
        ],
        lows=[
            90,
            94,
            98,
            101,
            105,
            109,
            112,
            110,
            111,
            113,
            112,
            109,
            110,
            111,
            112,
            113,
            114,
            115,
            116,
            117,
        ],
        closes=[100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 119, 120],
    )


def _context(symbol="ETH", frame=None, previous_oi=1000.0, current_oi=1100.0):
    frame = frame or _frame()
    return SymbolMarketContext(
        symbol=symbol,
        timeframes={"1h": frame, "4h": frame},
        derivatives={"open_interest": current_oi, "funding_rate": 0.0001},
        previous_derivatives={"open_interest": previous_oi},
    )


def test_kelly_position_sizing_is_code_calculated_and_uses_100_usd_minimum():
    result = calculate_position_size(
        _score_result(total=8.0),
        available_balance=900.0,
        kelly_config=KellyConfig(min_position_usd=100),
        leverage_config=LeverageConfig(),
        scoring_config=ScoringConfig(),
    )

    assert result.can_open is False
    assert result.position_size_usd == 91.8
    assert "100" in result.hold_reason


def test_kelly_position_sizing_opens_when_calculated_size_meets_minimum():
    result = calculate_position_size(
        _score_result(total=9.2),
        available_balance=3_000.0,
        kelly_config=KellyConfig(min_position_usd=100),
        leverage_config=LeverageConfig(),
        scoring_config=ScoringConfig(),
    )

    assert result.can_open is True
    assert result.winrate == 0.58
    assert result.position_size_usd == 333.0
    assert result.leverage == 3


def test_core_symbol_d5_scores_own_trend_without_btc_hard_veto():
    eth_context = _context("ETH")
    btc_bearish_frame = _frame(
        price=80.0,
        ema20=90.0,
        ema50=100.0,
        macd=-2.0,
        previous_macd=-1.0,
    )
    btc_context = _context("BTC", frame=btc_bearish_frame)

    result = score_symbol(eth_context, btc_context, ScoringConfig())

    assert result.long_score.breakdown["D5"] == 2
    assert result.short_score.breakdown["D5"] == 0
    assert result.direction_bias == "LONG"


def test_core_symbol_d5_can_be_zero_when_own_trend_does_not_support_direction():
    neutral_frame = _frame(price=105.0, ema20=110.0, ema50=100.0)
    eth_context = _context("ETH", frame=neutral_frame)
    btc_bearish_context = _context(
        "BTC",
        frame=_frame(price=80.0, ema20=90.0, ema50=100.0),
    )

    result = score_symbol(eth_context, btc_bearish_context, ScoringConfig())

    assert result.long_score.breakdown["D5"] == 0
    assert result.short_score.breakdown["D5"] == 0


def test_non_core_symbol_still_uses_benchmark_context_for_d5():
    doge_context = _context("DOGE")
    btc_bearish_context = _context(
        "BTC",
        frame=_frame(price=80.0, ema20=90.0, ema50=100.0),
    )

    result = score_symbol(doge_context, btc_bearish_context, ScoringConfig())

    assert result.long_score.breakdown["D5"] == 0
    assert result.short_score.breakdown["D5"] == 2


def test_objective_stops_are_directionally_valid_and_two_to_one():
    result = calculate_stops(_context(), StopConfig(), ScoringConfig())

    assert result.long.stop_loss < result.current_price < result.long.take_profit
    assert result.short.take_profit < result.current_price < result.short.stop_loss
    assert result.long.risk_reward == 2.0
    assert result.short.risk_reward == 2.0
