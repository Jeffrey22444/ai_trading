"""Deterministic decision node: turns regime classification into symbol decisions."""

import logging

from agent.nodes.analysis_node import (
    RegimeClassification,
    build_deterministic_symbol_decisions,
)
from agent.state import AgentState

logger = logging.getLogger("AlphaTransformer")


async def deterministic_decision_node(state: AgentState) -> AgentState:
    """Final trading actions are produced here, not by the LLM."""
    try:
        context = state.get("analysis_context") or {}
        classification = state.get("regime_classification_result")
        if not context or not isinstance(classification, RegimeClassification):
            state["symbol_decisions"] = {}
            state["deterministic_decisions"] = {}
            state["error"] = state.get("error") or "deterministic decision context missing"
            return state

        decisions = build_deterministic_symbol_decisions(
            symbols=context["symbols"],
            total_balance=context["total_balance"],
            positions_by_symbol=context["positions_by_symbol"],
            quant_guardrails=context["quant_guardrails"],
            regime_indicators=context["regime_indicators"],
            regime_classification=classification,
        )
        state["symbol_decisions"] = decisions
        state["deterministic_decisions"] = decisions
        return state
    except Exception as exc:
        logger.error(f"deterministic decision failed: {exc}")
        state["symbol_decisions"] = {}
        state["deterministic_decisions"] = {}
        state["error"] = str(exc)
        return state
