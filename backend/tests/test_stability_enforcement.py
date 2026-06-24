from types import SimpleNamespace

from agent.nodes.analysis_node import DeterministicSymbolDecision, _apply_position_exit_guardrail
from agent.stability.engine import (
    HARD_RISK_EXIT,
    NO_EXIT,
    PROFIT_PROTECTION_EXIT,
    THESIS_INVALIDATED_EXIT,
    TIME_STOP_EXIT,
    apply_entry_gate,
    apply_exit_enforcement,
    classify_exit,
    entry_gate,
    favorable_stop,
    profit_protection_state,
    stoploss_guard_blocks,
)
from config.agent_config import StabilityRefactorConfig
from config.settings import config


def _position(**overrides):
    values = {
        "symbol": "BTC",
        "side": "LONG",
        "entry_price": 100.0,
        "mark_price": 101.0,
        "unrealized_pnl": 1.0,
        "percentage_pnl": 1.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _plan(**overrides):
    values = {
        "position_id": "p1",
        "symbol": "BTC",
        "side": "LONG",
        "status": "OPEN",
        "entry_price": 100.0,
        "entry_regime": "TREND",
        "entry_setup": "PULLBACK",
        "entry_lifecycle": "SHORT",
        "active_regime": "TREND",
        "stable_direction": "LONG",
        "initial_stop_loss": 95.0,
        "current_stop_loss": 95.0,
        "peak_profit_pct": 0.0,
        "peak_profit_r": 0.0,
        "cycles_held": 3,
        "max_hold_cycles_if_no_profit": 40,
        "challenge_score": 0.0,
        "no_new_evidence_cycles": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _shadow(**overrides):
    values = {
        "active_regime": "TREND",
        "setup": "PULLBACK",
        "lifecycle": "SHORT",
        "stable_direction": "LONG",
        "stable_long_score": 8.5,
        "stable_short_score": 3.0,
        "instability_index": 0.0,
        "challenge_score": 0.0,
        "position_health": "HEALTHY",
        "atr": 1.0,
    }
    values.update(overrides)
    return values


def test_default_config_mode_remains_shadow():
    assert config.stability_refactor.mode == "shadow"


def test_old_raw_opposite_score_spike_no_longer_closes_in_enforcement(monkeypatch):
    monkeypatch.setattr(config.stability_refactor, "mode", "enforce_exit")
    decision = DeterministicSymbolDecision(symbol="BTC", action="POSITION_HOLD", reasoning="hold")
    guardrail = SimpleNamespace(
        score=SimpleNamespace(
            long_score=SimpleNamespace(total_score=1.0),
            short_score=SimpleNamespace(total_score=9.0),
        )
    )

    result = _apply_position_exit_guardrail(decision, guardrail, _position())

    assert result.action == "POSITION_HOLD"


def test_challenge_invalidated_closes_with_exit_class():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    result = classify_exit(
        position=_position(mark_price=99.0, unrealized_pnl=-1.0),
        plan=_plan(challenge_score=6.0),
        shadow=_shadow(challenge_score=6.0, position_health="INVALIDATED"),
        config=cfg,
    )

    assert result["exit_allowed"] is True
    assert result["exit_class"] == THESIS_INVALIDATED_EXIT


def test_challenge_below_threshold_does_not_exit():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    result = classify_exit(
        position=_position(mark_price=99.0),
        plan=_plan(challenge_score=4.0),
        shadow=_shadow(challenge_score=4.0, position_health="CHALLENGED"),
        config=cfg,
    )

    assert result["exit_allowed"] is False
    assert result["exit_class"] == NO_EXIT


def test_hard_stop_exits_during_min_hold():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    result = classify_exit(
        position=_position(mark_price=94.0),
        plan=_plan(cycles_held=0),
        shadow=_shadow(),
        config=cfg,
    )

    assert result["exit_allowed"] is True
    assert result["exit_class"] == HARD_RISK_EXIT


def test_unknown_only_observation_does_not_exit():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    result = classify_exit(
        position=_position(),
        plan=_plan(active_regime="TREND"),
        shadow=_shadow(active_regime="UNKNOWN", challenge_score=0.0, position_health="HEALTHY"),
        config=cfg,
    )

    assert result["exit_class"] == NO_EXIT


def test_extreme_signal_exits_only_after_required_age():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    young = classify_exit(
        position=_position(),
        plan=_plan(cycles_held=1),
        shadow=_shadow(stable_long_score=4.0, stable_short_score=8.5),
        config=cfg,
    )
    old = classify_exit(
        position=_position(),
        plan=_plan(cycles_held=2),
        shadow=_shadow(stable_long_score=4.0, stable_short_score=8.5),
        config=cfg,
    )

    assert young["exit_allowed"] is False
    assert old["exit_allowed"] is True
    assert old["exit_class"] == THESIS_INVALIDATED_EXIT


def test_time_stop_does_not_close_profitable_position():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    profitable = classify_exit(
        position=_position(unrealized_pnl=1.0),
        plan=_plan(cycles_held=40, peak_profit_r=0.0),
        shadow=_shadow(challenge_score=1.0, position_health="WATCH"),
        config=cfg,
    )
    losing = classify_exit(
        position=_position(unrealized_pnl=-1.0),
        plan=_plan(cycles_held=40, peak_profit_r=0.0),
        shadow=_shadow(challenge_score=1.0, position_health="WATCH"),
        config=cfg,
    )

    assert profitable["exit_class"] == NO_EXIT
    assert losing["exit_class"] == TIME_STOP_EXIT


def test_every_close_decision_gets_exit_class():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    decision = {"action": "POSITION_HOLD", "reasoning": ""}

    apply_exit_enforcement(
        decision,
        _position(mark_price=94.0),
        _plan(),
        _shadow(),
        cfg,
    )

    assert decision["action"] == "CLOSE_LONG"
    assert decision["exit_class"] == HARD_RISK_EXIT


def test_lifecycle_profit_protection_thresholds_and_atr_fallback():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    scalp = cfg.lifecycle["SCALP"]
    short = cfg.lifecycle["SHORT"]

    assert scalp.trailing_distance_floor_pct < short.trailing_distance_floor_pct
    short_state = profit_protection_state(
        _position(mark_price=100.5),
        _plan(entry_lifecycle="SHORT", initial_stop_loss=99.5, current_stop_loss=99.5),
        _shadow(atr=None),
        cfg,
    )

    assert short_state["state"] == "NOT_ARMED"
    assert short_state["atr_fallback"] is True


def test_profit_protection_exit_uses_peak_trailing():
    cfg = StabilityRefactorConfig(mode="enforce_exit")
    result = classify_exit(
        position=_position(mark_price=101.0),
        plan=_plan(entry_lifecycle="SHORT", peak_profit_pct=3.0, peak_profit_r=2.0),
        shadow=_shadow(atr=0.1),
        config=cfg,
    )

    assert result["exit_allowed"] is True
    assert result["exit_class"] == PROFIT_PROTECTION_EXIT


def test_swing_does_not_use_fixed_point_three_percent_trailing():
    cfg = StabilityRefactorConfig(mode="enforce_exit")

    assert cfg.lifecycle["SWING"].trailing_distance_floor_pct != 0.003


def test_stop_only_moves_favorably_for_long_and_short():
    assert favorable_stop("LONG", 95.0, 96.0) == 96.0
    assert favorable_stop("LONG", 95.0, 94.0) == 95.0
    assert favorable_stop("SHORT", 105.0, 104.0) == 104.0
    assert favorable_stop("SHORT", 105.0, 106.0) == 105.0


def test_entry_gate_thresholds_and_unknown_blocks():
    cfg = StabilityRefactorConfig(mode="enforce_entry_and_exit")
    decision = {
        "action": "OPEN_LONG",
        "position_size_usd": 100.0,
        "stop_loss_price": 95.0,
        "take_profit_price": 110.0,
    }

    low = entry_gate(decision, _shadow(stable_long_score=7.9), [], cfg)
    allowed = entry_gate(decision, _shadow(stable_long_score=8.0, stable_short_score=5.0), [], cfg)
    high_instability = entry_gate(decision, _shadow(stable_long_score=8.5, instability_index=2.0), [], cfg)
    unknown = entry_gate(decision, _shadow(active_regime="UNKNOWN"), [], cfg)

    assert low["entry_allowed"] is False
    assert low["block_reason"] == "stable_score_below_threshold"
    assert allowed["entry_allowed"] is True
    assert high_instability["effective_threshold"] == 9.0
    assert high_instability["entry_allowed"] is False
    assert unknown["block_reason"] == "active_regime_unknown"
    assert allowed["max_drawdown_guard"] == "shadow_only_unreliable_source"


def test_entry_gate_blocks_setup_lifecycle_and_plan_field_failures():
    cfg = StabilityRefactorConfig(mode="enforce_entry_and_exit")
    base = {"action": "OPEN_LONG", "position_size_usd": 100.0, "stop_loss_price": 95.0, "take_profit_price": 110.0}

    assert entry_gate(base, _shadow(setup="NONE"), [], cfg)["block_reason"] == "setup_none"
    assert entry_gate(base, _shadow(lifecycle=None), [], cfg)["block_reason"] == "lifecycle_unresolved"
    assert entry_gate({**base, "stop_loss_price": None}, _shadow(), [], cfg)["block_reason"] == "position_plan_fields_missing"


def test_cooldown_and_extreme_override_entry_block():
    cfg = StabilityRefactorConfig(mode="enforce_entry_and_exit")
    decision = {"action": "OPEN_LONG", "position_size_usd": 100.0, "stop_loss_price": 95.0, "take_profit_price": 110.0}
    recent = [_plan(status="CLOSED", side="LONG", cooldown_state={"cycles_since_exit": 1})]

    normal = entry_gate(decision, _shadow(stable_long_score=8.2, stable_short_score=5.0), recent, cfg)
    extreme = entry_gate(decision, _shadow(stable_long_score=8.5, stable_short_score=5.0), recent, cfg)

    assert normal["block_reason"] == "cooldown_active"
    assert extreme["entry_allowed"] is True


def test_stoploss_guard_blocks_four_of_last_five():
    cfg = StabilityRefactorConfig(mode="enforce_entry_and_exit")
    blocked = [_plan(status="CLOSED", last_exit_class=HARD_RISK_EXIT) for _ in range(4)] + [_plan(status="CLOSED", last_exit_class=THESIS_INVALIDATED_EXIT)]
    allowed = [_plan(status="CLOSED", last_exit_class=HARD_RISK_EXIT) for _ in range(3)] + [_plan(status="CLOSED", last_exit_class=THESIS_INVALIDATED_EXIT) for _ in range(2)]

    assert stoploss_guard_blocks(blocked, cfg) is True
    assert stoploss_guard_blocks(allowed, cfg) is False


def test_shadow_mode_does_not_alter_live_entry_decision():
    cfg = StabilityRefactorConfig(mode="shadow")
    decision = {"action": "OPEN_LONG", "position_size_usd": 100.0, "stop_loss_price": 95.0, "take_profit_price": 110.0, "leverage": 1}
    before = dict(decision)

    apply_entry_gate(decision, _shadow(stable_long_score=1.0), [], cfg)

    assert decision == before
