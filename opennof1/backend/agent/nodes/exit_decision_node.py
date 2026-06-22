import logging
from datetime import datetime

from agent.portfolio.position_manager import PositionState, update_position_state
from agent.state import AgentState
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
