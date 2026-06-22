"""
Analysis Node - ReAct Agent for technical analysis and decision making
"""

import json
import logging
import time
from typing import List, Optional
from datetime import datetime
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.quant.guardrails import build_quant_guardrails
from agent.quant.indicators import build_market_context
from agent.regime.engine import (
    build_entry_decision_from_guardrail,
    normalize_regime,
    score_direction,
    score_entry,
)
from agent.regime.market import indicator_set_from_context
from agent.regime.models import Regime, RegimeOutput
from agent.state import AgentState
from config.settings import config
from services.prompt_service import (
    get_regime_classifier_prompt,
    get_regime_prompt_status,
    reject_trade_action_fields,
)
from trading.symbols import from_exchange_symbol, same_symbol


class DeterministicSymbolDecision(BaseModel):
    """Internal deterministic symbol decision."""

    symbol: str = Field(description="逻辑交易标的，例如 'BTC'")
    action: str
    reasoning: str
    position_size_usd: float = 0.0
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    leverage: Optional[int] = None

    @field_validator("position_size_usd", mode="before")
    @classmethod
    def normalize_optional_position_size(cls, value):
        return 0.0 if value is None else value

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return from_exchange_symbol(value)


class SymbolRegimeDecision(BaseModel):
    """AI regime classification for one symbol."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(description="逻辑交易标的，例如 'BTC'")
    regime: Regime = Field(description="TREND, RANGE, BREAKOUT, or UNKNOWN")
    confidence: float = Field(ge=0.0, le=1.0)
    expires_at: int = Field(description="Unix timestamp seconds")
    evidence: list[str] = Field(default_factory=list)
    reasoning: str = Field(default="")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return from_exchange_symbol(value)

    @field_validator("expires_at", mode="before")
    @classmethod
    def normalize_expires_at(cls, value):
        if isinstance(value, datetime):
            return int(value.timestamp())
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            return int(datetime.fromisoformat(normalized).timestamp())
        return value


class RegimeClassification(BaseModel):
    """AI output is advisory regime classification only."""

    model_config = ConfigDict(extra="forbid")

    symbol_regimes: List[SymbolRegimeDecision] = Field(
        description="每个标的的 regime 分类"
    )
    market_summary: str | None = None
    overall_summary: str = Field(default="")

    def model_post_init(self, __context) -> None:
        if not self.overall_summary and self.market_summary:
            self.overall_summary = self.market_summary


logger = logging.getLogger("AlphaTransformer")


# 基础 ReAct agent LLM - 支持自定义服务商
def create_llm():
    """创建LLM实例，支持不同的AI服务商"""
    llm_config = {
        "model": config.agent.model_name,
        "api_key": config.agent.api_key,
        "temperature": 0.1
    }
    
    # 如果配置了自定义base_url，则使用
    if config.agent.base_url:
        llm_config["base_url"] = config.agent.base_url
    
    return ChatOpenAI(**llm_config)

llm = create_llm()

# 结构化输出 LLM - 用于最终决策
def create_structured_llm():
    """创建结构化输出LLM实例，兼容不同AI服务商"""
    llm_config = {
        "model": config.agent.model_name,
        "api_key": config.agent.api_key,
        "temperature": 0.0
    }
    
    if config.agent.base_url:
        llm_config["base_url"] = config.agent.base_url
    
    llm = ChatOpenAI(**llm_config)
    
    # 检查是否支持原生结构化输出 (仅OpenAI gpt-4o系列)
    if config.agent.model_name.startswith("gpt-4o") and config.agent.base_url is None:
        return llm.with_structured_output(RegimeClassification)
    else:
        # 其他模型使用JSON mode或普通文本模式
        return llm

def supports_native_structured_output():
    """检查是否支持原生结构化输出"""
    return config.agent.model_name.startswith("gpt-4o") and config.agent.base_url is None

structured_llm = create_structured_llm()


def parse_regime_response(
    response_text: str, required_symbols: Optional[list[str]] = None
) -> RegimeClassification:
    """Parse JSON regime output and degrade to UNKNOWN on errors."""
    import re

    symbols = required_symbols or list(config.agent.symbols)
    now = int(time.time())

    def unknown(summary: str) -> RegimeClassification:
        return RegimeClassification(
            symbol_regimes=[
                SymbolRegimeDecision(
                    symbol=symbol,
                    regime=Regime.UNKNOWN,
                    confidence=0.0,
                    expires_at=now,
                    evidence=["invalid_regime_output"],
                    reasoning=summary,
                )
                for symbol in symbols
            ],
            overall_summary=summary,
        )

    json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
    json_str = json_match.group(1) if json_match else response_text.strip()
    try:
        payload = json.loads(json_str)
        if reject_trade_action_fields(payload):
            return unknown("regime output contained trading decision fields")
        parsed = RegimeClassification(**payload)
    except Exception as e:
        logger.error(f"解析 regime JSON 响应失败: {e}, 原始响应: {response_text}")
        return unknown("regime JSON 解析失败，全部 UNKNOWN")

    by_symbol = {item.symbol: item for item in parsed.symbol_regimes}
    normalized = []
    for symbol in symbols:
        item = by_symbol.get(symbol)
        if item is None:
            normalized.append(
                SymbolRegimeDecision(
                    symbol=symbol,
                    regime=Regime.UNKNOWN,
                    confidence=0.0,
                    expires_at=now,
                    evidence=["missing_symbol"],
                    reasoning="missing symbol regime",
                )
            )
            continue
        if (
            item.confidence < config.regime_execution.regime.min_confidence
            or item.expires_at < now
        ):
            item.regime = Regime.UNKNOWN
        normalized.append(item)
    return RegimeClassification(
        symbol_regimes=normalized,
        overall_summary=parsed.overall_summary or parsed.market_summary or "",
    )


def analysis_node(tools: List):
    """Create analysis node function with structured output"""
    react_agent = create_react_agent(llm, tools)

    async def node(state: AgentState) -> AgentState:
        """ReAct 分析节点 - AI 主动调用工具获取技术数据并做出决策"""
        try:
            logger.info("开始 ReAct 分析...")
            prompt_status = await get_regime_prompt_status()
            state["strategy_runtime"] = prompt_status.to_dict()
            if not prompt_status.compatible:
                state["symbol_decisions"] = {}
                state["overall_summary"] = prompt_status.message
                state["error"] = prompt_status.error_code
                return state

            # 获取配置中的交易标的
            symbols = config.agent.symbols
            symbols_list = ", ".join(symbols)

            # 获取当前账户状态
            from trading.factory import get_trader

            trader = get_trader()
            balance = await trader.get_balance()
            positions = await trader.get_positions()
            quant_guardrails = build_quant_guardrails(
                symbols, balance.available_balance, config
            )
            regime_indicators = {
                symbol: indicator_set_from_context(
                    build_market_context(symbol, config.agent.timeframes),
                    config.regime_execution,
                )
                for symbol in symbols
            }

            # 格式化账户信息
            balance_info = f"总余额: ${balance.total_balance:.2f}, 可用余额: ${balance.available_balance:.2f}, 未实现盈亏: ${balance.unrealized_pnl:.2f}"

            positions_info = ""
            if positions:
                position_details = []
                for pos in positions:
                    position_details.append(
                        f"{pos.symbol}: {pos.side} {pos.size} (盈亏: ${pos.unrealized_pnl:.2f})"
                    )
                positions_info = f"当前持仓: {', '.join(position_details)}"
            else:
                positions_info = "当前持仓: 无"

            # 第一步：ReAct agent 分析市场数据
            analysis_prompt = f"""
            请分析以下交易标的的当前市场状况：
            
            标的: {symbols_list}
            
            请使用可用的技术分析工具来获取 K 线数据和技术指标。
            分析完成后，为每个标的提供详细的市场分析结果。
            指标包括：RSI、MACD、EMA、ATR、NATR（波动率指标）、最近支撑/阻力位、持仓量 OI、资金费率 Funding。
            也需要对各个 timeframe 的指标进行细化分析和汇总，并把衍生品上下文一起纳入判断。
            
            时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """

            # 运行 ReAct agent 进行技术分析
            analysis_result = await react_agent.ainvoke(
                {"messages": [HumanMessage(content=analysis_prompt)]}
            )

            analysis_content = (
                analysis_result["messages"][-1].content
                if analysis_result["messages"]
                else ""
            )
            logger.info(f"{analysis_content}")

            # 第二步：AI 只做 regime classification，交易动作由确定性代码生成
            
            # 系统提示词（固定结构）
            system_prompt = f"""基于以下信息为每个标的做 regime 分类：

标的: {symbols_list}

当前账户状态:
{balance_info}
{positions_info}

技术分析结果:
{analysis_content}

你只能输出 regime 分类；不能输出交易动作，不能决定入场、退出、仓位、保护价格或风险。
regime 只能是 TREND、RANGE、BREAKOUT、UNKNOWN。
如果证据不足、confidence < {config.regime_execution.regime.min_confidence}，或分类不稳定，输出 UNKNOWN。
expires_at 必须是 ISO-8601 时间，不能早于当前时间。"""

            regime_prompt = await get_regime_classifier_prompt()
            
            # 根据是否支持原生结构化输出来调整处理
            if supports_native_structured_output():
                # OpenAI gpt-4o 使用原生结构化输出
                regime_classification = await structured_llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=regime_prompt)
                ])
            else:
                # 其他模型使用JSON格式
                json_schema = {
                    "symbol_regimes": [
                        {
                            "symbol": "string",
                            "regime": "TREND|RANGE|BREAKOUT|UNKNOWN",
                            "confidence": "number between 0 and 1",
                            "evidence": ["short_tag"],
                            "expires_at": "ISO-8601 timestamp"
                        }
                    ],
                    "market_summary": "string"
                }
                
                json_instruction = f"""
请以JSON格式返回 regime 分类，严格按照以下格式：

```json
{json.dumps(json_schema, indent=2, ensure_ascii=False)}
```

确保JSON格式正确，所有字符串用双引号包围。"""
                
                response = await structured_llm.ainvoke([
                    SystemMessage(content=system_prompt + json_instruction),
                    HumanMessage(content=regime_prompt)
                ])
                
                # 解析JSON响应
                regime_classification = parse_regime_response(response.content, symbols)

            logger.info(f"regime classification: {regime_classification}")

            # 更新状态
            state["overall_summary"] = regime_classification.overall_summary
            state["regime_classification"] = {
                item.symbol: {
                    "regime": item.regime.value,
                    "confidence": item.confidence,
                    "evidence": item.evidence,
                    "expires_at": item.expires_at,
                }
                for item in regime_classification.symbol_regimes
            }
            state["regime_classification_result"] = regime_classification
            state["analysis_context"] = {
                "symbols": symbols,
                "total_balance": balance.total_balance,
                "positions_by_symbol": _positions_by_symbol(positions),
                "quant_guardrails": quant_guardrails,
                "regime_indicators": regime_indicators,
            }

            logger.info(
                f"ReAct regime 分析完成: {len(regime_classification.symbol_regimes)} 个标的"
            )
            return state

        except Exception as e:
            logger.error(f"ReAct 分析失败: {e}")
            state["symbol_decisions"] = {}
            state["overall_summary"] = f"分析失败: {str(e)}"
            state["error"] = str(e)
            return state

    return node


def build_deterministic_symbol_decisions(
    *,
    symbols: list[str],
    total_balance: float,
    positions_by_symbol: dict[str, object],
    quant_guardrails: dict,
    regime_indicators: dict,
    regime_classification: RegimeClassification,
) -> dict[str, dict]:
    regimes_by_symbol = _regimes_by_symbol(regime_classification)
    symbol_decisions = {}

    for symbol in symbols:
        guardrail = quant_guardrails.get(symbol)
        indicators = regime_indicators.get(symbol)
        entry_score = score_entry(indicators, config.regime_execution) if indicators else None
        direction = score_direction(indicators, config.regime_execution) if indicators else None
        regime_decision = regimes_by_symbol.get(symbol)
        regime = _normalized_regime(regime_decision)
        current_position = positions_by_symbol.get(symbol)

        if current_position:
            decision = DeterministicSymbolDecision(
                symbol=symbol,
                action="POSITION_HOLD",
                reasoning=(
                    f"已有持仓由 deterministic exit/lifecycle 管理；"
                    f"AI regime={regime.value}。"
                ),
            )
            decision = _apply_quant_guardrail(
                decision, quant_guardrails, current_position
            )
            symbol_decisions[symbol] = {
                "action": decision.action,
                "reasoning": decision.reasoning,
                "position_size_usd": decision.position_size_usd,
                "stop_loss_price": decision.stop_loss_price,
                "take_profit_price": decision.take_profit_price,
                "leverage": decision.leverage,
                "regime": regime.value,
                "quant_guardrail": guardrail.to_prompt_dict() if guardrail else None,
                "execution_result": None,
                "execution_status": "pending",
            }
            continue

        entry_decision = build_entry_decision_from_guardrail(
            symbol=symbol,
            regime=regime,
            guardrail=guardrail,
            entry_score=entry_score,
            direction=direction,
            indicators=indicators,
            equity=total_balance,
            config=config.regime_execution,
        )
        entry_decision.update(
            {
                "quant_guardrail": guardrail.to_prompt_dict() if guardrail else None,
                "execution_result": None,
                "execution_status": "pending",
            }
        )
        symbol_decisions[symbol] = entry_decision

    for symbol, regime_decision in regimes_by_symbol.items():
        if symbol not in symbol_decisions:
            symbol_decisions[symbol] = {
                "action": "ENTRY_HOLD",
                "reasoning": "AI returned an unconfigured symbol; ignored.",
                "position_size_usd": 0.0,
                "stop_loss_price": None,
                "take_profit_price": None,
                "leverage": None,
                "regime": _normalized_regime(regime_decision).value,
                "quant_guardrail": None,
                "execution_result": None,
                "execution_status": "pending",
            }

    return symbol_decisions


def _apply_quant_guardrail(
    decision: DeterministicSymbolDecision, quant_guardrails: dict, current_position=None
) -> DeterministicSymbolDecision:
    """Enforce deterministic v2 guardrails over LLM output."""
    guardrail = quant_guardrails.get(decision.symbol)
    if guardrail is None:
        return decision

    if decision.action in {"OPEN_LONG", "OPEN_SHORT"}:
        if not guardrail.action_allowed:
            decision.action = "ENTRY_HOLD"
            decision.reasoning = (
                f"{decision.reasoning}\n系统量化护栏强制 ENTRY_HOLD: {guardrail.hold_reason}"
            )
            decision.position_size_usd = 0.0
            decision.stop_loss_price = None
            decision.take_profit_price = None
            decision.leverage = None
            return _apply_position_exit_guardrail(decision, guardrail, current_position)

        if decision.action != guardrail.allowed_action:
            decision.action = "ENTRY_HOLD"
            decision.reasoning = (
                f"{decision.reasoning}\nAI 开仓方向与系统评分方向不一致，系统降级 ENTRY_HOLD。"
            )
            decision.position_size_usd = 0.0
            decision.stop_loss_price = None
            decision.take_profit_price = None
            decision.leverage = None
            return _apply_position_exit_guardrail(decision, guardrail, current_position)

        stop_side = (
            guardrail.stops.long
            if decision.action == "OPEN_LONG"
            else guardrail.stops.short
        )
        decision.position_size_usd = guardrail.sizing.position_size_usd
        decision.stop_loss_price = stop_side.stop_loss
        decision.take_profit_price = stop_side.take_profit
        decision.leverage = guardrail.sizing.leverage
        decision.reasoning = (
            f"{decision.reasoning}\n系统量化护栏已覆盖仓位/止损/止盈/杠杆: "
            f"score={guardrail.score.total_score}, size=${guardrail.sizing.position_size_usd}, "
            f"leverage={guardrail.sizing.leverage}x, stop_source={stop_side.stop_source}."
        )
        return _apply_position_exit_guardrail(decision, guardrail, current_position)

    return _apply_position_exit_guardrail(decision, guardrail, current_position)


def _apply_position_exit_guardrail(
    decision: DeterministicSymbolDecision, guardrail, current_position
) -> DeterministicSymbolDecision:
    """Close existing positions when quantified opposite-side evidence appears."""
    if current_position is None or decision.action in {"CLOSE_LONG", "CLOSE_SHORT"}:
        return decision

    side = str(getattr(current_position, "side", "")).upper()
    exit_threshold = config.scoring.exit_score_threshold
    long_score = guardrail.score.long_score.total_score
    short_score = guardrail.score.short_score.total_score

    if side == "SHORT" and long_score >= exit_threshold and long_score > short_score:
        decision.action = "CLOSE_SHORT"
        _clear_open_fields(decision)
        decision.reasoning = (
            f"{decision.reasoning}\n持仓退出护栏触发: 当前为 SHORT，"
            f"LONG 评分 {long_score} >= 退出阈值 {exit_threshold} 且高于 SHORT 评分 {short_score}，"
            "平掉空头。action_allowed=false 只限制新开仓，不限制平仓。"
        )
    elif side == "LONG" and short_score >= exit_threshold and short_score > long_score:
        decision.action = "CLOSE_LONG"
        _clear_open_fields(decision)
        decision.reasoning = (
            f"{decision.reasoning}\n持仓退出护栏触发: 当前为 LONG，"
            f"SHORT 评分 {short_score} >= 退出阈值 {exit_threshold} 且高于 LONG 评分 {long_score}，"
            "平掉多头。action_allowed=false 只限制新开仓，不限制平仓。"
        )

    return decision


def _clear_open_fields(decision: DeterministicSymbolDecision) -> None:
    decision.position_size_usd = 0.0
    decision.stop_loss_price = None
    decision.take_profit_price = None
    decision.leverage = None


def _positions_by_symbol(positions) -> dict[str, object]:
    indexed = {}
    for pos in positions:
        for symbol in config.agent.symbols:
            if same_symbol(pos.symbol, symbol):
                indexed[symbol] = pos
                break
    return indexed


def _regimes_by_symbol(
    classification: RegimeClassification,
) -> dict[str, SymbolRegimeDecision]:
    return {item.symbol: item for item in classification.symbol_regimes}


def _normalized_regime(decision: SymbolRegimeDecision | None) -> Regime:
    if decision is None:
        return Regime.UNKNOWN
    now = int(time.time())
    return normalize_regime(
        RegimeOutput(
            regime=decision.regime,
            confidence=decision.confidence,
            expires_at=decision.expires_at,
        ),
        now=now,
        config=config.regime_execution,
    ).regime
