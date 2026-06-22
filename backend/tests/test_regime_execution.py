import pytest

from agent.regime.engine import (
    advance_position_state,
    bounded_execution_result,
    calculate_risk_budget,
    construct_order_intent,
    decide_loop_gates,
    final_entry_decision,
    normalize_regime,
    reconcile_position,
    risk_gate,
    route_regime,
    score_direction,
    score_entry,
    select_lifecycle,
    select_setup,
    tighten_stop_loss,
    verify_post_fill_protection,
)
from agent.regime.models import (
    Decision,
    EntryScore,
    ExecutionResult,
    ExecutionStatus,
    FailureMode,
    Gate,
    IndicatorSet,
    Lifecycle,
    OpenRisk,
    Position,
    PositionStatus,
    Regime,
    RegimeOutput,
    Side,
    Setup,
)
from config.agent_config import RegimeExecutionConfig, load_app_config


def _indicators(**overrides):
    values = {
        "close": 120.0,
        "ema_fast": 115.0,
        "ema_slow": 100.0,
        "ema_fast_previous": 110.0,
        "ema_mean": 118.0,
        "atr": 5.0,
        "atr_history": [3.0] * 40 + [4.0] * 40 + [5.0] * 20,
        "highs": list(range(90, 122)),
        "lows": list(range(70, 102)),
        "closes": list(range(90, 121)),
        "macd_histogram": 2.0,
        "previous_macd_histogram": 1.0,
    }
    values.update(overrides)
    return IndicatorSet(**values)


def _setup_indicators(**overrides):
    values = {
        "close": 100.0,
        "ema_fast": 99.8,
        "ema_slow": 95.0,
        "ema_fast_previous": 99.0,
        "ema_mean": 99.0,
        "atr": 2.0,
        "atr_history": [2.0] * 100,
        "highs": [90.0] * 20 + [101.0],
        "lows": [80.0] * 20 + [98.0],
        "closes": [95.0] * 19 + [99.0, 100.0],
        "macd_histogram": 1.0,
        "previous_macd_histogram": 0.5,
    }
    values.update(overrides)
    return IndicatorSet(**values)


def _position(**overrides):
    values = {
        "id": "p1",
        "symbol": "BTC",
        "side": Side.LONG,
        "lifecycle": Lifecycle.SHORT,
        "state": PositionStatus.ACTIVE,
        "failure_mode": FailureMode.NONE,
        "entry_price": 100.0,
        "size": 1.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "opened_at": 100,
        "updated_at": 100,
        "unrealized_pnl": 0.0,
        "unrealized_r": 0.0,
    }
    values.update(overrides)
    return Position(**values)


def test_regime_execution_defaults_load_from_yaml():
    cfg = load_app_config().regime_execution

    assert cfg.regime.min_confidence == 0.60
    assert cfg.scoring.q_threshold == 0.65
    assert cfg.risk.regime_weights["TREND"] == 0.50
    assert cfg.orders.protection_retry_max == 1


def test_invalid_enum_is_rejected():
    with pytest.raises(ValueError):
        Regime("CHOP")


def test_confidence_and_expiration_normalize_to_unknown():
    cfg = RegimeExecutionConfig()

    low_confidence = normalize_regime(
        RegimeOutput(Regime.TREND, confidence=0.59, expires_at=200),
        now=100,
        config=cfg,
    )
    expired = normalize_regime(
        RegimeOutput(Regime.BREAKOUT, confidence=0.90, expires_at=99),
        now=100,
        config=cfg,
    )

    assert low_confidence.regime == Regime.UNKNOWN
    assert expired.regime == Regime.UNKNOWN
    assert route_regime(Regime.UNKNOWN) == []


def test_range_routes_to_mean_reversion_short_only():
    assert route_regime(Regime.RANGE)[0].setup == Setup.MEAN_REVERSION
    assert route_regime(Regime.RANGE)[0].lifecycle == Lifecycle.SHORT


def test_entry_scores_are_clamped_and_q_is_weighted():
    cfg = RegimeExecutionConfig()

    result = score_entry(_indicators(), cfg)
    expected_q = (
        result.f1_trend_strength * 0.30
        + result.f2_momentum * 0.25
        + result.f3_volatility_context * 0.25
        + result.f4_entry_timing * 0.20
    )

    assert 0 <= result.f1_trend_strength <= 1
    assert 0 <= result.f2_momentum <= 1
    assert 0 <= result.f3_volatility_context <= 1
    assert 0 <= result.f4_entry_timing <= 1
    assert result.q == pytest.approx(expected_q)


def test_missing_atr_returns_zero_q():
    result = score_entry(_indicators(atr=None), RegimeExecutionConfig())

    assert result.q == 0


def test_direction_tie_and_low_edge_block_entry():
    cfg = RegimeExecutionConfig()

    tied = score_direction(
        _indicators(
            close=100,
            ema_fast=100,
            ema_slow=100,
            ema_mean=100,
            macd_histogram=1,
            previous_macd_histogram=1,
        ),
        cfg,
    )
    low_edge = score_direction(
        _indicators(close=120, ema_fast=115, ema_slow=130, ema_mean=130),
        cfg,
    )

    assert tied.side == Side.NONE
    assert low_edge.edge < cfg.scoring.d_edge_threshold
    assert low_edge.side == Side.NONE


def test_setup_selector_blocks_unknown_none_side_and_missing_atr():
    cfg = RegimeExecutionConfig()

    assert select_setup(Regime.UNKNOWN, Side.LONG, _setup_indicators(), cfg).setup == Setup.NONE
    assert select_setup(Regime.TREND, Side.NONE, _setup_indicators(), cfg).setup == Setup.NONE
    assert select_setup(Regime.TREND, Side.LONG, _setup_indicators(atr=0), cfg).setup == Setup.NONE


def test_setup_selector_trend_pullbacks():
    cfg = RegimeExecutionConfig()

    long_result = select_setup(
        Regime.TREND,
        Side.LONG,
        _setup_indicators(close=100, ema_fast=99.8, ema_slow=95, highs=[101] * 20 + [100]),
        cfg,
    )
    short_result = select_setup(
        Regime.TREND,
        Side.SHORT,
        _setup_indicators(
            close=90,
            ema_fast=90.2,
            ema_slow=95,
            highs=[100] * 21,
            lows=[88] * 20 + [90],
            closes=[95] * 19 + [91, 90],
            macd_histogram=-1,
            previous_macd_histogram=-0.5,
        ),
        cfg,
    )

    assert long_result.setup == Setup.PULLBACK
    assert short_result.setup == Setup.PULLBACK


def test_setup_selector_trend_continuations_and_middle_block():
    cfg = RegimeExecutionConfig()

    long_result = select_setup(
        Regime.TREND,
        Side.LONG,
        _setup_indicators(close=102, ema_fast=99, ema_slow=95, highs=[100] * 20 + [102]),
        cfg,
    )
    short_result = select_setup(
        Regime.TREND,
        Side.SHORT,
        _setup_indicators(
            close=88,
            ema_fast=91,
            ema_slow=95,
            lows=[90] * 20 + [88],
            closes=[95] * 19 + [89, 88],
            macd_histogram=-1,
            previous_macd_histogram=-0.5,
        ),
        cfg,
    )
    middle = select_setup(
        Regime.TREND,
        Side.LONG,
        _setup_indicators(close=100, ema_fast=98, ema_slow=95, highs=[101] * 21),
        cfg,
    )

    assert long_result.setup == Setup.CONTINUATION
    assert short_result.setup == Setup.CONTINUATION
    assert middle.setup == Setup.NONE


def test_setup_selector_breakout_momentum_and_continuation():
    cfg = RegimeExecutionConfig()

    fresh_long = select_setup(
        Regime.BREAKOUT,
        Side.LONG,
        _setup_indicators(close=102, highs=[100] * 20 + [102], closes=[95] * 19 + [99, 102]),
        cfg,
    )
    fresh_short = select_setup(
        Regime.BREAKOUT,
        Side.SHORT,
        _setup_indicators(
            close=88,
            lows=[90] * 20 + [88],
            closes=[95] * 19 + [91, 88],
            macd_histogram=-1,
            previous_macd_histogram=-0.5,
        ),
        cfg,
    )
    continued_long = select_setup(
        Regime.BREAKOUT,
        Side.LONG,
        _setup_indicators(close=103, ema_fast=100, ema_slow=95, highs=[100] * 20 + [103], closes=[95] * 19 + [101, 103]),
        cfg,
    )
    continued_short = select_setup(
        Regime.BREAKOUT,
        Side.SHORT,
        _setup_indicators(
            close=87,
            ema_fast=90,
            ema_slow=95,
            lows=[90] * 20 + [87],
            closes=[95] * 19 + [89, 87],
            macd_histogram=-1,
            previous_macd_histogram=-0.5,
        ),
        cfg,
    )
    weak = select_setup(
        Regime.BREAKOUT,
        Side.LONG,
        _setup_indicators(close=102, highs=[100] * 20 + [102], macd_histogram=0.1, previous_macd_histogram=0.5),
        cfg,
    )

    assert fresh_long.setup == Setup.MOMENTUM
    assert fresh_short.setup == Setup.MOMENTUM
    assert continued_long.setup == Setup.CONTINUATION
    assert continued_short.setup == Setup.CONTINUATION
    assert weak.setup == Setup.NONE


def test_setup_selector_range_mean_reversion_short_lifecycle():
    cfg = RegimeExecutionConfig()
    selection = select_setup(Regime.RANGE, Side.LONG, _setup_indicators(), cfg)

    assert selection.setup == Setup.MEAN_REVERSION
    assert select_lifecycle(Regime.RANGE, selection.setup, q=0.7, edge=0.7, config=cfg) == Lifecycle.SHORT


def test_final_entry_decision_requires_q_direction_budget_and_risk_pass():
    cfg = RegimeExecutionConfig()
    passing_score = EntryScore(1, 1, 1, 1, q=0.90)
    passing_direction = score_direction(_indicators(), cfg)

    approved = final_entry_decision(
        symbol="BTC",
        regime=Regime.TREND,
        setup=Setup.PULLBACK,
        lifecycle=Lifecycle.SWING,
        score=passing_score,
        direction=passing_direction,
        budget_available=True,
        risk_gate_result=Gate.PASS,
        config=cfg,
    )
    blocked = final_entry_decision(
        symbol="BTC",
        regime=Regime.TREND,
        setup=Setup.PULLBACK,
        lifecycle=Lifecycle.SWING,
        score=passing_score,
        direction=passing_direction,
        budget_available=True,
        risk_gate_result=Gate.BLOCK,
        config=cfg,
    )

    assert approved.decision == Decision.APPROVE
    assert blocked.decision == Decision.BLOCK


def test_risk_budget_and_gate_enforce_caps():
    cfg = RegimeExecutionConfig()
    open_risks = [
        OpenRisk(
            regime=Regime.TREND,
            side=Side.LONG,
            entry_price=100,
            stop_loss=95,
            size=2,
        )
    ]
    budget = calculate_risk_budget(1000, Regime.TREND, open_risks, cfg)

    assert budget.regime_budget == 50
    assert budget.active_risk == 10
    assert budget.remaining_risk == 40
    assert (
        risk_gate(
            account_drawdown=0,
            circuit_breaker_active=False,
            candidate_risk=25,
            cluster_active_risk=20,
            equity=1000,
            remaining_risk=budget.remaining_risk,
            config=cfg,
        )
        == Gate.BLOCK
    )


def test_lifecycle_selection_and_order_construction():
    cfg = RegimeExecutionConfig()
    lifecycle = select_lifecycle(
        Regime.BREAKOUT,
        Setup.CONTINUATION,
        q=0.85,
        edge=0.70,
        config=cfg,
    )

    long_intent = construct_order_intent(
        symbol="BTC",
        side=Side.LONG,
        lifecycle=lifecycle,
        entry_price=100,
        atr=2,
        equity=1000,
        remaining_risk=15,
        config=cfg,
    )
    short_intent = construct_order_intent(
        symbol="BTC",
        side=Side.SHORT,
        lifecycle=Lifecycle.SHORT,
        entry_price=100,
        atr=2,
        equity=1000,
        remaining_risk=15,
        config=cfg,
    )

    assert lifecycle == Lifecycle.SWING
    assert long_intent.stop_loss < long_intent.entry_price < long_intent.take_profit
    assert short_intent.take_profit < short_intent.entry_price < short_intent.stop_loss
    assert long_intent.lifecycle == Lifecycle.SWING
    assert long_intent.size == pytest.approx(15 / 4)


def test_execution_retry_count_is_bounded_and_unknown_does_not_activate():
    cfg = RegimeExecutionConfig()
    bounded = bounded_execution_result(
        ExecutionResult(ExecutionStatus.FAILURE, retry_count=9),
        cfg.orders.max_execution_retries,
    )
    protection = verify_post_fill_protection(
        execution_result=ExecutionResult(ExecutionStatus.UNKNOWN),
        stop_loss_verified=True,
        take_profit_verified=True,
        config=cfg,
    )

    assert bounded.retry_count == cfg.orders.max_execution_retries
    assert protection.position_state == PositionStatus.INIT
    assert protection.symbol_entries_blocked is True


def test_post_fill_protection_failures_drive_required_actions():
    cfg = RegimeExecutionConfig()

    no_sl = verify_post_fill_protection(
        execution_result=ExecutionResult(ExecutionStatus.SUCCESS, filled_size=1),
        stop_loss_verified=False,
        take_profit_verified=True,
        config=cfg,
    )
    no_tp = verify_post_fill_protection(
        execution_result=ExecutionResult(ExecutionStatus.SUCCESS, filled_size=1),
        stop_loss_verified=True,
        take_profit_verified=False,
        config=cfg,
    )

    assert no_sl.emergency_exit is True
    assert no_sl.failure_mode == FailureMode.PROTECTION_FAILED
    assert no_tp.position_state == PositionStatus.ACTIVE
    assert no_tp.symbol_entries_blocked is True


def test_position_state_machine_and_sl_tightening_rules():
    cfg = RegimeExecutionConfig()
    profiting = advance_position_state(
        _position(unrealized_r=1.0),
        now=120,
        config=cfg,
    )
    mature = advance_position_state(
        _position(
            state=PositionStatus.PROFITING,
            opened_at=100,
            unrealized_r=1.2,
        ),
        now=100 + cfg.lifecycle.max_hold_seconds_short,
        config=cfg,
    )
    exit_position = advance_position_state(
        _position(),
        now=130,
        risk_trigger=True,
        config=cfg,
    )
    closed = advance_position_state(
        _position(state=PositionStatus.EXIT),
        now=140,
        exchange_flat=True,
        all_orders_closed=True,
        config=cfg,
    )
    long_stop = tighten_stop_loss(_position(stop_loss=95), 94)
    short_stop = tighten_stop_loss(
        _position(side=Side.SHORT, stop_loss=105),
        106,
    )

    assert profiting.state == PositionStatus.PROFITING
    assert mature.state == PositionStatus.MATURITY
    assert exit_position.state == PositionStatus.EXIT
    assert closed.state == PositionStatus.CLOSED
    assert long_stop.stop_loss == 95
    assert short_stop.stop_loss == 105


def test_reconciliation_and_capital_release_rules():
    local = _position()
    exchange = _position(id="exchange", failure_mode=FailureMode.NONE)

    flat = reconcile_position(
        local_position=local,
        exchange_position=None,
        exchange_flat=True,
        all_orders_closed=True,
    )
    missing_local = reconcile_position(
        local_position=None,
        exchange_position=exchange,
        exchange_flat=False,
        all_orders_closed=False,
    )

    assert flat.position.state == PositionStatus.CLOSED
    assert flat.capital_released is True
    assert missing_local.position.failure_mode == FailureMode.RECONCILE
    assert missing_local.entries_blocked is True


def test_loop_gates_keep_risk_reducing_exits_allowed():
    cfg = RegimeExecutionConfig()
    unknown = decide_loop_gates(
        regime=Regime.UNKNOWN,
        drawdown_breached=False,
        reconcile_pending=False,
        config=cfg,
    )
    drawdown = decide_loop_gates(
        regime=Regime.TREND,
        drawdown_breached=True,
        reconcile_pending=False,
        config=cfg,
    )

    assert unknown.allow_entry is False
    assert unknown.allow_exit is True
    assert drawdown.allow_entry is False
    assert drawdown.allow_exit is True
    assert unknown.steps[0] == "data_validation"
    assert unknown.steps[-1] == "main_loop_orchestrator"
