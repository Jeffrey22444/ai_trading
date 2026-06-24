"""
Save Analysis Node - Save complete analysis results to database
"""
import logging
from agent.state import AgentState
from agent.models import analysis_service
from agent.stability.persistence import record_execution_plans

logger = logging.getLogger("AlphaTransformer")


async def save_analysis_node(state: AgentState) -> AgentState:
    """保存完整分析结果到数据库"""
    try:
        payload = dict(state["symbol_decisions"])
        if (
            state.get("strategy_runtime")
            or state.get("regime_classification")
            or state.get("stability_shadow")
        ):
            payload["_metadata"] = {
                "strategy_runtime": state.get("strategy_runtime"),
                "regime_classification": state.get("regime_classification"),
                "deterministic_decisions": state.get("deterministic_decisions"),
                "stability_shadow": state.get("stability_shadow"),
            }

        await record_execution_plans(state["symbol_decisions"])
        await analysis_service.save_analysis(
            symbol_decisions=payload,
            overall_summary=state.get("overall_summary"),
            error=state.get("error")
        )
        
        logger.info("完整分析已保存到数据库")
        return state
        
    except Exception as e:
        logger.error(f"保存分析失败: {e}")
        state["error"] = f"保存分析失败: {str(e)}"
        return state
