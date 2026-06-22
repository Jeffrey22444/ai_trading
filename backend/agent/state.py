"""
Optimized agent state for multi-symbol trading workflow
Each symbol has independent action and execution tracking
"""
from typing import TypedDict, Dict, Any, Optional


class SymbolDecision(TypedDict):
    """单个交易标的的决策和执行结果"""
    action: str  # OPEN_*, CLOSE_*, ENTRY_HOLD, POSITION_HOLD
    reasoning: str  # AI reasoning for this symbol
    execution_result: Optional[Dict[str, Any]]  # 交易执行结果
    execution_status: str  # "pending", "success", "failed"


class AgentState(TypedDict):
    """多标的交易智能体状态"""
    
    # 多标的决策 (filled by analysis node)
    symbol_decisions: Dict[str, SymbolDecision]  # symbol -> decision mapping
    
    # 整体分析摘要
    overall_summary: Optional[str]  # AI的整体市场分析
    
    # 错误处理
    error: Optional[str]  # Analysis or execution error

    # Deterministic regime runtime metadata
    strategy_runtime: Optional[Dict[str, Any]]
    regime_classification: Optional[Dict[str, Any]]
    deterministic_decisions: Optional[Dict[str, Any]]
    regime_classification_result: Optional[Any]
    analysis_context: Optional[Dict[str, Any]]
