from datetime import datetime
from types import SimpleNamespace

from agent.quant.guardrails import build_quant_guardrail
from agent.quant.models import (
    DirectionScore,
    IndicatorFrame,
    ScoreResult,
    SymbolMarketContext,
)
from agent.quant.position_sizing import calculate_position_size
from agent.quant.scoring import score_symbol
from agent.quant.stops import calculate_stops
from config.agent_config import (
    EntryQualityConfig,
    KellyConfig,
    LeverageConfig,
    ScoringConfig,
    StopConfig,
    load_app_config,
)


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
    timestamp=None,
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
        timestamp=timestamp,
    )


def _context(symbol="ETH", frame=None, previous_oi=1000.0, current_oi=1100.0):
    frame = frame or _frame()
    return SymbolMarketContext(
        symbol=symbol,
        timeframes={"1h": frame, "4h": frame},
        derivatives={"open_interest": current_oi, "funding_rate": 0.0001},
        previous_derivatives={"open_interest": previous_oi},
    )


def _guardrail_config(entry_quality=None):
    return SimpleNamespace(
        scoring=ScoringConfig(),
        stop=StopConfig(),
        kelly=KellyConfig(min_position_usd=10),
        leverage=LeverageConfig(),
        entry_quality=entry_quality or EntryQualityConfig(),
    )


def _guardrail_context_for_frame(frame, symbol="ETH"):
    return SymbolMarketContext(
        symbol=symbol,
        timeframes={"3m": frame, "1h": frame, "4h": frame},
        derivatives={"open_interest": 1100.0, "funding_rate": 0.0001},
        previous_derivatives={"open_interest": 1000.0},
    )


def _fresh_long_frame(**overrides):
    values = {"timestamp": datetime.now()}
    values.update(overrides)
    return _frame(**values)


def _fresh_short_frame(**overrides):
    values = {
        "price": 80.0,
        "ema20": 90.0,
        "ema50": 100.0,
        "macd": -2.0,
        "previous_macd": -1.0,
        "rsi": 45.0,
        "timestamp": datetime.now(),
    }
    values.update(overrides)
    return _frame(**values)


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


def test_safety_and_entry_quality_config_loads_from_agent_yaml():
    config = load_app_config()

    assert config.entry_quality.enabled is True
    assert config.execution_safety.max_entry_price_drift_pct == 0.003


def test_quant_guardrail_outputs_reference_price_from_3m_first():
    timestamp = datetime(2026, 6, 18, 12, 0, 0)
    context = SymbolMarketContext(
        symbol="ETH",
        timeframes={
            "3m": _frame(price=121.0, timestamp=timestamp),
            "1h": _frame(price=120.0, timestamp=datetime(2026, 6, 18, 11, 0, 0)),
            "4h": _frame(price=119.0, timestamp=datetime(2026, 6, 18, 8, 0, 0)),
        },
        derivatives={"open_interest": 1100.0, "funding_rate": 0.0001},
        previous_derivatives={"open_interest": 1000.0},
    )

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())
    prompt = guardrail.to_prompt_dict()

    assert prompt["reference_price"] == 121.0
    assert prompt["reference_timeframe"] == "3m"
    assert prompt["reference_timestamp"] == "2026-06-18T12:00:00"


def test_reference_frame_falls_back_to_1h_then_4h():
    one_hour_context = SymbolMarketContext(
        symbol="ETH",
        timeframes={
            "1h": _frame(price=120.0, timestamp=datetime(2026, 6, 18, 11, 0, 0)),
            "4h": _frame(price=119.0, timestamp=datetime(2026, 6, 18, 8, 0, 0)),
        },
        derivatives={},
        previous_derivatives={},
    )
    four_hour_context = SymbolMarketContext(
        symbol="ETH",
        timeframes={
            "4h": _frame(price=119.0, timestamp=datetime(2026, 6, 18, 8, 0, 0)),
        },
        derivatives={},
        previous_derivatives={},
    )

    assert one_hour_context.reference_price == 120.0
    assert one_hour_context.reference_timeframe == "1h"
    assert four_hour_context.reference_price == 119.0
    assert four_hour_context.reference_timeframe == "4h"


def test_entry_quality_blocks_long_when_rsi_is_overheated():
    context = _guardrail_context_for_frame(_fresh_long_frame(rsi=71.0))

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())

    assert guardrail.action_allowed is False
    assert guardrail.to_prompt_dict()["entry_quality"]["can_enter"] is False
    assert "RSI" in guardrail.hold_reason


def test_entry_quality_blocks_short_when_rsi_is_too_cold():
    context = _guardrail_context_for_frame(_fresh_short_frame(rsi=29.0))

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())

    assert guardrail.action_allowed is False
    assert guardrail.to_prompt_dict()["entry_quality"]["can_enter"] is False
    assert "RSI" in guardrail.hold_reason


def test_entry_quality_blocks_long_when_price_chases_above_ema20():
    context = _guardrail_context_for_frame(
        _fresh_long_frame(price=120.0, ema20=110.0, atr=5.0)
    )

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())

    assert guardrail.action_allowed is False
    assert "EMA20" in guardrail.hold_reason


def test_entry_quality_blocks_short_when_price_chases_below_ema20():
    context = _guardrail_context_for_frame(
        _fresh_short_frame(price=80.0, ema20=90.0, atr=5.0)
    )

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())

    assert guardrail.action_allowed is False
    assert "EMA20" in guardrail.hold_reason


def test_entry_quality_blocks_long_when_macd_momentum_decays():
    context = _guardrail_context_for_frame(
        _fresh_long_frame(price=112.0, ema20=110.0, macd=1.0, previous_macd=1.0)
    )

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())

    assert guardrail.action_allowed is False
    assert "MACD" in guardrail.hold_reason


def test_entry_quality_blocks_short_when_macd_momentum_decays():
    context = _guardrail_context_for_frame(
        _fresh_short_frame(price=88.0, ema20=90.0, macd=-1.0, previous_macd=-1.0)
    )

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())

    assert guardrail.action_allowed is False
    assert "MACD" in guardrail.hold_reason


def test_entry_quality_can_be_disabled():
    context = _guardrail_context_for_frame(_fresh_long_frame(rsi=80.0))

    guardrail = build_quant_guardrail(
        context,
        None,
        10_000.0,
        _guardrail_config(EntryQualityConfig(enabled=False)),
    )

    assert guardrail.entry_quality.can_enter is True
    assert guardrail.to_prompt_dict()["entry_quality"]["checks"]["enabled"] is False


def test_entry_quality_blocks_when_required_fields_are_missing():
    context = _guardrail_context_for_frame(_fresh_long_frame(price=112.0, rsi=None))

    guardrail = build_quant_guardrail(context, None, 10_000.0, _guardrail_config())

    assert guardrail.action_allowed is False
    assert "字段缺失" in guardrail.hold_reason
    assert "rsi14" in guardrail.entry_quality.checks["missing_fields"]


def test_quant_guardrail_prompt_dict_contains_review_fields():
    context = _guardrail_context_for_frame(_fresh_long_frame(price=112.0, ema20=110.0))

    prompt = build_quant_guardrail(
        context, None, 10_000.0, _guardrail_config()
    ).to_prompt_dict()

    for field in (
        "direction_bias",
        "total_score",
        "long_score",
        "short_score",
        "reference_price",
        "reference_timeframe",
        "reference_timestamp",
        "entry_quality",
        "action_allowed",
        "allowed_action",
        "hold_reason",
    ):
        assert field in prompt

    assert "total" in prompt["long_score"]
    assert "breakdown" in prompt["long_score"]
    assert "notes" in prompt["long_score"]
    assert "can_enter" in prompt["entry_quality"]
    assert "checks" in prompt["entry_quality"]
