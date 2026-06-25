"""Best-effort PositionPlan persistence."""

from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select

from database.database import get_session_maker
from database.models import PositionPlan
from trading.symbols import same_symbol

logger = logging.getLogger("AlphaTransformer")


async def get_open_plan(symbol: str, position: Any | None = None, side: str | None = None) -> PositionPlan | None:
    try:
        async with get_session_maker()() as session:
            return await _open_plan(session, symbol, _position_side(position) or side)
    except Exception as exc:
        logger.error("PositionPlan read failed for %s: %s", symbol, exc)
        return None


async def get_recent_plans(symbol: str, limit: int = 20) -> list[PositionPlan]:
    try:
        async with get_session_maker()() as session:
            stmt = select(PositionPlan).order_by(PositionPlan.id.desc()).limit(limit * 3)
            result = await session.execute(stmt)
            return [plan for plan in result.scalars().all() if same_symbol(plan.symbol, symbol)][:limit]
    except Exception as exc:
        logger.error("PositionPlan recent read failed for %s: %s", symbol, exc)
        return []


async def update_open_plan(symbol: str, position: Any, shadow: dict[str, Any]) -> None:
    try:
        async with get_session_maker()() as session:
            side = _position_side(position)
            plan = await _open_plan(session, symbol, side, position=position)
            if plan is None:
                plan = PositionPlan(
                    position_id=f"SHADOW_ORPHAN:{symbol}:{side}:{getattr(position, 'entry_price', '')}:{getattr(position, 'size', '')}",
                    symbol=symbol,
                    side=side or "",
                    status="OPEN",
                    entry_time=datetime.now(),
                    entry_price=getattr(position, "entry_price", None),
                    entry_regime=shadow.get("active_regime"),
                    active_regime=shadow.get("active_regime"),
                )
                session.add(plan)
            _apply_shadow(plan, shadow, position)
            await session.commit()
    except Exception as exc:
        logger.error("PositionPlan update failed for %s: %s", symbol, exc)


async def record_execution_plans(symbol_decisions: dict[str, dict]) -> None:
    for symbol, decision in symbol_decisions.items():
        result = decision.get("execution_result") or {}
        if result.get("status") != "success":
            continue
        action = result.get("action") or decision.get("action")
        if action in {"OPEN_LONG", "OPEN_SHORT"}:
            await upsert_open_plan(symbol, decision, result)
        elif action in {"CLOSE_LONG", "CLOSE_SHORT"}:
            await close_plan(symbol, decision, result)


async def upsert_open_plan(symbol: str, decision: dict[str, Any], result: dict[str, Any]) -> None:
    try:
        async with get_session_maker()() as session:
            position_id = _position_id(symbol, result)
            plan = (await session.execute(select(PositionPlan).where(PositionPlan.position_id == position_id))).scalar_one_or_none()
            if plan is None:
                plan = PositionPlan(position_id=position_id, symbol=symbol, side=_side_from_action(result.get("action") or decision.get("action")))
                session.add(plan)
            _apply_entry(plan, decision, result)
            await session.commit()
    except Exception as exc:
        logger.error("PositionPlan open write failed for %s: %s", symbol, exc)


async def close_plan(symbol: str, decision: dict[str, Any], result: dict[str, Any]) -> None:
    try:
        async with get_session_maker()() as session:
            plan = await _matching_open_plan(session, symbol, decision, result)
            if plan is None:
                logger.warning(
                    "PositionPlan close could not map order_id=%s symbol=%s side=%s",
                    result.get("order_id"),
                    symbol,
                    _side_from_action(result.get("action") or decision.get("action")),
                )
                return
            _apply_close(plan, decision, result)
            await session.commit()
    except Exception as exc:
        logger.error("PositionPlan close write failed for %s: %s", symbol, exc)


async def reconcile_flat_position(
    symbol: str,
    side: str,
    *,
    order_id: str | None = None,
    reason: str = "exchange_flat_reconciliation",
) -> None:
    try:
        async with get_session_maker()() as session:
            plans = await _open_plans(session, symbol, side)
            if not plans:
                logger.warning(
                    "PositionPlan flat reconciliation found no OPEN plan order_id=%s symbol=%s side=%s",
                    order_id,
                    symbol,
                    side,
                )
                return
            for plan in plans:
                _apply_close(
                    plan,
                    {"exit_class": "EXCHANGE_FLAT", "reasoning": reason},
                    {"order_id": order_id, "action": f"CLOSE_{side.upper()}"},
                )
                logger.warning(
                    "PositionPlan flat reconciliation closed stale plan position_id=%s order_id=%s symbol=%s side=%s",
                    plan.position_id,
                    order_id,
                    symbol,
                    side,
                )
            await session.commit()
    except Exception as exc:
        logger.error("PositionPlan flat reconciliation failed for %s %s: %s", symbol, side, exc)


async def reconcile_flat_symbol(
    symbol: str,
    *,
    reason: str = "exchange_flat_reconciliation",
) -> None:
    try:
        async with get_session_maker()() as session:
            plans = await _open_plans(session, symbol)
            for plan in plans:
                _apply_close(
                    plan,
                    {"exit_class": "EXCHANGE_FLAT", "reasoning": reason},
                    {"action": f"CLOSE_{plan.side}"},
                )
                logger.warning(
                    "PositionPlan flat reconciliation closed stale plan position_id=%s symbol=%s side=%s",
                    plan.position_id,
                    symbol,
                    plan.side,
                )
            if plans:
                await session.commit()
    except Exception as exc:
        logger.error("PositionPlan flat symbol reconciliation failed for %s: %s", symbol, exc)


async def _open_plan(
    session,
    symbol: str,
    side: str | None = None,
    *,
    position: Any | None = None,
) -> PositionPlan | None:
    plans = await _open_plans(session, symbol, side)
    if position is not None:
        matched = _fallback_match(plans, position)
        if matched is not None:
            return matched
    return plans[0] if plans else None


async def _open_plans(session, symbol: str, side: str | None = None) -> list[PositionPlan]:
    stmt = select(PositionPlan).where(PositionPlan.status == "OPEN").order_by(PositionPlan.id.desc())
    result = await session.execute(stmt)
    side = side.upper() if side else None
    return [
        plan
        for plan in result.scalars().all()
        if same_symbol(plan.symbol, symbol) and (side is None or plan.side == side)
    ]


async def _matching_open_plan(
    session,
    symbol: str,
    decision: dict[str, Any],
    result: dict[str, Any],
) -> PositionPlan | None:
    side = _side_from_action(result.get("action") or decision.get("action"))
    plans = await _open_plans(session, symbol, side)
    if not plans:
        return None
    candidate_position_id = result.get("position_id") or (result.get("position_state") or {}).get("position_id")
    if candidate_position_id:
        matched = next((plan for plan in plans if plan.position_id == str(candidate_position_id)), None)
        if matched is not None:
            return matched
    candidate_entry_order_id = result.get("entry_order_id") or decision.get("entry_order_id")
    if candidate_entry_order_id:
        matched = next((plan for plan in plans if plan.entry_order_id == str(candidate_entry_order_id)), None)
        if matched is not None:
            return matched
    position = result.get("position_state")
    if isinstance(position, dict):
        matched = _fallback_match(plans, SimpleNamespace(**position))
        if matched is not None:
            return matched
    if len(plans) == 1:
        return plans[0]
    logger.warning(
        "PositionPlan close ambiguous order_id=%s symbol=%s side=%s open_plans=%s",
        result.get("order_id"),
        symbol,
        side,
        [plan.position_id for plan in plans],
    )
    return None


def _apply_entry(plan: PositionPlan, decision: dict[str, Any], result: dict[str, Any]) -> None:
    state = result.get("position_state") or {}
    guardrail = decision.get("quant_guardrail") or {}
    shadow = decision.get("stability_shadow") or {}
    plan.symbol = decision.get("symbol") or result.get("symbol") or plan.symbol
    plan.side = _side_from_action(result.get("action") or decision.get("action"))
    plan.status = "OPEN"
    plan.entry_order_id = str(result.get("order_id")) if result.get("order_id") else plan.entry_order_id
    plan.entry_time = datetime.now()
    plan.entry_price = result.get("price") or state.get("entry_price") or guardrail.get("reference_price")
    plan.entry_regime = decision.get("regime") or shadow.get("active_regime")
    plan.entry_setup = decision.get("setup") or shadow.get("setup")
    plan.entry_lifecycle = decision.get("lifecycle") or shadow.get("lifecycle")
    plan.entry_direction_bias = guardrail.get("direction_bias")
    plan.entry_total_score = guardrail.get("total_score")
    plan.entry_long_score = _score_total(guardrail.get("long_score"))
    plan.entry_short_score = _score_total(guardrail.get("short_score"))
    plan.entry_confidence = shadow.get("raw_ai_confidence")
    plan.active_regime = plan.entry_regime
    plan.stable_direction = plan.entry_direction_bias
    plan.initial_stop_loss = decision.get("stop_loss_price") or state.get("stop_loss")
    plan.current_stop_loss = plan.initial_stop_loss
    plan.take_profit = decision.get("take_profit_price") or state.get("take_profit")
    plan.risk_per_unit = abs(plan.entry_price - plan.initial_stop_loss) if plan.entry_price and plan.initial_stop_loss else None
    plan.expected_min_hold_cycles = _lifecycle_defaults(plan.entry_lifecycle).get("min_hold_cycles")
    plan.expected_review_cycles = _lifecycle_defaults(plan.entry_lifecycle).get("expected_review_cycles")
    plan.max_hold_cycles_if_no_profit = _lifecycle_defaults(plan.entry_lifecycle).get("max_hold_cycles_if_no_profit")
    plan.cooldown_state = {"mode": "shadow", "active": False}
    plan.profit_protection_state = {"mode": "shadow"}
    plan.updated_at = datetime.now()


def _apply_close(plan: PositionPlan, decision: dict[str, Any], result: dict[str, Any]) -> None:
    plan.status = "CLOSED"
    plan.close_time = datetime.now()
    plan.close_order_id = str(result.get("order_id")) if result.get("order_id") else None
    plan.position_health = "CLOSED"
    plan.last_exit_class = decision.get("exit_class")
    plan.last_exit_reason = decision.get("exit_block_reason") or decision.get("reasoning")
    plan.updated_at = datetime.now()


def _apply_shadow(plan: PositionPlan, shadow: dict[str, Any], position: Any) -> None:
    plan.active_regime = shadow.get("active_regime")
    plan.stable_direction = shadow.get("stable_direction")
    plan.stable_total_score = shadow.get("stable_total_score")
    plan.stable_long_score = shadow.get("stable_long_score")
    plan.stable_short_score = shadow.get("stable_short_score")
    plan.instability_index = shadow.get("instability_index")
    plan.position_health = shadow.get("position_health") or plan.position_health
    plan.challenge_score = shadow.get("challenge_score") or 0.0
    plan.challenge_evidence_json = shadow.get("challenge_evidence")
    plan.no_new_evidence_cycles = shadow.get("no_new_evidence_cycles") or 0
    plan.challenge_streak = plan.challenge_streak + 1 if shadow.get("challenge_evidence") else 0
    plan.last_challenge_time = datetime.now() if shadow.get("challenge_evidence") else plan.last_challenge_time
    plan.profit_protection_state = shadow.get("profit_protection_state")
    plan.cooldown_state = shadow.get("cooldown_state")
    plan.last_exit_class = shadow.get("exit_class")
    plan.last_exit_reason = shadow.get("exit_block_reason")
    plan.warmup = int(bool(shadow.get("warmup")))
    plan.cycles_held += 1
    plan.entry_price = plan.entry_price or getattr(position, "entry_price", None)
    plan.peak_profit_pct = max(plan.peak_profit_pct or 0.0, float(getattr(position, "percentage_pnl", 0.0) or 0.0))
    profit_r = shadow.get("profit_protection_state", {}).get("profit_r") if isinstance(shadow.get("profit_protection_state"), dict) else None
    if profit_r is not None:
        plan.peak_profit_r = max(plan.peak_profit_r or 0.0, profit_r)
    plan.updated_at = datetime.now()


def _position_id(symbol: str, result: dict[str, Any]) -> str:
    state = result.get("position_state") or {}
    return str(
        result.get("position_id")
        or state.get("position_id")
        or result.get("order_id")
        or f"{symbol}:{state.get('side')}:{state.get('entry_price')}:{state.get('size') or result.get('quantity')}"
    )


def _position_side(position: Any | None) -> str | None:
    if position is None:
        return None
    side = getattr(position, "side", None)
    return str(side).upper() if side else None


def _fallback_match(plans: list[PositionPlan], position: Any) -> PositionPlan | None:
    entry_price = getattr(position, "entry_price", None)
    if entry_price is None:
        return None
    for plan in plans:
        if _close_enough(plan.entry_price, entry_price):
            return plan
    return None


def _close_enough(left: Any, right: Any, pct: float = 0.001) -> bool:
    try:
        left_float = float(left)
        right_float = float(right)
    except (TypeError, ValueError):
        return False
    if left_float == right_float:
        return True
    basis = max(abs(left_float), abs(right_float), 1.0)
    return abs(left_float - right_float) / basis <= pct


def _side_from_action(action: str | None) -> str:
    if action and action.endswith("LONG"):
        return "LONG"
    if action and action.endswith("SHORT"):
        return "SHORT"
    return ""


def _score_total(value) -> float | None:
    return value.get("total") if isinstance(value, dict) else None


def _lifecycle_defaults(lifecycle: str | None) -> dict[str, int]:
    return {
        "SCALP": {"min_hold_cycles": 1, "expected_review_cycles": 2, "max_hold_cycles_if_no_profit": 10},
        "SHORT": {"min_hold_cycles": 3, "expected_review_cycles": 5, "max_hold_cycles_if_no_profit": 40},
        "SWING": {"min_hold_cycles": 10, "expected_review_cycles": 20, "max_hold_cycles_if_no_profit": 480},
    }.get(lifecycle or "", {})
