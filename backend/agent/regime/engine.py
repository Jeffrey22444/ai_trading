"""Deterministic regime routing, scoring, risk, and order construction."""

from __future__ import annotations

from statistics import median

from agent.regime.models import (
    AllowedStrategy,
    Decision,
    DirectionScore,
    EntryCandidate,
    EntryScore,
    ExecutionResult,
    ExecutionStatus,
    FailureMode,
    Gate,
    IndicatorSet,
    Lifecycle,
    LoopDecision,
    OpenRisk,
    OrderIntent,
    Position,
    PositionStatus,
    ProtectionResult,
    ReconcileResult,
    Regime,
    RegimeOutput,
    RiskBudget,
    Side,
    Setup,
)


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def safe_div(a: float, b: float) -> float:
    return 0.0 if b <= 0 else a / b


def normalize_regime(output: RegimeOutput, now: int, config) -> RegimeOutput:
    regime = output.regime
    if output.confidence < config.regime.min_confidence or now > output.expires_at:
        regime = Regime.UNKNOWN
    return RegimeOutput(
        regime=regime,
        confidence=clamp01(output.confidence),
        expires_at=output.expires_at,
    )


def route_regime(regime: Regime) -> list[AllowedStrategy]:
    if regime == Regime.TREND:
        return [
            AllowedStrategy(Setup.PULLBACK, Lifecycle.SHORT),
            AllowedStrategy(Setup.PULLBACK, Lifecycle.SWING),
            AllowedStrategy(Setup.CONTINUATION, Lifecycle.SHORT),
            AllowedStrategy(Setup.CONTINUATION, Lifecycle.SWING),
        ]
    if regime == Regime.RANGE:
        return [AllowedStrategy(Setup.MEAN_REVERSION, Lifecycle.SHORT)]
    if regime == Regime.BREAKOUT:
        return [
            AllowedStrategy(Setup.MOMENTUM, Lifecycle.SHORT),
            AllowedStrategy(Setup.MOMENTUM, Lifecycle.SWING),
            AllowedStrategy(Setup.CONTINUATION, Lifecycle.SHORT),
            AllowedStrategy(Setup.CONTINUATION, Lifecycle.SWING),
        ]
    return []


def score_entry(indicators: IndicatorSet, config) -> EntryScore:
    if indicators.close <= 0 or not indicators.atr or indicators.atr <= 0:
        return EntryScore(0.0, 0.0, 0.0, 0.0, 0.0)

    f1 = _score_f1(indicators, config)
    f2 = _score_f2(indicators, config)
    f3 = _score_f3(indicators)
    f4 = _score_f4(indicators, config)
    weights = config.scoring.weights
    q = (
        f1 * weights.f1_trend_strength
        + f2 * weights.f2_momentum
        + f3 * weights.f3_volatility_context
        + f4 * weights.f4_entry_timing
    )
    return EntryScore(f1, f2, f3, f4, clamp01(q))


def score_direction(indicators: IndicatorSet, config) -> DirectionScore:
    values = [
        indicators.close,
        indicators.ema_fast,
        indicators.ema_slow,
        indicators.ema_mean,
        indicators.macd_histogram,
        indicators.previous_macd_histogram,
    ]
    if any(value is None for value in values) or len(indicators.closes) <= config.scoring.roc_window_bars:
        return DirectionScore(0.0, 0.0, 0.0, Side.NONE)

    roc = _roc(indicators.closes, config.scoring.roc_window_bars)
    d_long = _average_bools(
        [
            indicators.close > indicators.ema_fast,
            indicators.ema_fast > indicators.ema_slow,
            roc > 0,
            indicators.macd_histogram > indicators.previous_macd_histogram,
            indicators.close >= indicators.ema_mean,
        ]
    )
    d_short = _average_bools(
        [
            indicators.close < indicators.ema_fast,
            indicators.ema_fast < indicators.ema_slow,
            roc < 0,
            indicators.macd_histogram < indicators.previous_macd_histogram,
            indicators.close <= indicators.ema_mean,
        ]
    )
    edge = abs(d_long - d_short)
    side = Side.NONE
    if max(d_long, d_short) >= config.scoring.d_threshold and edge >= config.scoring.d_edge_threshold:
        if d_long > d_short:
            side = Side.LONG
        elif d_short > d_long:
            side = Side.SHORT
    return DirectionScore(d_long, d_short, edge, side)


def select_lifecycle(
    regime: Regime, setup: Setup, q: float, edge: float, config
) -> Lifecycle | None:
    if regime == Regime.RANGE and setup == Setup.MEAN_REVERSION:
        return Lifecycle.SHORT
    if regime == Regime.TREND and setup == Setup.PULLBACK:
        return Lifecycle.SWING if q >= 0.75 else Lifecycle.SHORT
    if regime == Regime.TREND and setup == Setup.CONTINUATION:
        return Lifecycle.SWING
    if regime == Regime.BREAKOUT and setup == Setup.MOMENTUM:
        return Lifecycle.SHORT
    if regime == Regime.BREAKOUT and setup == Setup.CONTINUATION:
        return (
            Lifecycle.SWING
            if q >= 0.80 and edge >= config.scoring.d_edge_threshold
            else Lifecycle.SHORT
        )
    return None


def calculate_risk_budget(
    equity: float, regime: Regime, open_risks: list[OpenRisk], config
) -> RiskBudget:
    weight = config.risk.regime_weights.get(regime.value, 0.0)
    regime_budget = equity * config.risk.max_risk_pct * weight
    active_risk = sum(
        calculate_active_risk(position)
        for position in open_risks
        if position.regime == regime
    )
    return RiskBudget(
        equity=equity,
        max_risk_pct=config.risk.max_risk_pct,
        regime=regime,
        regime_weight=weight,
        regime_budget=regime_budget,
        active_risk=active_risk,
        remaining_risk=regime_budget - active_risk,
    )


def calculate_active_risk(position: OpenRisk) -> float:
    if position.side == Side.LONG:
        return max(0.0, position.entry_price - position.stop_loss) * position.size
    if position.side == Side.SHORT:
        return max(0.0, position.stop_loss - position.entry_price) * position.size
    return 0.0


def risk_gate(
    *,
    account_drawdown: float,
    circuit_breaker_active: bool,
    candidate_risk: float,
    cluster_active_risk: float,
    equity: float,
    remaining_risk: float,
    config,
) -> Gate:
    if account_drawdown >= config.risk.max_drawdown_pct:
        return Gate.BLOCK
    if circuit_breaker_active:
        return Gate.BLOCK
    if remaining_risk <= 0 or candidate_risk > remaining_risk:
        return Gate.BLOCK
    if candidate_risk > equity * config.risk.max_trade_risk_pct:
        return Gate.BLOCK
    if cluster_active_risk + candidate_risk > equity * config.risk.correlation_cap_pct:
        return Gate.BLOCK
    return Gate.PASS


def final_entry_decision(
    *,
    symbol: str,
    regime: Regime,
    setup: Setup | None,
    lifecycle: Lifecycle | None,
    score: EntryScore,
    direction: DirectionScore,
    budget_available: bool,
    risk_gate_result: Gate,
    config,
) -> EntryCandidate:
    preliminary_pass = (
        score.q >= config.scoring.q_threshold
        and direction.side != Side.NONE
        and budget_available
    )
    decision = (
        Decision.APPROVE
        if preliminary_pass and risk_gate_result == Gate.PASS
        else Decision.BLOCK
    )
    return EntryCandidate(
        symbol=symbol,
        regime=regime,
        setup=setup,
        lifecycle=lifecycle,
        score=score,
        direction=direction,
        budget_available=budget_available,
        risk_gate=risk_gate_result,
        decision=decision,
    )


def build_entry_decision_from_guardrail(
    *,
    symbol: str,
    regime: Regime,
    guardrail,
    entry_score: EntryScore | None,
    direction: DirectionScore | None,
    equity: float,
    config,
) -> dict:
    """Build a deterministic trade decision from existing quant guardrails."""
    if regime == Regime.UNKNOWN:
        return _hold_decision(symbol, regime, guardrail, "UNKNOWN regime blocks entries")
    if not guardrail or not guardrail.action_allowed:
        reason = getattr(guardrail, "hold_reason", None) or "quant guardrail blocks entry"
        return _hold_decision(symbol, regime, guardrail, reason)
    if guardrail.score.direction_bias not in {"LONG", "SHORT"}:
        return _hold_decision(symbol, regime, guardrail, "direction is NONE")
    if entry_score is None or direction is None:
        return _hold_decision(symbol, regime, guardrail, "regime indicators missing")
    if entry_score.q < config.scoring.q_threshold:
        return _hold_decision(symbol, regime, guardrail, "Q below threshold")
    if direction.side == Side.NONE:
        return _hold_decision(symbol, regime, guardrail, "direction engine blocks entry")
    if direction.side.value != guardrail.score.direction_bias:
        return _hold_decision(symbol, regime, guardrail, "direction engine disagrees")

    setup = _select_setup(regime)
    if setup is None:
        return _hold_decision(symbol, regime, guardrail, "regime router has no setup")

    side = Side(guardrail.score.direction_bias)
    q = entry_score.q
    edge = direction.edge
    lifecycle = select_lifecycle(regime, setup, q, edge, config)
    if lifecycle is None:
        return _hold_decision(symbol, regime, guardrail, "lifecycle selection blocked")

    stop_side = guardrail.stops.long if side == Side.LONG else guardrail.stops.short
    if stop_side.stop_loss is None or stop_side.take_profit is None:
        return _hold_decision(symbol, regime, guardrail, "SL/TP missing")
    if not guardrail.reference_price or guardrail.reference_price <= 0:
        return _hold_decision(symbol, regime, guardrail, "reference price missing")

    risk_budget = calculate_risk_budget(equity, regime, [], config)
    quantity = safe_div(guardrail.sizing.position_size_usd, guardrail.reference_price)
    candidate_risk = abs(guardrail.reference_price - stop_side.stop_loss) * quantity
    gate = risk_gate(
        account_drawdown=0.0,
        circuit_breaker_active=False,
        candidate_risk=candidate_risk,
        cluster_active_risk=0.0,
        equity=equity,
        remaining_risk=risk_budget.remaining_risk,
        config=config,
    )
    if gate == Gate.BLOCK:
        return _hold_decision(symbol, regime, guardrail, "risk gate blocks entry")

    decision = {
        "action": f"OPEN_{side.value}",
        "reasoning": (
            f"Deterministic entry approved: regime={regime.value}, setup={setup.value}, "
            f"lifecycle={lifecycle.value}, q={q:.2f}, edge={edge:.2f}."
        ),
        "position_size_usd": guardrail.sizing.position_size_usd,
        "stop_loss_price": stop_side.stop_loss,
        "take_profit_price": stop_side.take_profit,
        "leverage": guardrail.sizing.leverage,
        "regime": regime.value,
        "setup": setup.value,
        "lifecycle": lifecycle.value,
        "entry_candidate": {
            "decision": Decision.APPROVE.value,
            "q": q,
            "edge": edge,
            "budget_available": risk_budget.budget_available,
            "risk_gate": gate.value,
            "candidate_risk": candidate_risk,
            "remaining_risk": risk_budget.remaining_risk,
        },
    }
    return decision


def construct_order_intent(
    *,
    symbol: str,
    side: Side,
    lifecycle: Lifecycle,
    entry_price: float,
    atr: float,
    equity: float,
    remaining_risk: float,
    config,
) -> OrderIntent:
    atr_multiplier = (
        config.orders.atr_stop_multiplier_short
        if lifecycle == Lifecycle.SHORT
        else config.orders.atr_stop_multiplier_swing
    )
    stop_distance = max(atr * atr_multiplier, entry_price * config.orders.min_stop_pct)
    risk_amount = min(equity * config.risk.max_trade_risk_pct, remaining_risk)
    size = safe_div(risk_amount, stop_distance)

    if side == Side.LONG:
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + stop_distance * config.orders.take_profit_r
    elif side == Side.SHORT:
        stop_loss = entry_price + stop_distance
        take_profit = entry_price - stop_distance * config.orders.take_profit_r
    else:
        raise ValueError("OrderIntent side must be LONG or SHORT")

    intent = OrderIntent(
        symbol=symbol,
        side=side,
        lifecycle=lifecycle,
        size=size,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_amount=risk_amount,
    )
    validate_order_intent(intent)
    return intent


def validate_order_intent(intent: OrderIntent) -> None:
    if intent.size <= 0:
        raise ValueError("OrderIntent size must be positive")
    if intent.side == Side.LONG and not (
        intent.stop_loss < intent.entry_price < intent.take_profit
    ):
        raise ValueError("LONG order requires stop_loss < entry < take_profit")
    if intent.side == Side.SHORT and not (
        intent.take_profit < intent.entry_price < intent.stop_loss
    ):
        raise ValueError("SHORT order requires take_profit < entry < stop_loss")


def bounded_execution_result(
    result: ExecutionResult, max_retries: int
) -> ExecutionResult:
    retry_count = min(result.retry_count, max_retries)
    return ExecutionResult(
        status=result.status,
        filled_size=result.filled_size,
        retry_count=retry_count,
        reason=result.reason,
    )


def verify_post_fill_protection(
    *,
    execution_result: ExecutionResult,
    stop_loss_verified: bool,
    take_profit_verified: bool,
    config,
) -> ProtectionResult:
    if execution_result.status != ExecutionStatus.SUCCESS:
        return ProtectionResult(
            position_state=PositionStatus.INIT,
            failure_mode=FailureMode.NONE,
            emergency_exit=False,
            symbol_entries_blocked=True,
        )
    if execution_result.filled_size <= 0:
        return ProtectionResult(
            position_state=PositionStatus.INIT,
            failure_mode=FailureMode.NONE,
            emergency_exit=False,
            symbol_entries_blocked=True,
        )
    if not stop_loss_verified:
        return ProtectionResult(
            position_state=PositionStatus.EXIT,
            failure_mode=FailureMode.PROTECTION_FAILED,
            emergency_exit=True,
            symbol_entries_blocked=True,
        )
    if not take_profit_verified:
        return ProtectionResult(
            position_state=PositionStatus.ACTIVE,
            failure_mode=FailureMode.PROTECTION_FAILED,
            emergency_exit=False,
            symbol_entries_blocked=True,
        )
    return ProtectionResult(
        position_state=PositionStatus.ACTIVE,
        failure_mode=FailureMode.NONE,
        emergency_exit=False,
        symbol_entries_blocked=False,
    )


def advance_position_state(
    position: Position,
    *,
    now: int,
    exchange_flat: bool = False,
    all_orders_closed: bool = False,
    risk_trigger: bool = False,
    stop_loss_hit: bool = False,
    protection_failed: bool = False,
    lifecycle_exit: bool = False,
    config,
) -> Position:
    if position.state == PositionStatus.EXIT and exchange_flat and all_orders_closed:
        return _replace_position(position, state=PositionStatus.CLOSED, updated_at=now)
    if risk_trigger or stop_loss_hit or protection_failed:
        failure_mode = (
            FailureMode.PROTECTION_FAILED
            if protection_failed
            else position.failure_mode
        )
        return _replace_position(
            position,
            state=PositionStatus.EXIT,
            failure_mode=failure_mode,
            updated_at=now,
        )
    if position.state == PositionStatus.INIT:
        return position
    if (
        position.state == PositionStatus.ACTIVE
        and position.unrealized_r >= config.lifecycle.profit_r_threshold
    ):
        return _replace_position(position, state=PositionStatus.PROFITING, updated_at=now)
    if position.state == PositionStatus.PROFITING:
        max_hold = (
            config.lifecycle.max_hold_seconds_short
            if position.lifecycle == Lifecycle.SHORT
            else config.lifecycle.max_hold_seconds_swing
        )
        if now - position.opened_at >= max_hold or lifecycle_exit:
            return _replace_position(
                position, state=PositionStatus.MATURITY, updated_at=now
            )
    return position


def tighten_stop_loss(position: Position, proposed_stop_loss: float) -> Position:
    if position.side == Side.LONG:
        stop_loss = max(position.stop_loss, proposed_stop_loss)
    elif position.side == Side.SHORT:
        stop_loss = min(position.stop_loss, proposed_stop_loss)
    else:
        stop_loss = position.stop_loss
    return _replace_position(position, stop_loss=stop_loss)


def reconcile_position(
    *,
    local_position: Position | None,
    exchange_position: Position | None,
    exchange_flat: bool,
    all_orders_closed: bool,
) -> ReconcileResult:
    if exchange_flat and local_position is not None:
        closed = _replace_position(local_position, state=PositionStatus.CLOSED)
        return ReconcileResult(
            position=closed,
            entries_blocked=False,
            capital_released=all_orders_closed,
        )
    if exchange_position is not None and local_position is None:
        rebuilt = _replace_position(
            exchange_position,
            failure_mode=FailureMode.RECONCILE,
        )
        return ReconcileResult(
            position=rebuilt,
            entries_blocked=True,
            capital_released=False,
        )
    if local_position and exchange_position and local_position != exchange_position:
        reconciled = _replace_position(
            exchange_position,
            failure_mode=FailureMode.RECONCILE,
        )
        return ReconcileResult(
            position=reconciled,
            entries_blocked=True,
            capital_released=False,
        )
    return ReconcileResult(
        position=local_position or exchange_position,
        entries_blocked=False,
        capital_released=exchange_flat and all_orders_closed,
    )


def decide_loop_gates(
    *,
    regime: Regime,
    drawdown_breached: bool,
    reconcile_pending: bool,
    config,
) -> LoopDecision:
    steps = [
        "data_validation",
        "exchange_reconciliation",
        "ai_regime_classification",
        "regime_router",
        "entry_scoring",
        "direction_engine",
        "portfolio_risk_budget",
        "preliminary_entry_check",
        "pre_entry_risk_gate",
        "final_entry_decision",
        "order_construction",
        "execution_engine",
        "post_fill_verification",
        "position_activation",
        "lifecycle_engine",
        "continuous_risk_override_engine",
        "exit_engine",
        "capital_recycling",
        "main_loop_orchestrator",
    ]
    entries_blocked = reconcile_pending or drawdown_breached
    if config.regime.unknown_blocks_entries and regime == Regime.UNKNOWN:
        entries_blocked = True
    return LoopDecision(
        steps=steps,
        allow_entry=not entries_blocked,
        allow_exit=True,
    )


def _score_f1(indicators: IndicatorSet, config) -> float:
    required = [indicators.ema_fast, indicators.ema_slow, indicators.ema_fast_previous]
    if any(value is None for value in required):
        return 0.0
    if len(indicators.highs) < config.scoring.structure_lookback_bars or len(indicators.lows) < config.scoring.structure_lookback_bars:
        return 0.0
    half = config.scoring.structure_half_window_bars
    ema_slope_score = clamp01(
        safe_div(abs(indicators.ema_fast - indicators.ema_fast_previous), indicators.atr)
    )
    alignment_score = float(
        (indicators.close > indicators.ema_fast > indicators.ema_slow)
        or (indicators.close < indicators.ema_fast < indicators.ema_slow)
    )
    recent_high = max(indicators.highs[-half:])
    previous_high = max(indicators.highs[-half * 2 : -half])
    recent_low = min(indicators.lows[-half:])
    previous_low = min(indicators.lows[-half * 2 : -half])
    long_structure = _average_bools([recent_high > previous_high, recent_low > previous_low])
    short_structure = _average_bools([recent_high < previous_high, recent_low < previous_low])
    structure_score = max(long_structure, short_structure)
    return clamp01((ema_slope_score + alignment_score + structure_score) / 3)


def _score_f2(indicators: IndicatorSet, config) -> float:
    if (
        indicators.macd_histogram is None
        or indicators.previous_macd_histogram is None
        or len(indicators.closes) <= config.scoring.roc_window_bars
    ):
        return 0.0
    atr_pct = indicators.atr / indicators.close
    roc_score = clamp01(abs(_roc(indicators.closes, config.scoring.roc_window_bars)) / max(atr_pct, 0.0001))
    macd_accel = abs(indicators.macd_histogram - indicators.previous_macd_histogram)
    macd_score = clamp01(safe_div(macd_accel, indicators.atr))
    return clamp01((roc_score + macd_score) / 2)


def _score_f3(indicators: IndicatorSet) -> float:
    if not indicators.atr_history:
        return 0.0
    atr_percentile = _percentile_rank(indicators.atr, indicators.atr_history)
    percentile_score = clamp01(1 - abs(atr_percentile - 0.60) / 0.60)
    atr_median = median(indicators.atr_history)
    expansion_ratio = safe_div(indicators.atr, atr_median)
    expansion_score = clamp01(1 - abs(expansion_ratio - 1.20) / 1.20)
    return clamp01((percentile_score + expansion_score) / 2)


def _score_f4(indicators: IndicatorSet, config) -> float:
    if indicators.ema_mean is None:
        return 0.0
    if len(indicators.highs) <= config.scoring.breakout_lookback_bars or len(indicators.lows) <= config.scoring.breakout_lookback_bars:
        return 0.0
    lookback = config.scoring.breakout_lookback_bars
    distance_from_mean_atr = abs(indicators.close - indicators.ema_mean) / indicators.atr
    mean_distance_score = clamp01(
        1 - distance_from_mean_atr / config.scoring.max_mean_distance_atr
    )
    previous_high = max(indicators.highs[-lookback - 1 : -1])
    previous_low = min(indicators.lows[-lookback - 1 : -1])
    breakout_distance_atr = min(
        abs(indicators.close - previous_high) / indicators.atr,
        abs(indicators.close - previous_low) / indicators.atr,
    )
    breakout_proximity_score = clamp01(
        1 - breakout_distance_atr / config.scoring.max_breakout_distance_atr
    )
    return max(mean_distance_score, breakout_proximity_score)


def _roc(closes: list[float], window: int) -> float:
    previous = closes[-window - 1]
    return 0.0 if previous == 0 else (closes[-1] - previous) / previous


def _average_bools(values: list[bool]) -> float:
    return sum(1.0 for value in values if value) / len(values)


def _percentile_rank(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(1 for item in values if item <= value) / len(values)


def _replace_position(position: Position, **changes) -> Position:
    data = position.__dict__.copy()
    data.update(changes)
    return Position(**data)


def _select_setup(regime: Regime) -> Setup | None:
    if regime == Regime.TREND:
        return Setup.CONTINUATION
    if regime == Regime.RANGE:
        return Setup.MEAN_REVERSION
    if regime == Regime.BREAKOUT:
        return Setup.MOMENTUM
    return None


def _hold_decision(symbol: str, regime: Regime, guardrail, reason: str) -> dict:
    return {
        "action": "ENTRY_HOLD",
        "reasoning": f"Deterministic entry blocked: regime={regime.value}; {reason}.",
        "position_size_usd": 0.0,
        "stop_loss_price": None,
        "take_profit_price": None,
        "leverage": None,
        "regime": regime.value,
        "quant_guardrail": guardrail.to_prompt_dict() if guardrail else None,
        "execution_result": None,
        "execution_status": "pending",
        "symbol": symbol,
    }
