#!/usr/bin/env python3
"""Deterministic Hyperliquid testnet execution acceptance."""

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from config.settings import config  # noqa: E402
from trading.factory import get_trader  # noqa: E402
from trading.symbols import same_symbol, to_exchange_symbol  # noqa: E402


def fail(message: str) -> None:
    raise RuntimeError(message)


def validate_local_safety() -> None:
    missing = config.exchange.missing_credential_env_vars()
    if missing:
        fail(f"缺少环境变量: {', '.join(missing)}")
    if config.exchange.name != "hyperliquid":
        fail(f"交易所不是 Hyperliquid: {config.exchange.name}")
    if not config.exchange.testnet:
        fail("Hyperliquid 验收只允许 testnet: true")
    if config.exchange.allow_live_trading:
        fail("Hyperliquid 验收要求 allow_live_trading: false")


async def wait_for_position(trader, symbol: str, side: str | None, attempts=10):
    for _ in range(attempts):
        positions = await trader.get_positions()
        matching = [
            position
            for position in positions
            if same_symbol(position.symbol, symbol)
            and (side is None or position.side == side)
        ]
        if side is None and not matching:
            return None
        if side is not None and matching:
            return matching[0]
        await asyncio.sleep(1)
    expected = "无持仓" if side is None else side
    fail(f"{symbol} 未在等待时间内达到状态: {expected}")


async def verify_protection_orders(
    trader, symbol: str, side: str, reference_price: float, attempts=10
) -> None:
    exchange_symbol = to_exchange_symbol(symbol, "hyperliquid")
    expected_order_side = "sell" if side == "LONG" else "buy"
    for _ in range(attempts):
        orders = trader.exchange.fetch_open_orders(exchange_symbol)
        triggers = [
            order
            for order in orders
            if order.get("reduceOnly")
            and order.get("triggerPrice") is not None
            and order.get("side") == expected_order_side
        ]
        prices = [float(order["triggerPrice"]) for order in triggers]
        has_stop_loss = (
            any(price < reference_price for price in prices)
            if side == "LONG"
            else any(price > reference_price for price in prices)
        )
        has_take_profit = (
            any(price > reference_price for price in prices)
            if side == "LONG"
            else any(price < reference_price for price in prices)
        )
        if has_stop_loss and has_take_profit:
            return
        await asyncio.sleep(1)
    fail(f"{symbol} 未观察到有效止损和止盈保护单")


async def run_acceptance(symbol: str, notional_usd: float) -> None:
    validate_local_safety()
    trader = get_trader()
    existing = [
        position
        for position in await trader.get_positions()
        if same_symbol(position.symbol, symbol)
    ]
    if existing:
        fail(f"{symbol} 已有持仓，拒绝执行确定性验收")
    exchange_symbol = to_exchange_symbol(symbol, "hyperliquid")
    if trader.exchange.fetch_open_orders(exchange_symbol):
        fail(f"{symbol} 已有挂单，拒绝执行确定性验收")

    balance = await trader.get_balance()
    if balance.available_balance < notional_usd:
        fail(
            f"测试网可用余额不足: available={balance.available_balance}, "
            f"required={notional_usd}"
        )

    price = await trader.get_market_price(symbol)
    quantity = float(trader.format_quantity(symbol, notional_usd / price))
    if quantity <= 0:
        fail("精度格式化后的下单数量为 0")

    try:
        await trader.open_long(
            symbol,
            quantity,
            config.exchange.default_leverage,
            price * 0.98,
            price * 1.04,
        )
        await wait_for_position(trader, symbol, "LONG")
        await verify_protection_orders(trader, symbol, "LONG", price)
        await trader.close_long(symbol)
        await wait_for_position(trader, symbol, None)
        print("Hyperliquid 测试网开多、保护单、平多通过")

        price = await trader.get_market_price(symbol)
        await trader.open_short(
            symbol,
            quantity,
            config.exchange.default_leverage,
            price * 1.02,
            price * 0.96,
        )
        await wait_for_position(trader, symbol, "SHORT")
        await verify_protection_orders(trader, symbol, "SHORT", price)
        await trader.close_short(symbol)
        await wait_for_position(trader, symbol, None)
        print("Hyperliquid 测试网开空、保护单、平空通过")
    finally:
        positions = [
            position
            for position in await trader.get_positions()
            if same_symbol(position.symbol, symbol)
        ]
        for position in positions:
            if position.side == "LONG":
                await trader.close_long(symbol)
            elif position.side == "SHORT":
                await trader.close_short(symbol)
        await trader.cancel_all_orders(symbol)

    print("Hyperliquid 确定性交易验收通过")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--notional-usd", type=float, default=20.0)
    args = parser.parse_args()
    try:
        asyncio.run(run_acceptance(args.symbol, args.notional_usd))
    except Exception as exc:
        print(f"Hyperliquid 确定性交易验收失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
