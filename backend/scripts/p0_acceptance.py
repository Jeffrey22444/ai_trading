#!/usr/bin/env python3
"""Run the final five-cycle P0 acceptance against a running local backend."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from config.settings import config  # noqa: E402
from trading.factory import get_trader  # noqa: E402


VALID_ACTIONS = {
    "OPEN_LONG",
    "OPEN_SHORT",
    "CLOSE_LONG",
    "CLOSE_SHORT",
    "HOLD",
}
PARSE_FAILURE_MARKERS = ("JSON解析失败", "JSON 解析失败", "解析JSON响应失败")


def fail(message: str) -> None:
    raise RuntimeError(message)


def validate_local_safety() -> None:
    missing = config.validate_required_env_vars()
    if missing:
        fail(f"缺少环境变量: {', '.join(missing)}")
    if config.agent.model_name != "deepseek-chat":
        fail(f"模型不是 deepseek-chat: {config.agent.model_name}")
    if config.agent.base_url != "https://api.deepseek.com/v1":
        fail(f"DeepSeek base_url 不正确: {config.agent.base_url}")
    if config.exchange.name != "hyperliquid":
        fail(f"交易所不是 Hyperliquid: {config.exchange.name}")
    if not config.exchange.testnet:
        fail("testnet 必须为 true")
    if config.exchange.allow_live_trading:
        fail("allow_live_trading 必须为 false")

    trader = get_trader()
    if not trader.exchange.options.get("sandboxMode"):
        fail("CCXT Hyperliquid sandbox 未启用")
    private_url = trader.exchange.urls["api"]["private"]
    if not private_url.startswith("https://api.hyperliquid-testnet.xyz"):
        fail(f"交易私有端点不是 Hyperliquid 测试网: {private_url}")


def validate_decision(
    *,
    symbol: str,
    decision: dict[str, Any],
    current_price: float,
    available_balance: float,
) -> bool:
    action = decision.get("action")
    if action not in VALID_ACTIONS:
        fail(f"{symbol}: 非法动作 {action}")

    reasoning = str(decision.get("reasoning", ""))
    if any(marker in reasoning for marker in PARSE_FAILURE_MARKERS):
        fail(f"{symbol}: 检测到 JSON 解析失败降级")

    if action == "HOLD":
        return True

    if action not in {"OPEN_LONG", "OPEN_SHORT"}:
        return False

    position_size = float(decision.get("position_size_usd") or 0)
    max_position_size = available_balance * config.default_risk.max_position_size_percent
    if position_size <= 0 or position_size > max_position_size:
        fail(
            f"{symbol}: position_size_usd={position_size} 超出允许范围 "
            f"(max={max_position_size})"
        )

    stop_loss = decision.get("stop_loss_price")
    take_profit = decision.get("take_profit_price")
    if stop_loss is None or take_profit is None:
        fail(f"{symbol}: 开仓缺少止损或止盈")

    stop_loss = float(stop_loss)
    take_profit = float(take_profit)
    if action == "OPEN_LONG" and not stop_loss < current_price < take_profit:
        fail(f"{symbol}: 多头止损止盈方向错误")
    if action == "OPEN_SHORT" and not take_profit < current_price < stop_loss:
        fail(f"{symbol}: 空头止损止盈方向错误")

    return False


def validate_execution(*, symbol: str, decision: dict[str, Any]) -> None:
    """Require the execution node to complete every saved decision."""
    execution_result = decision.get("execution_result") or {}
    if (
        decision.get("execution_status") != "completed"
        or execution_result.get("status") != "success"
    ):
        fail(f"{symbol}: 执行未成功: {execution_result}")


async def run_acceptance(base_url: str, cycles: int) -> None:
    timeout = httpx.Timeout(600.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        health = (await client.get("/health")).raise_for_status().json()
        if health.get("status") != "healthy":
            fail(f"后端不健康: {health}")

        validation = (await client.get("/config/validate")).raise_for_status().json()
        if not validation.get("valid") or not validation.get("testnet_mode"):
            fail(f"后端配置验证失败: {validation}")

        balance = (await client.get("/trading/balance")).raise_for_status().json()
        available_balance = float(balance["available_balance"])

        strategy = (await client.get("/trading/strategy")).raise_for_status().json()
        if "拿不准就 HOLD" not in strategy.get("strategy", ""):
            fail("当前生效策略不是已配置的 P0 中文策略")

        previous = (
            await client.get("/decisions", params={"limit": 1, "order": "desc"})
        ).raise_for_status().json()
        previous_decision_id = previous[0]["id"] if previous else None

        saw_hold = False
        for cycle in range(1, cycles + 1):
            response = (await client.post("/agent/analyze")).raise_for_status().json()
            if response.get("error"):
                fail(f"第 {cycle} 轮分析失败: {response['error']}")

            decisions = (
                await client.get("/decisions", params={"limit": 1, "order": "desc"})
            ).raise_for_status().json()
            if not decisions:
                fail(f"第 {cycle} 轮没有保存决策记录")
            current_decision_id = decisions[0]["id"]
            if current_decision_id == previous_decision_id:
                fail(f"第 {cycle} 轮没有产生新的决策记录")
            previous_decision_id = current_decision_id

            saved = decisions[0]["symbol_decisions"]
            if set(saved) != set(config.agent.symbols):
                fail(f"第 {cycle} 轮标的不完整: {sorted(saved)}")

            for symbol, decision in saved.items():
                validate_execution(symbol=symbol, decision=decision)
                price_response = (
                    await client.get(f"/trading/market/{symbol}/price")
                ).raise_for_status().json()
                saw_hold |= validate_decision(
                    symbol=symbol,
                    decision=decision,
                    current_price=float(price_response["price"]),
                    available_balance=available_balance,
                )

            print(f"第 {cycle}/{cycles} 轮通过")

        if not saw_hold:
            fail(f"{cycles} 轮内未出现 HOLD，未满足纪律验收标准")

        print("P0 五轮端到端验收通过")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api/v1",
        help="Running backend API base URL",
    )
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args()

    try:
        validate_local_safety()
        asyncio.run(run_acceptance(args.base_url, args.cycles))
    except Exception as exc:
        print(f"P0 验收失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
