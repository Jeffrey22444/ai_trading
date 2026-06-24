import logging
from datetime import datetime

from agent.portfolio.position_manager import PositionState, update_position_state
from agent.state import AgentState
from agent.stability.engine import (
    apply_entry_gate,
    apply_exit_enforcement,
    build_observation,
    compute_shadow_state,
)
from agent.stability.persistence import get_open_plan, get_recent_plans, update_open_plan
from config.settings import config
from trading.factory import get_trader
from trading.symbols import same_symbol

logger = logging.getLogger("AlphaTransformer")


async def exit_decision_node(state: AgentState) -> AgentState:
    """Position manager runs after entry AI and before execution."""
    try:
        trader = get_trader()
        positions = await trader.get_positions()
        now = datetime.now()

        for symbol, decision in state["symbol_decisions"].items():
            position = next((pos for pos in positions if same_symbol(pos.symbol, symbol)), None)
            _split_hold(decision, position)
            if position is None:
                continue

            if config.stability_refactor.mode == "shadow":
                position_state = update_position_state(position, now)
                decision["position_state"] = _state_dict(position_state)
                if position_state.stop_loss is not None:
                    decision["stop_loss_price"] = position_state.stop_loss

                if position_state.should_exit:
                    decision["action"] = (
                        "CLOSE_LONG" if str(position.side).upper() == "LONG" else "CLOSE_SHORT"
                    )
                    decision["position_size_usd"] = 0.0
                    decision["take_profit_price"] = None
                    decision["leverage"] = None
                    decision["reasoning"] = (
                        f"{decision.get('reasoning', '')}\n利润保护触发: peak={position_state.peak_profit_pct:.2f}%, "
                        f"current={position_state.unrealized_pnl_pct:.2f}%, trailing={position_state.trailing_stop:.2f}%，"
                        "系统平仓保护利润。"
                    )

        await _attach_stability(state, positions)
        return state
    except Exception as exc:
        logger.error(f"退出决策节点失败: {exc}")
        state["error"] = str(exc)
        return state


def _split_hold(decision: dict, position) -> None:
    action = decision.get("action")
    if position is None:
        if action in {"HOLD", "POSITION_HOLD", "CLOSE_LONG", "CLOSE_SHORT"}:
            decision["action"] = "ENTRY_HOLD"
        return

    if action in {"HOLD", "ENTRY_HOLD", "OPEN_LONG", "OPEN_SHORT"}:
        decision["action"] = "POSITION_HOLD"
        if action in {"OPEN_LONG", "OPEN_SHORT"}:
            decision["reasoning"] = (
                f"{decision.get('reasoning', '')}\nENTRY AI 信号不管理已有持仓，交给 EXIT/利润保护。"
            )


def _state_dict(state: PositionState) -> dict:
    return {
        "entry_price": state.entry_price,
        "current_price": state.current_price,
        "current_profit_pct": state.unrealized_pnl_pct,
        "peak_profit_pct": state.peak_profit_pct,
        "drawdown_pct": state.drawdown_from_peak_pct,
        "holding_time_seconds": state.holding_time_seconds,
        "regime": state.regime,
        "trailing_stop": state.trailing_stop,
        "stop_loss": state.stop_loss,
    }


async def _attach_stability(state: AgentState, positions) -> None:
    if not config.stability_refactor.enabled:
        return
    classifications = state.get("regime_classification") or {}
    context = state.get("analysis_context") or {}
    indicators_by_symbol = context.get("regime_indicators") or {}
    stability = {}
    for symbol, decision in state["symbol_decisions"].items():
        before = _behavior_snapshot(decision)
        try:
            position = next((pos for pos in positions if same_symbol(pos.symbol, symbol)), None)
            plan = await get_open_plan(symbol) if position else None
            observation = build_observation(
                symbol=symbol,
                decision=decision,
                regime_classification=classifications.get(symbol),
                indicators=indicators_by_symbol.get(symbol),
                config=config,
            )
            shadow = compute_shadow_state(
                observation=observation,
                previous_plan=plan,
                position=position,
                config=config.stability_refactor,
            )
            decision["stability_shadow"] = shadow
            if position:
                apply_exit_enforcement(decision, position, plan, shadow, config.stability_refactor)
                shadow["exit_class"] = decision.get("exit_class", shadow.get("exit_class"))
                shadow["exit_allowed"] = decision.get("exit_allowed", shadow.get("exit_allowed"))
                shadow["exit_block_reason"] = decision.get("exit_block_reason", shadow.get("exit_block_reason"))
                shadow["profit_protection_state"] = decision.get("profit_protection_state", shadow.get("profit_protection_state"))
                await update_open_plan(symbol, position, shadow)
            else:
                recent = await get_recent_plans(symbol)
                apply_entry_gate(decision, shadow, recent, config.stability_refactor)
            stability[symbol] = shadow
        except Exception as exc:
            logger.error("stability refactor failed for %s: %s", symbol, exc)
        if config.stability_refactor.mode == "shadow" and before != _behavior_snapshot(decision):
            logger.error("shadow stability changed live decision fields for %s", symbol)
    state["stability_shadow"] = stability


def _behavior_snapshot(decision: dict) -> tuple:
    return (
        decision.get("action"),
        decision.get("position_size_usd"),
        decision.get("stop_loss_price"),
        decision.get("take_profit_price"),
        decision.get("leverage"),
        decision.get("order_intent"),
        decision.get("execution_result"),
    )
