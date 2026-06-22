"""
LangGraph workflow for multi-symbol trading agent with modular nodes
"""
import logging
from typing import List
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes.analysis_node import analysis_node
from agent.nodes.deterministic_decision_node import deterministic_decision_node
from agent.nodes.exit_decision_node import exit_decision_node
from agent.nodes.trading_execution_node import trading_execution_node
from agent.nodes.save_analysis_node import save_analysis_node

logger = logging.getLogger("AlphaTransformer")


def create_trading_workflow(tools: List):
    """Create trading workflow with modular analysis and execution nodes"""
    
    # Create workflow
    workflow = StateGraph(AgentState)
    
    # Create nodes
    analysis = analysis_node(tools)
    
    # 添加节点到工作流程
    workflow.add_node("regime_classification", analysis)
    workflow.add_node("deterministic_decision", deterministic_decision_node)
    workflow.add_node("exit_decision", exit_decision_node)
    workflow.add_node("trading_execution", trading_execution_node)
    workflow.add_node("save_analysis", save_analysis_node)
    
    # 定义工作流程边
    workflow.add_edge("regime_classification", "deterministic_decision")
    workflow.add_edge("deterministic_decision", "exit_decision")
    workflow.add_edge("exit_decision", "trading_execution")
    workflow.add_edge("trading_execution", "save_analysis")
    workflow.add_edge("save_analysis", END)
    
    # 设置入口点
    workflow.set_entry_point("regime_classification")
    
    return workflow.compile()
