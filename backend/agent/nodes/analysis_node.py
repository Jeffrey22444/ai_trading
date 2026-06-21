"""
Analysis Node - ReAct Agent for technical analysis and decision making
"""

import json
import logging
from typing import List, Optional
from datetime import datetime
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator

from agent.quant.guardrails import build_quant_guardrails
from agent.state import AgentState
from config.settings import config
from services.prompt_service import get_trading_strategy
from trading.symbols import from_exchange_symbol, same_symbol


class SymbolDecision(BaseModel):
    """单个交易标的的决策"""

    symbol: str = Field(description="逻辑交易标的，例如 'BTC'")
    action: str = Field(
        description="期货交易决策，只能是 'OPEN_LONG'(开多仓), 'OPEN_SHORT'(开空仓), 'CLOSE_LONG'(平多仓), 'CLOSE_SHORT'(平空仓) 或 'HOLD'(持仓观望)"
    )
    reasoning: str = Field(description="详细的推理过程，说明为什么做出这个决策")
    position_size_usd: float = Field(
        description="期望的仓位价值(美元)，仅对开仓操作有效，平仓操作会自动全部平仓",
        default=0.0,
    )
    stop_loss_price: Optional[float] = Field(
        description="止损价格，仅对开仓操作有效", default=None
    )
    take_profit_price: Optional[float] = Field(
        description="止盈价格，仅对开仓操作有效", default=None
    )
    leverage: Optional[int] = Field(
        description="杠杆倍数，仅对开仓操作有效；最终以系统量化护栏为准", default=None
    )

    @field_validator("position_size_usd", mode="before")
    @classmethod
    def normalize_optional_position_size(cls, value):
        return 0.0 if value is None else value

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return from_exchange_symbol(value)


class TradingDecision(BaseModel):
    """完整的交易决策结构"""

    symbol_decisions: List[SymbolDecision] = Field(description="所有交易标的的决策列表")
    overall_summary: str = Field(description="整体市场状况分析和总结")


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
        return llm.with_structured_output(TradingDecision)
    else:
        # 其他模型使用JSON mode或普通文本模式
        return llm

def supports_native_structured_output():
    """检查是否支持原生结构化输出"""
    return config.agent.model_name.startswith("gpt-4o") and config.agent.base_url is None

def parse_json_response(response_text: str) -> TradingDecision:
    """解析JSON格式的响应为TradingDecision对象"""
    import json
    import re
    
    # 提取JSON部分（去除markdown代码块标记等）
    json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试直接解析整个响应
        json_str = response_text.strip()
    
    try:
        json_data = json.loads(json_str)
        return TradingDecision(**json_data)
    except Exception as e:
        logger.error(f"解析JSON响应失败: {e}, 原始响应: {response_text}")
        # 返回默认的HOLD决策
        return TradingDecision(
            symbol_decisions=[
                SymbolDecision(
                    symbol=symbol,
                    action="HOLD",
                    reasoning="JSON解析失败，采用保守策略",
                    position_size_usd=0.0
                ) for symbol in config.agent.symbols
            ],
            overall_summary="由于响应解析错误，所有标的采用观望策略"
        )

structured_llm = create_structured_llm()


def analysis_node(tools: List):
    """Create analysis node function with structured output"""
    react_agent = create_react_agent(llm, tools)

    async def node(state: AgentState) -> AgentState:
        """ReAct 分析节点 - AI 主动调用工具获取技术数据并做出决策"""
        try:
            logger.info("开始 ReAct 分析...")

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

            # 第二步：使用新的分层提示词系统生成结构化决策
            
            # 系统提示词（固定结构）
            system_prompt = f"""基于以下信息为每个标的做出交易决策：

标的: {symbols_list}

当前账户状态:
{balance_info}
{positions_info}

技术分析结果:
{analysis_content}

系统量化护栏（代码已计算，AI 不得改写 position_size_usd、stop_loss_price、take_profit_price、leverage）:
{json.dumps({symbol: guardrail.to_prompt_dict() for symbol, guardrail in quant_guardrails.items()}, indent=2, ensure_ascii=False)}

请为每个标的做出期货交易决策：
- OPEN_LONG: 开多仓 (看涨时选择)
- OPEN_SHORT: 开空仓 (看跌时选择) 
- CLOSE_LONG: 平多仓 (将全部平掉多头持仓)
- CLOSE_SHORT: 平空仓 (将全部平掉空头持仓)
- HOLD: 持仓观望 (无明确信号或当前持仓合适)

对于开仓操作(OPEN_LONG/OPEN_SHORT)，请指定：
1. 采用系统量化护栏里的 position_size_usd，不得自行改写
2. 采用系统量化护栏里对应方向的 stop_loss_price
3. 采用系统量化护栏里对应方向的 take_profit_price
4. 采用系统量化护栏里的 leverage

如果准备开仓且系统量化护栏 action_allowed=false，必须 HOLD。该限制只约束 OPEN_LONG/OPEN_SHORT，不约束 CLOSE_LONG/CLOSE_SHORT。
action_allowed=true 不是必须开仓，只代表系统没有硬性禁止。AI 的主要职责是拒绝低质量入场；如果存在追高/追低、RSI 过热/过冷、MACD 动能衰减、价格远离 EMA20、reference_timestamp 数据过期，或无法解释入场优势，必须把系统允许的 OPEN_LONG/OPEN_SHORT 改为 HOLD。
direction_bias 只是候选方向，不是开仓理由。AI 可以把系统允许的 OPEN_LONG/OPEN_SHORT 改为 HOLD，但不得反向开仓，不得放大仓位。
已有持仓失效、风控恶化或策略要求退出时，AI 仍可输出平仓动作。AI 判断不确定时必须 HOLD。"""

            # 获取用户交易策略（三层优先级）
            user_trading_strategy = await get_trading_strategy()
            
            # 根据是否支持原生结构化输出来调整处理
            if supports_native_structured_output():
                # OpenAI gpt-4o 使用原生结构化输出
                trading_decision = await structured_llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_trading_strategy)
                ])
            else:
                # 其他模型使用JSON格式
                json_schema = {
                    "symbol_decisions": [
                        {
                            "symbol": "string",
                            "action": "OPEN_LONG|OPEN_SHORT|CLOSE_LONG|CLOSE_SHORT|HOLD",
                            "reasoning": "string",
                            "position_size_usd": "number (仅开仓时需要)",
                            "stop_loss_price": "number (仅开仓时，可选)",
                            "take_profit_price": "number (仅开仓时，可选)",
                            "leverage": "number (仅开仓时，可选)"
                        }
                    ],
                    "overall_summary": "string"
                }
                
                json_instruction = f"""
请以JSON格式返回决策，严格按照以下格式：

```json
{json.dumps(json_schema, indent=2, ensure_ascii=False)}
```

确保JSON格式正确，所有字符串用双引号包围。"""
                
                response = await structured_llm.ainvoke([
                    SystemMessage(content=system_prompt + json_instruction),
                    HumanMessage(content=user_trading_strategy)
                ])
                
                # 解析JSON响应
                trading_decision = parse_json_response(response.content)

            logger.info(f"trading decision: {trading_decision}")

            positions_by_symbol = _positions_by_symbol(positions)

            # 直接使用 TradingDecision 构建状态
            symbol_decisions = {}
            for decision in trading_decision.symbol_decisions:
                decision = _apply_quant_guardrail(
                    decision,
                    quant_guardrails,
                    positions_by_symbol.get(decision.symbol),
                )
                symbol_decisions[decision.symbol] = {
                    "action": decision.action,
                    "reasoning": decision.reasoning,
                    "position_size_usd": decision.position_size_usd,
                    "stop_loss_price": decision.stop_loss_price,
                    "take_profit_price": decision.take_profit_price,
                    "leverage": decision.leverage,
                    "quant_guardrail": (
                        quant_guardrails[decision.symbol].to_prompt_dict()
                        if decision.symbol in quant_guardrails
                        else None
                    ),
                    "execution_result": None,
                    "execution_status": "pending",
                }

            for symbol in symbols:
                if symbol not in symbol_decisions:
                    guardrail = quant_guardrails.get(symbol)
                    fallback_decision = SymbolDecision(
                        symbol=symbol,
                        action="HOLD",
                        reasoning="AI 未返回该标的决策，系统降级 HOLD",
                    )
                    fallback_decision = _apply_quant_guardrail(
                        fallback_decision,
                        quant_guardrails,
                        positions_by_symbol.get(symbol),
                    )
                    symbol_decisions[symbol] = {
                        "action": fallback_decision.action,
                        "reasoning": fallback_decision.reasoning,
                        "position_size_usd": fallback_decision.position_size_usd,
                        "stop_loss_price": fallback_decision.stop_loss_price,
                        "take_profit_price": fallback_decision.take_profit_price,
                        "leverage": fallback_decision.leverage,
                        "quant_guardrail": guardrail.to_prompt_dict() if guardrail else None,
                        "execution_result": None,
                        "execution_status": "pending",
                    }

            # 更新状态
            state["symbol_decisions"] = symbol_decisions
            state["overall_summary"] = trading_decision.overall_summary

            logger.info(
                f"ReAct 分析完成: {len(trading_decision.symbol_decisions)} 个标的决策"
            )
            return state

        except Exception as e:
            logger.error(f"ReAct 分析失败: {e}")
            state["symbol_decisions"] = {}
            state["overall_summary"] = f"分析失败: {str(e)}"
            state["error"] = str(e)
            return state

    return node


def _apply_quant_guardrail(
    decision: SymbolDecision, quant_guardrails: dict, current_position=None
) -> SymbolDecision:
    """Enforce deterministic v2 guardrails over LLM output."""
    guardrail = quant_guardrails.get(decision.symbol)
    if guardrail is None:
        return decision

    if decision.action in {"OPEN_LONG", "OPEN_SHORT"}:
        if not guardrail.action_allowed:
            decision.action = "HOLD"
            decision.reasoning = (
                f"{decision.reasoning}\n系统量化护栏强制 HOLD: {guardrail.hold_reason}"
            )
            decision.position_size_usd = 0.0
            decision.stop_loss_price = None
            decision.take_profit_price = None
            decision.leverage = None
            return _apply_position_exit_guardrail(decision, guardrail, current_position)

        if decision.action != guardrail.allowed_action:
            decision.action = "HOLD"
            decision.reasoning = (
                f"{decision.reasoning}\nAI 开仓方向与系统评分方向不一致，系统降级 HOLD。"
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
    decision: SymbolDecision, guardrail, current_position
) -> SymbolDecision:
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


def _clear_open_fields(decision: SymbolDecision) -> None:
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
