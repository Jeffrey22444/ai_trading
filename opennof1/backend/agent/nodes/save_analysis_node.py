"""
Save Analysis Node - Save complete analysis results to database
"""
import logging
from agent.state import AgentState
from agent.models import analysis_service

logger = logging.getLogger("AlphaTransformer")


async def save_analysis_node(state: AgentState) -> AgentState:
    """保存完整分析结果到数据库"""
    try:
        await analysis_service.save_analysis(
            symbol_decisions=state["symbol_decisions"],
            overall_summary=state.get("overall_summary"),
            error=state.get("error")
        )
        
        logger.info("完整分析已保存到数据库")
        return state
        
    except Exception as e:
        logger.error(f"保存分析失败: {e}")
        state["error"] = f"保存分析失败: {str(e)}"
        return state