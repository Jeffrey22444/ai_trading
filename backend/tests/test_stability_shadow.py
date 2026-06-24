from types import SimpleNamespace

from agent.stability.engine import (
    ShadowObservation,
    apply_entry_gate,
    compute_shadow_state,
    reset_shadow_history,
)
from config.agent_config import StabilityRefactorConfig, load_app_config


def _obs(**overrides):
    values = {
        "symbol": "BTC",
        "raw_ai_regime": "TREND",
        "raw_ai_confidence": 0.80,
        "raw_direction": "LONG",
        "raw_total_score": 7.0,
        "raw_long_score": 7.0,
        "raw_short_score": 3.0,
        "raw_allowed_action": "OPEN_LONG",
        "raw_final_action": "POSITION_HOLD",
        "price": 100.0,
        "atr": 1.0,
        "setup": "PULLBACK",
        "lifecycle": "SHORT",
    }
    values.update(overrides)
    return ShadowObservation(**values)


def test_stability_config_defaults_to_shadow():
    cfg = load_app_config().stability_refactor

    assert cfg.enabled is True
    assert cfg.mode == "shadow"
    assert cfg.lifecycle["SCALP"].expected_review_cycles == 2


def test_unknown_observation_keeps_previous_active_regime_without_exit():
    reset_shadow_history()
    cfg = StabilityRefactorConfig()
    plan = SimpleNamespace(active_regime="TREND", side="LONG")

    result = compute_shadow_state(
        observation=_obs(raw_ai_regime="UNKNOWN", raw_ai_confidence=0.0),
        previous_plan=plan,
        position=SimpleNamespace(side="LONG"),
        config=cfg,
    )

    assert result["active_regime"] == "TREND"
    assert result["exit_allowed"] is False


def test_warmup_rolling_median_uses_available_scores():
    reset_shadow_history()
    cfg = StabilityRefactorConfig()

    first = compute_shadow_state(
        observation=_obs(raw_total_score=9.0),
        previous_plan=None,
        position=None,
        config=cfg,
    )
    second = compute_shadow_state(
        observation=_obs(raw_total_score=1.0),
        previous_plan=None,
        position=None,
        config=cfg,
    )

    assert first["stable_total_score"] == 9.0
    assert first["warmup"] is True
    assert second["stable_total_score"] == 5.0


def test_shadow_mode_entry_gate_does_not_change_live_decision():
    cfg = StabilityRefactorConfig(mode="shadow")
    decision = {
        "action": "OPEN_LONG",
        "position_size_usd": 100.0,
        "stop_loss_price": 95.0,
        "take_profit_price": 110.0,
        "leverage": 1,
    }
    before = dict(decision)

    apply_entry_gate(decision, {"stable_long_score": 1.0}, [], cfg)

    assert decision == before
