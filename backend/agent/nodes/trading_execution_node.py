"""
Trading Execution Node - Execute real futures trading decisions
"""
import logging
from typing import Dict, Any
from datetime import datetime

from agent.state import AgentState
from trading.factory import get_trader
from trading.risk_guard import validate_open_decision
from trading.symbols import same_symbol
from config.settings import config

logger = logging.getLogger("AlphaTransformer")


async def trading_execution_node(state: AgentState) -> AgentState:
    """真实期货交易执行节点"""
    try:
        symbol_decisions = state["symbol_decisions"]
        trader = get_trader()
        
        logger.info(f"开始执行真实期货交易: {len(symbol_decisions)} 个标的")
        
        # 获取当前账户状态
        try:
            balance = await trader.get_balance()
            positions = await trader.get_positions()
            logger.info(f"账户余额: ${balance.total_balance}, 持仓数量: {len(positions)}")
        except Exception as e:
            logger.error(f"获取账户状态失败: {e}")
            state["error"] = f"获取账户状态失败: {str(e)}"
            return state
        
        # 先执行所有平仓操作，再执行所有开仓操作
        close_decisions = {}
        open_decisions = {}
        
        # 分离平仓和开仓决策
        for symbol, decision in symbol_decisions.items():
            action = decision["action"]
            if action in ["CLOSE_LONG", "CLOSE_SHORT"]:
                close_decisions[symbol] = decision
            elif action in ["OPEN_LONG", "OPEN_SHORT"]:
                open_decisions[symbol] = decision
            elif action in ["ENTRY_HOLD", "POSITION_HOLD", "HOLD"]:
                logger.info(f"{symbol}: {action} - 无需执行交易操作")
                decision["execution_result"] = {
                    "status": "success",
                    "action": action,
                    "symbol": symbol,
                    "message": "无需执行交易",
                    "timestamp": datetime.now().isoformat()
                }
                decision["execution_status"] = "completed"
        
        # 第一步：执行所有平仓操作
        for symbol, decision in close_decisions.items():
            try:
                execution_result = await _execute_futures_trading(
                    symbol, decision, trader, balance, positions
                )
                decision["execution_result"] = execution_result
                decision["execution_status"] = _execution_status(execution_result)
                
            except Exception as e:
                logger.error(f"执行 {symbol} 平仓失败: {e}")
                decision["execution_status"] = "failed"
                decision["execution_result"] = {
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        # 第二步：重新获取余额和持仓信息（平仓后可能有变化）
        if close_decisions:
            try:
                balance = await trader.get_balance()
                positions = await trader.get_positions()
                _mark_confirmed_closed(close_decisions, positions)
                logger.info(f"平仓后账户余额: ${balance.total_balance}, 持仓数量: {len(positions)}")
            except Exception as e:
                logger.error(f"重新获取账户状态失败: {e}")
        
        # 第三步：执行所有开仓操作
        for symbol, decision in open_decisions.items():
            try:
                execution_result = await _execute_futures_trading(
                    symbol, decision, trader, balance, positions
                )
                decision["execution_result"] = execution_result
                decision["execution_status"] = _execution_status(execution_result)
                
            except Exception as e:
                logger.error(f"执行 {symbol} 开仓失败: {e}")
                decision["execution_status"] = "failed"
                decision["execution_result"] = {
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        logger.info(f"期货交易执行完成: {len(symbol_decisions)} 个标的")
        return state
        
    except Exception as e:
        logger.error(f"期货交易执行节点失败: {e}")
        state["error"] = str(e)
        return state


async def _execute_futures_trading(symbol: str, decision: Dict[str, Any], trader, balance, positions) -> Dict[str, Any]:
    """执行单个标的的真实期货交易"""
    action = decision["action"]
    timestamp = datetime.now().isoformat()
    
    try:
        # 处理 hold 操作
        if action in {"ENTRY_HOLD", "POSITION_HOLD", "HOLD"}:
            logger.info(f"{symbol}: {action} - 无需执行交易操作")
            return {
                "status": "success",
                "action": action,
                "symbol": symbol,
                "message": "无需执行交易",
                "timestamp": timestamp
            }
        
        # 获取当前市场价格
        current_price = await trader.get_market_price(symbol)
        if current_price <= 0:
            raise ValueError(f"无法获取 {symbol} 的有效价格")
        
        # 获取当前持仓 (处理符号格式差异)
        current_position = None
        for pos in positions:
            if same_symbol(pos.symbol, symbol):
                current_position = pos
                break
        
        # 执行具体的交易操作
        if action == "OPEN_LONG":
            result = await _execute_open_long(symbol, decision, trader, current_price, balance)
        elif action == "OPEN_SHORT":
            result = await _execute_open_short(symbol, decision, trader, current_price, balance)
        elif action == "CLOSE_LONG":
            result = await _execute_close_long(symbol, decision, trader, current_position)
        elif action == "CLOSE_SHORT":
            result = await _execute_close_short(symbol, decision, trader, current_position)
        else:
            raise ValueError(f"不支持的交易操作: {action}")
        
        result["timestamp"] = timestamp
        return result
        
    except Exception as e:
        logger.error(f"执行 {symbol} {action} 失败: {e}")
        return {
            "status": "failed",
            "action": action,
            "symbol": symbol,
            "error": str(e),
            "timestamp": timestamp
        }


async def _execute_open_long(symbol: str, decision: Dict, trader, current_price: float, balance) -> Dict[str, Any]:
    """执行开多仓"""
    position_size_usd = decision.get("position_size_usd", 0)
    leverage = _decision_leverage(decision)
    
    # 获取止损止盈价格
    stop_loss_price = decision.get("stop_loss_price")
    take_profit_price = decision.get("take_profit_price")
    reference_price = _decision_reference_price(decision)

    try:
        position_size_usd = validate_open_decision(
            action="OPEN_LONG",
            position_size_usd=position_size_usd,
            current_price=current_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            available_balance=balance.available_balance,
            max_position_size_percent=config.default_risk.max_position_size_percent,
            testnet=config.exchange.testnet,
            allow_live_trading=config.exchange.allow_live_trading,
            reference_price=reference_price,
            max_entry_price_drift_pct=config.execution_safety.max_entry_price_drift_pct,
            max_chase_price_drift_pct=config.execution_safety.max_chase_price_drift_pct,
        )
    except ValueError as exc:
        return _open_reject_result("OPEN_LONG", symbol, str(exc), current_price, reference_price)
    quantity = position_size_usd / current_price
    
    # 执行开多仓（含止损止盈）
    order = await trader.open_long(
        symbol, quantity, leverage, stop_loss_price, take_profit_price
    )
    
    logger.info(f"开多仓成功: {symbol} 数量:{quantity} 杠杆:{leverage}x 价格:${current_price}")
    
    return {
        "status": "success",
        "action": "OPEN_LONG",
        "symbol": symbol,
        "quantity": quantity,
        "leverage": leverage,
        "price": current_price,
        "current_price": current_price,
        "reference_price": reference_price,
        "protection_verified": bool(order.get("protection_verified")),
        "protection_order_count": len(order.get("protection_orders", [])),
        "position_state": _active_position_state(
            symbol=symbol,
            side="LONG",
            lifecycle=decision.get("lifecycle"),
            entry_price=current_price,
            quantity=quantity,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
        ),
        "drift_pct": _drift_pct(current_price, reference_price),
        "chase_drift_pct": _directional_chase_drift_pct(
            "OPEN_LONG", current_price, reference_price
        ),
        "message": f"开多仓成功: {quantity} @ ${current_price}"
    }


async def _execute_open_short(symbol: str, decision: Dict, trader, current_price: float, balance) -> Dict[str, Any]:
    """执行开空仓"""
    position_size_usd = decision.get("position_size_usd", 0)
    leverage = _decision_leverage(decision)
    
    # 获取止损止盈价格
    stop_loss_price = decision.get("stop_loss_price")
    take_profit_price = decision.get("take_profit_price")
    reference_price = _decision_reference_price(decision)

    try:
        position_size_usd = validate_open_decision(
            action="OPEN_SHORT",
            position_size_usd=position_size_usd,
            current_price=current_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            available_balance=balance.available_balance,
            max_position_size_percent=config.default_risk.max_position_size_percent,
            testnet=config.exchange.testnet,
            allow_live_trading=config.exchange.allow_live_trading,
            reference_price=reference_price,
            max_entry_price_drift_pct=config.execution_safety.max_entry_price_drift_pct,
            max_chase_price_drift_pct=config.execution_safety.max_chase_price_drift_pct,
        )
    except ValueError as exc:
        return _open_reject_result("OPEN_SHORT", symbol, str(exc), current_price, reference_price)
    quantity = position_size_usd / current_price
    
    # 执行开空仓（含止损止盈）
    order = await trader.open_short(
        symbol, quantity, leverage, stop_loss_price, take_profit_price
    )
    
    logger.info(f"开空仓成功: {symbol} 数量:{quantity} 杠杆:{leverage}x 价格:${current_price}")
    
    return {
        "status": "success",
        "action": "OPEN_SHORT",
        "symbol": symbol,
        "quantity": quantity,
        "leverage": leverage,
        "price": current_price,
        "current_price": current_price,
        "reference_price": reference_price,
        "protection_verified": bool(order.get("protection_verified")),
        "protection_order_count": len(order.get("protection_orders", [])),
        "position_state": _active_position_state(
            symbol=symbol,
            side="SHORT",
            lifecycle=decision.get("lifecycle"),
            entry_price=current_price,
            quantity=quantity,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
        ),
        "drift_pct": _drift_pct(current_price, reference_price),
        "chase_drift_pct": _directional_chase_drift_pct(
            "OPEN_SHORT", current_price, reference_price
        ),
        "message": f"开空仓成功: {quantity} @ ${current_price}"
    }


async def _execute_close_long(symbol: str, decision: Dict, trader, current_position) -> Dict[str, Any]:
    """执行平多仓 - 直接全部平仓"""
    if not current_position or current_position.side != "LONG":
        raise ValueError(f"{symbol} 没有多头持仓可平")
    
    # 执行全部平仓
    await trader.close_long(symbol, 0)  # 0 表示全部平仓
    
    logger.info(f"平多仓成功: {symbol} 数量:{current_position.size}")
    
    return {
        "status": "success",
        "action": "CLOSE_LONG",
        "symbol": symbol,
        "quantity": current_position.size,
        "message": f"平多仓成功: {current_position.size}"
    }


async def _execute_close_short(symbol: str, decision: Dict, trader, current_position) -> Dict[str, Any]:
    """执行平空仓 - 直接全部平仓"""
    if not current_position or current_position.side != "SHORT":
        raise ValueError(f"{symbol} 没有空头持仓可平")
    
    # 执行全部平仓
    await trader.close_short(symbol, 0)  # 0 表示全部平仓
    
    logger.info(f"平空仓成功: {symbol} 数量:{current_position.size}")
    
    return {
        "status": "success",
        "action": "CLOSE_SHORT",
        "symbol": symbol,
        "quantity": current_position.size,
        "message": f"平空仓成功: {current_position.size}"
    }


def _decision_leverage(decision: Dict[str, Any]) -> int:
    leverage = int(decision.get("leverage") or config.exchange.default_leverage)
    if leverage < 1:
        raise ValueError("杠杆必须大于等于 1")
    if leverage > config.leverage.max_leverage:
        raise ValueError(f"杠杆超过配置上限 {config.leverage.max_leverage}x")
    return leverage


def _execution_status(execution_result: Dict[str, Any]) -> str:
    if execution_result["status"] == "success":
        return "completed"
    if execution_result["status"] == "blocked":
        return "blocked"
    return "failed"


def _decision_reference_price(decision: Dict[str, Any]) -> float | None:
    reference_price = decision.get("reference_price")
    if reference_price is None and isinstance(decision.get("quant_guardrail"), dict):
        reference_price = decision["quant_guardrail"].get("reference_price")
    return float(reference_price) if reference_price is not None else None


def _open_reject_result(
    action: str,
    symbol: str,
    reason: str,
    current_price: float,
    reference_price: float | None,
) -> Dict[str, Any]:
    return {
        "status": "blocked",
        "action": action,
        "symbol": symbol,
        "error": reason,
        "reject_reason": reason,
        "blocked_by": "risk_guard",
        "current_price": current_price,
        "reference_price": reference_price,
        "drift_pct": _drift_pct(current_price, reference_price),
        "chase_drift_pct": _directional_chase_drift_pct(
            action, current_price, reference_price
        ),
    }


def _drift_pct(current_price: float, reference_price: float | None) -> float | None:
    if reference_price is None or reference_price <= 0:
        return None
    return abs(current_price - reference_price) / reference_price


def _directional_chase_drift_pct(
    action: str, current_price: float, reference_price: float | None
) -> float | None:
    if reference_price is None or reference_price <= 0:
        return None
    if action == "OPEN_LONG":
        return max(0.0, (current_price - reference_price) / reference_price)
    if action == "OPEN_SHORT":
        return max(0.0, (reference_price - current_price) / reference_price)
    return None


def _active_position_state(
    *,
    symbol: str,
    side: str,
    lifecycle: str | None,
    entry_price: float,
    quantity: float,
    stop_loss_price: float,
    take_profit_price: float,
) -> dict:
    return {
        "symbol": symbol,
        "side": side,
        "lifecycle": lifecycle,
        "state": "ACTIVE",
        "failure_mode": "NONE",
        "entry_price": entry_price,
        "size": quantity,
        "stop_loss": stop_loss_price,
        "take_profit": take_profit_price,
        "opened_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "capital_released": False,
    }


def _mark_confirmed_closed(close_decisions: dict, positions) -> None:
    for symbol, decision in close_decisions.items():
        still_open = any(same_symbol(pos.symbol, symbol) for pos in positions)
        if still_open or decision.get("execution_status") != "completed":
            continue
        result = decision.setdefault("execution_result", {})
        result["position_state"] = {
            "symbol": symbol,
            "state": "CLOSED",
            "failure_mode": "NONE",
            "updated_at": datetime.now().isoformat(),
            "capital_released": True,
        }
