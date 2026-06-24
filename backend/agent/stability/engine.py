"""Shadow and enforcement logic for stability refactor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any

from agent.regime.engine import select_lifecycle, select_setup
from agent.regime.models import IndicatorSet, Regime, Setup, Side


HEALTHY = "HEALTHY"
WATCH = "WATCH"
CHALLENGED = "CHALLENGED"
INVALIDATED = "INVALIDATED"
UNKNOWN = "UNKNOWN"
NONE = "NONE"

HARD_RISK_EXIT = "HARD_RISK_EXIT"
PROFIT_PROTECTION_EXIT = "PROFIT_PROTECTION_EXIT"
THESIS_INVALIDATED_EXIT = "THESIS_INVALIDATED_EXIT"
TIME_STOP_EXIT = "TIME_STOP_EXIT"
NO_EXIT = "NO_EXIT"
EXIT_BLOCKED_BY_COOLDOWN = "EXIT_BLOCKED_BY_COOLDOWN"
EXIT_BLOCKED_BY_MIN_HOLD = "EXIT_BLOCKED_BY_MIN_HOLD"
EXIT_SHADOW_ONLY = "EXIT_SHADOW_ONLY"


@dataclass(frozen=True)
class ShadowObservation:
    symbol: str
    raw_ai_regime: str
    raw_ai_confidence: float
    raw_direction: str
    raw_total_score: float | None
    raw_long_score: float | None
    raw_short_score: float | None
    raw_allowed_action: str | None
    raw_final_action: str
    price: float | None
    atr: float | None
    setup: str | None = None
    lifecycle: str | None = None


_history: dict[str, list[ShadowObservation]] = {}


def reset_shadow_history() -> None:
    _history.clear()


def build_observation(
    *,
    symbol: str,
    decision: dict[str, Any],
    regime_classification: dict[str, Any] | None,
    indicators: IndicatorSet | None,
    config,
) -> ShadowObservation:
    guardrail = decision.get("quant_guardrail") or {}
    regime = regime_classification or {}
    raw_regime = regime.get("regime") or decision.get("regime") or UNKNOWN
    raw_direction = guardrail.get("direction_bias") or NONE
    setup, lifecycle = _setup_lifecycle(raw_regime, raw_direction, guardrail, indicators, config)
    return ShadowObservation(
        symbol=symbol,
        raw_ai_regime=raw_regime,
        raw_ai_confidence=float(regime.get("confidence") or 0.0),
        raw_direction=raw_direction,
        raw_total_score=_float(guardrail.get("total_score")),
        raw_long_score=_score_total(guardrail.get("long_score")),
        raw_short_score=_score_total(guardrail.get("short_score")),
        raw_allowed_action=guardrail.get("allowed_action"),
        raw_final_action=decision.get("action", UNKNOWN),
        price=_float(guardrail.get("reference_price")) or _float(getattr(indicators, "close", None)),
        atr=_float(getattr(indicators, "atr", None)),
        setup=setup,
        lifecycle=lifecycle,
    )


def compute_shadow_state(
    *,
    observation: ShadowObservation,
    previous_plan: Any | None,
    position: Any | None,
    config,
) -> dict[str, Any]:
    history = (_history.get(observation.symbol, []) + [observation])[-3:]
    _history[observation.symbol] = history
    active_regime = _active_regime(history, previous_plan, config)
    scores = _stable_scores(history)
    stable_direction = _stable_direction(history, scores, previous_plan, position, config)
    instability = _instability(history)
    challenge = _challenge(observation, active_regime, stable_direction, scores, instability, previous_plan, position, config)
    return {
        "timestamp": datetime.now().isoformat(),
        "symbol": observation.symbol,
        "position_id": getattr(previous_plan, "position_id", None),
        "raw_ai_regime": observation.raw_ai_regime,
        "raw_ai_confidence": observation.raw_ai_confidence,
        "active_regime": active_regime,
        "raw_direction": observation.raw_direction,
        "stable_direction": stable_direction,
        "raw_total_score": observation.raw_total_score,
        "stable_total_score": scores["total"],
        "raw_long_score": observation.raw_long_score,
        "stable_long_score": scores["long"],
        "raw_short_score": observation.raw_short_score,
        "stable_short_score": scores["short"],
        "instability_index": instability,
        "high_instability": instability >= config.instability_index.high_threshold,
        "entry_gate_threshold_effective": _entry_threshold(instability, config),
        "position_health": challenge["position_health"],
        "challenge_score": challenge["challenge_score"],
        "challenge_evidence": challenge["evidence"],
        "challenge_decay_applied": challenge["decay_applied"],
        "no_new_evidence_cycles": challenge["no_new_evidence_cycles"],
        "cooldown_state": {"mode": "shadow", "active": False},
        "profit_protection_state": {"mode": "shadow", "state": "NOT_ARMED"},
        "exit_class": EXIT_SHADOW_ONLY if observation.raw_final_action.startswith("CLOSE_") else NO_EXIT,
        "exit_allowed": False,
        "exit_block_reason": "shadow_mode_no_enforcement",
        "final_action": observation.raw_final_action,
        "warmup": len(history) < config.regime_stabilization.window_cycles,
        "setup": observation.setup,
        "lifecycle": observation.lifecycle,
    }


def apply_exit_enforcement(decision: dict[str, Any], position, plan, shadow: dict[str, Any], config) -> None:
    if config.mode == "shadow":
        if str(decision.get("action", "")).startswith("CLOSE_"):
            decision.setdefault("exit_class", EXIT_SHADOW_ONLY)
        return
    side = _position_side(position)
    close_action = "CLOSE_LONG" if side == "LONG" else "CLOSE_SHORT"
    exit_decision = classify_exit(position=position, plan=plan, shadow=shadow, config=config)
    decision["exit_class"] = exit_decision["exit_class"]
    decision["exit_allowed"] = exit_decision["exit_allowed"]
    decision["exit_block_reason"] = exit_decision["exit_block_reason"]
    decision["profit_protection_state"] = exit_decision["profit_protection_state"]
    if exit_decision["exit_allowed"]:
        decision["action"] = close_action
        decision["position_size_usd"] = 0.0
        decision["take_profit_price"] = None
        decision["leverage"] = None
        decision["reasoning"] = f"{decision.get('reasoning', '')}\nLayered exit: {exit_decision['exit_class']} {exit_decision['exit_reason']}"


def classify_exit(*, position, plan, shadow: dict[str, Any], config) -> dict[str, Any]:
    profit = profit_protection_state(position, plan, shadow, config)
    if profit["hard_risk"]:
        return _exit(HARD_RISK_EXIT, True, "hard_stop_reached", profit)
    if profit["exit"]:
        return _exit(PROFIT_PROTECTION_EXIT, True, profit["reason"], profit)
    if _extreme_signal(plan, shadow, config):
        return _exit(THESIS_INVALIDATED_EXIT, True, "extreme_signal_fast_exit", profit)
    if _min_hold_blocks(plan, config) and shadow.get("challenge_score", 0) < config.challenge_engine.max_score:
        return _exit(EXIT_BLOCKED_BY_MIN_HOLD, False, "min_hold_active", profit)
    if _thesis_invalidated(plan, shadow, config):
        return _exit(THESIS_INVALIDATED_EXIT, True, "challenge_threshold_reached", profit)
    if _time_stop(position, plan, shadow):
        return _exit(TIME_STOP_EXIT, True, "max_hold_no_progress", profit)
    return _exit(NO_EXIT, False, "no_exit_condition", profit)


def profit_protection_state(position, plan, shadow: dict[str, Any], config) -> dict[str, Any]:
    side = _position_side(position)
    entry = _float(getattr(plan, "entry_price", None)) or _float(getattr(position, "entry_price", None))
    price = _float(getattr(position, "mark_price", None)) or _float(shadow.get("raw_price")) or entry
    stop = _float(getattr(plan, "current_stop_loss", None)) or _float(getattr(plan, "initial_stop_loss", None))
    initial_stop = _float(getattr(plan, "initial_stop_loss", None))
    lifecycle = getattr(plan, "entry_lifecycle", None) or shadow.get("lifecycle") or "SHORT"
    lifecycle_cfg = config.lifecycle.get(lifecycle) or config.lifecycle["SHORT"]
    profit_pct = _profit_pct(side, entry, price)
    profit_r = _profit_r(side, entry, price, initial_stop)
    peak_profit_pct = max(_float(getattr(plan, "peak_profit_pct", None)) or 0.0, profit_pct)
    peak_profit_r = max(_float(getattr(plan, "peak_profit_r", None)) or 0.0, profit_r or 0.0)
    atr_pct = ((_float(shadow.get("atr")) or 0.0) / price) if price else 0.0
    distance_pct = max(lifecycle_cfg.trailing_distance_floor_pct, lifecycle_cfg.trailing_atr_multiple * atr_pct)
    breakeven_armed = peak_profit_pct >= lifecycle_cfg.breakeven_activation_profit_pct * 100 and (
        profit_r is None or peak_profit_r >= lifecycle_cfg.breakeven_activation_r
    )
    trailing_armed = peak_profit_pct >= lifecycle_cfg.trailing_activation_profit_pct * 100 and (
        profit_r is None or peak_profit_r >= lifecycle_cfg.trailing_activation_r
    )
    candidate_stop = stop
    if breakeven_armed and entry:
        candidate_stop = favorable_stop(side, stop, entry)
    if trailing_armed and price:
        trail_stop = price * (1 - distance_pct) if side == "LONG" else price * (1 + distance_pct)
        candidate_stop = favorable_stop(side, candidate_stop, trail_stop)
    trailing_profit_floor = peak_profit_pct - distance_pct * 100
    exit_now = trailing_armed and profit_pct < trailing_profit_floor
    hard_risk = _hard_risk(side, price, initial_stop)
    return {
        "state": "TRAILING_ARMED" if trailing_armed else "BREAKEVEN_ARMED" if breakeven_armed else "NOT_ARMED",
        "profit_pct": profit_pct,
        "profit_r": profit_r,
        "peak_profit_pct": peak_profit_pct,
        "peak_profit_r": peak_profit_r,
        "current_stop_loss": candidate_stop,
        "trailing_distance_pct": distance_pct,
        "atr_fallback": atr_pct == 0,
        "hard_risk": hard_risk,
        "exit": exit_now,
        "reason": "trailing_stop_triggered" if exit_now else "not_triggered",
    }


def favorable_stop(side: str, existing_stop: float | None, candidate_stop: float) -> float:
    if existing_stop is None:
        return candidate_stop
    if side == "LONG":
        return max(existing_stop, candidate_stop)
    if side == "SHORT":
        return min(existing_stop, candidate_stop)
    return existing_stop


def apply_entry_gate(decision: dict[str, Any], shadow: dict[str, Any], recent_plans: list[Any], config) -> None:
    if config.mode != "enforce_entry_and_exit" or decision.get("action") not in {"OPEN_LONG", "OPEN_SHORT"}:
        return
    result = entry_gate(decision, shadow, recent_plans, config)
    decision["entry_gate"] = result
    if not result["entry_allowed"]:
        decision["action"] = "ENTRY_HOLD"
        decision["position_size_usd"] = 0.0
        decision["stop_loss_price"] = None
        decision["take_profit_price"] = None
        decision["leverage"] = None
        decision["reasoning"] = f"{decision.get('reasoning', '')}\nStable entry gate blocked: {result['block_reason']}"


def entry_gate(decision: dict[str, Any], shadow: dict[str, Any], recent_plans: list[Any], config) -> dict[str, Any]:
    side = decision.get("action", "").replace("OPEN_", "")
    stable = shadow.get("stable_long_score") if side == "LONG" else shadow.get("stable_short_score")
    opposite = shadow.get("stable_short_score") if side == "LONG" else shadow.get("stable_long_score")
    threshold = _entry_threshold(shadow.get("instability_index", 0.0), config)
    extreme = stable is not None and opposite is not None and stable >= config.extreme_signal.stable_score_min and stable - opposite >= config.extreme_signal.score_margin_min
    checks = [
        (stable is not None and stable >= threshold, "stable_score_below_threshold"),
        (opposite is not None and stable is not None and stable - opposite >= config.entry_gate.score_margin_min, "stable_margin_below_threshold"),
        (shadow.get("active_regime") != UNKNOWN, "active_regime_unknown"),
        (shadow.get("setup") not in {None, NONE}, "setup_none"),
        (shadow.get("lifecycle") in {"SCALP", "SHORT", "SWING"}, "lifecycle_unresolved"),
        (_position_plan_fields_ready(decision, shadow), "position_plan_fields_missing"),
        (not _cooldown_blocks(side, recent_plans, config, extreme), "cooldown_active"),
        (not stoploss_guard_blocks(recent_plans, config), "stoploss_guard_active"),
    ]
    for passed, reason in checks:
        if not passed:
            return {
                "entry_allowed": False,
                "block_reason": reason,
                "stable_score": stable,
                "effective_threshold": threshold,
                "instability_index": shadow.get("instability_index"),
                "max_drawdown_guard": "shadow_only_unreliable_source",
            }
    return {
        "entry_allowed": True,
        "block_reason": None,
        "stable_score": stable,
        "effective_threshold": threshold,
        "instability_index": shadow.get("instability_index"),
        "max_drawdown_guard": "shadow_only_unreliable_source",
    }


def stoploss_guard_blocks(recent_plans: list[Any], config) -> bool:
    guard = config.portfolio_guards.stoploss_guard
    if not guard.enabled:
        return False
    closed = [plan for plan in recent_plans if getattr(plan, "status", None) == "CLOSED"][: guard.lookback_trades]
    stoplosses = [plan for plan in closed if getattr(plan, "last_exit_class", None) == HARD_RISK_EXIT or "stop" in str(getattr(plan, "last_exit_reason", "")).lower()]
    return len(closed) >= guard.lookback_trades and len(stoplosses) >= guard.stoploss_count_threshold


def _setup_lifecycle(raw_regime, raw_direction, guardrail, indicators, config) -> tuple[str | None, str | None]:
    try:
        regime = Regime(raw_regime)
        side = Side(raw_direction) if raw_direction in {"LONG", "SHORT"} else Side.NONE
    except ValueError:
        return None, None
    if not indicators:
        return None, None
    setup = select_setup(regime, side, indicators, config.regime_execution)
    if setup.setup == Setup.NONE:
        return setup.setup.value, None
    q = _float((guardrail.get("entry_candidate") or {}).get("q")) or 0.0
    edge = abs((_score_total(guardrail.get("long_score")) or 0.0) - (_score_total(guardrail.get("short_score")) or 0.0))
    if regime == Regime.RANGE and setup.setup == Setup.MEAN_REVERSION:
        return setup.setup.value, "SCALP"
    lifecycle = select_lifecycle(regime, setup.setup, q, edge, config.regime_execution)
    return setup.setup.value, lifecycle.value if lifecycle else None


def _active_regime(history, previous_plan, config) -> str:
    previous = getattr(previous_plan, "active_regime", None)
    for candidate in sorted({item.raw_ai_regime for item in history if item.raw_ai_regime != UNKNOWN}):
        hits = [item for item in history if item.raw_ai_regime == candidate]
        confidence = sum(item.raw_ai_confidence for item in hits) / len(hits)
        if len(hits) >= config.regime_stabilization.required_count and confidence >= config.regime_stabilization.min_average_confidence:
            return candidate
    return previous or UNKNOWN


def _stable_scores(history) -> dict[str, float | None]:
    return {
        "total": _median(item.raw_total_score for item in history),
        "long": _median(item.raw_long_score for item in history),
        "short": _median(item.raw_short_score for item in history),
    }


def _stable_direction(history, scores, previous_plan, position, config) -> str:
    previous = getattr(previous_plan, "stable_direction", None) or _position_side(position) or NONE
    for candidate in {"LONG", "SHORT"}:
        if [item.raw_direction for item in history].count(candidate) < config.direction_stabilization.required_count:
            continue
        if candidate == previous:
            return candidate
        current = scores["long"] if previous == "LONG" else scores["short"]
        target = scores["long"] if candidate == "LONG" else scores["short"]
        if current is not None and target is not None and target - current >= config.direction_stabilization.reversal_margin_min:
            return candidate
    return previous


def _instability(history) -> float:
    points = 0
    for previous, current in zip(history, history[1:]):
        points += int(previous.raw_ai_regime != current.raw_ai_regime)
        points += int(previous.raw_direction != current.raw_direction)
        if previous.raw_total_score is not None and current.raw_total_score is not None:
            points += int(abs(current.raw_total_score - previous.raw_total_score) >= 3)
    return float(points)


def _challenge(observation, active_regime, stable_direction, scores, instability, plan, position, config) -> dict[str, Any]:
    evidence: dict[str, float] = {}
    side = _position_side(position) or getattr(plan, "side", None)
    current = scores["long"] if side == "LONG" else scores["short"]
    opposite = scores["short"] if side == "LONG" else scores["long"]
    if side in {"LONG", "SHORT"} and current is not None and opposite is not None and opposite > current:
        evidence["opposite_score_dominance"] = config.challenge_engine.evidence_weights["opposite_score_dominance"]
    if side in {"LONG", "SHORT"} and stable_direction in {"LONG", "SHORT"} and stable_direction != side:
        evidence["stable_direction_reversal"] = config.challenge_engine.evidence_weights["stable_direction_reversal"]
    if getattr(plan, "entry_regime", None) and active_regime != getattr(plan, "entry_regime") and active_regime != UNKNOWN:
        evidence["active_regime_mismatch"] = config.challenge_engine.evidence_weights["active_regime_mismatch"]
    if getattr(plan, "entry_setup", None) and observation.setup and observation.setup != NONE and observation.setup != getattr(plan, "entry_setup"):
        evidence["setup_mismatch"] = config.challenge_engine.evidence_weights["setup_mismatch"]
    evidence.update(_price_evidence(side, getattr(plan, "entry_price", None), observation.price, getattr(plan, "initial_stop_loss", None)))
    if _time_no_progress(plan):
        evidence["time_no_progress"] = config.challenge_engine.evidence_weights["time_no_progress"]
    previous_score = float(getattr(plan, "challenge_score", 0.0) or 0.0)
    quiet = int(getattr(plan, "no_new_evidence_cycles", 0) or 0)
    decay = False
    if evidence:
        score = min(config.challenge_engine.max_score, previous_score + sum(evidence.values()))
        quiet = 0
    else:
        quiet += 1
        score = previous_score
        if quiet >= config.challenge_engine.decay_after_no_evidence_cycles:
            score = max(0.0, score - config.challenge_engine.decay_amount)
            quiet = 0
            decay = score != previous_score
    health = INVALIDATED if score >= config.challenge_engine.invalidation_threshold else CHALLENGED if score >= 3 else WATCH if score > 0 or instability >= config.instability_index.high_threshold else HEALTHY
    return {"evidence": evidence, "challenge_score": score, "position_health": health, "no_new_evidence_cycles": quiet, "decay_applied": decay}


def _price_evidence(side, entry, price, stop) -> dict[str, float]:
    entry = _float(entry)
    price = _float(price)
    stop = _float(stop)
    if side not in {"LONG", "SHORT"} or not entry or not price or not stop:
        return {}
    risk = entry - stop if side == "LONG" else stop - entry
    adverse = entry - price if side == "LONG" else price - entry
    hard = price <= stop if side == "LONG" else price >= stop
    if risk <= 0:
        return {}
    if hard:
        return {"hard_price_invalidation": 6.0}
    if adverse >= 0.75 * risk:
        return {"adverse_price_near_initial_stop": 2.0}
    return {}


def _exit(exit_class: str, allowed: bool, reason: str, profit: dict[str, Any]) -> dict[str, Any]:
    return {"exit_class": exit_class, "exit_allowed": allowed, "exit_reason": reason, "exit_block_reason": None if allowed else reason, "profit_protection_state": profit}


def _thesis_invalidated(plan, shadow, config) -> bool:
    return shadow.get("challenge_score", 0) >= config.challenge_engine.invalidation_threshold and shadow.get("position_health") == INVALIDATED


def _extreme_signal(plan, shadow, config) -> bool:
    side = getattr(plan, "side", None)
    current = shadow.get("stable_long_score") if side == "LONG" else shadow.get("stable_short_score")
    opposite = shadow.get("stable_short_score") if side == "LONG" else shadow.get("stable_long_score")
    return (
        current is not None
        and opposite is not None
        and opposite >= config.extreme_signal.stable_score_min
        and opposite - current >= config.extreme_signal.score_margin_min
        and getattr(plan, "cycles_held", 0) >= config.extreme_signal.min_hold_cycles_for_fast_exit
    )


def _time_stop(position, plan, shadow) -> bool:
    return (
        getattr(plan, "cycles_held", 0) >= (getattr(plan, "max_hold_cycles_if_no_profit", None) or 10**9)
        and _float(getattr(position, "unrealized_pnl", 0.0)) <= 0
        and (_float(getattr(plan, "peak_profit_r", None)) or 0.0) < 0.5
        and (shadow.get("challenge_score", 0) > 0 or shadow.get("position_health") in {WATCH, CHALLENGED})
    )


def _min_hold_blocks(plan, config) -> bool:
    lifecycle = getattr(plan, "entry_lifecycle", None)
    cfg = config.lifecycle.get(lifecycle or "")
    return bool(cfg and getattr(plan, "cycles_held", 0) < cfg.min_hold_cycles)


def _hard_risk(side, price, stop) -> bool:
    return bool(side == "LONG" and price and stop and price <= stop) or bool(side == "SHORT" and price and stop and price >= stop)


def _profit_pct(side, entry, price) -> float:
    if not entry or not price:
        return 0.0
    raw = (price - entry) / entry * 100
    return raw if side == "LONG" else -raw


def _profit_r(side, entry, price, stop) -> float | None:
    if not entry or not price or not stop:
        return None
    risk = entry - stop if side == "LONG" else stop - entry
    if risk <= 0:
        return None
    reward = price - entry if side == "LONG" else entry - price
    return reward / risk


def _entry_threshold(instability: float, config) -> float:
    return 9.0 if instability >= config.instability_index.high_threshold else config.entry_gate.base_stable_score_min


def _position_plan_fields_ready(decision, shadow) -> bool:
    return all(
        value not in {None, ""}
        for value in [
            decision.get("action"),
            decision.get("stop_loss_price"),
            decision.get("take_profit_price"),
            decision.get("position_size_usd"),
            shadow.get("active_regime"),
            shadow.get("setup"),
            shadow.get("lifecycle"),
        ]
    )


def _cooldown_blocks(side: str, recent_plans: list[Any], config, extreme: bool) -> bool:
    if extreme and config.cooldown.allow_extreme_signal_override:
        return False
    if not recent_plans:
        return False
    latest = recent_plans[0]
    cycles = int((getattr(latest, "cooldown_state", {}) or {}).get("cycles_since_exit", 999))
    if cycles < config.cooldown.post_exit_cooldown_cycles:
        return True
    if str(getattr(latest, "side", "")).upper() != side and cycles < config.cooldown.reverse_block_cycles:
        return True
    if "loss" in str(getattr(latest, "last_exit_reason", "")).lower() and cycles < config.cooldown.post_loss_cooldown_cycles:
        return True
    return False


def _time_no_progress(plan) -> bool:
    return bool(plan and getattr(plan, "max_hold_cycles_if_no_profit", None) and getattr(plan, "cycles_held", 0) >= plan.max_hold_cycles_if_no_profit and (getattr(plan, "peak_profit_pct", 0.0) or 0.0) <= 0)


def _position_side(position) -> str | None:
    side = getattr(position, "side", None)
    return str(side).upper() if side else None


def _median(values) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return float(median(clean)) if clean else None


def _score_total(value) -> float | None:
    if isinstance(value, dict):
        return _float(value.get("total") or value.get("total_score"))
    return _float(value)


def _float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
