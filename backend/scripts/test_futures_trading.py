"""
测试期货交易接口
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)

from trading import get_trader


async def clean_existing_positions(trader):
    """清理现有持仓和挂单"""
    print("\n🔍 检查现有持仓...")
    existing_positions = await trader.get_positions()
    print(existing_positions)
    
    # 1. 清理持仓
    if existing_positions:
        print("发现现有持仓，先平仓...")
        for pos in existing_positions:
            try:
                if pos.side == "LONG":
                    print(f"平掉多仓: {pos.symbol}")
                    await trader.close_long(pos.symbol, 0)
                elif pos.side == "SHORT":
                    print(f"平掉空仓: {pos.symbol}")
                    await trader.close_short(pos.symbol, 0)
                print("平仓成功")
            except Exception as e:
                print(f"平仓失败: {e}")
    else:
        print("没有现有持仓")
    
    # 2. 清理挂单
    print("\n🔍 清理挂单...")
    symbols_to_clean = ["ETH", "BTC", "SOL"]  # 运行时逻辑标的
    for symbol in symbols_to_clean:
        try:
            success = await trader.cancel_all_orders(symbol)
            if success:
                print(f"取消 {symbol} 所有挂单成功")
        except Exception as e:
            print(f"取消 {symbol} 挂单失败: {e}")
    
    await asyncio.sleep(2)
    print("持仓和挂单清理完成")


async def test_trading_interface():
    """测试期货交易接口"""

    try:
        trader = get_trader()
        print(f"✅ 交易所: {trader.get_exchange_name()}")
        print(f"✅ 测试模式: {trader.exchange.options.get('sandbox', False)}")

        # 测试获取账户余额
        print("\n📊 测试获取账户余额...")
        balance = await trader.get_balance()
        print(f"总余额: ${balance.total_balance}")
        print(f"可用余额: ${balance.available_balance}")
        print(f"未实现盈亏: ${balance.unrealized_pnl}")

        # 测试获取持仓
        print("\n📈 测试获取持仓...")
        positions = await trader.get_positions()
        print(f"持仓数量: {len(positions)}")
        for pos in positions:
            print(
                f"  {pos.symbol} {pos.side} 大小: {pos.size} 盈亏: ${pos.unrealized_pnl:.2f} 杠杆: ${pos.leverage}"
            )

        # 测试获取市场价格
        print("\n💰 测试获取市场价格...")
        eth_price = await trader.get_market_price("ETH")
        print(f"ETH 价格: ${eth_price}")

        # 测试数量格式化
        print("\n🔢 测试数量格式化...")
        formatted_qty = trader.format_quantity("ETH", 0.00123456)
        print(f"格式化数量: {formatted_qty}")

        # 测试开多仓
        print("\n🚀 测试开多仓...")

        # 计算交易数量（确保名义价值至少约20 USDC）
        eth_price = await trader.get_market_price("ETH")
        if eth_price > 0:
            min_quantity = 25 / eth_price  # 25 USDT价值的ETH
        else:
            min_quantity = 0.00001

        print(f"ETH价格: ${eth_price}")
        print(
            f"开仓数量: {min_quantity:.6f} ETH (约${min_quantity * eth_price:.2f} USDC名义价值，1倍杠杆)"
        )

        # 清理现有持仓
        await clean_existing_positions(trader)
        
        # # 计算止损止盈价格 (使用更保守的价格避免立即触发)
        # stop_loss_price = eth_price * 0.95  # 5% 止损
        # take_profit_price = eth_price * 1.10  # 10% 止盈
        
        # print(f"\n测试1: 开多仓（含止损止盈）: {min_quantity:.6f} ETH")
        # print(f"当前价格: ${eth_price}")
        # print(f"止损价格: ${stop_loss_price:.2f} (-5%)")
        # print(f"止盈价格: ${take_profit_price:.2f} (+10%)")
        
        # await trader.open_long("ETH", min_quantity, leverage=1,
        #                       stop_loss_price=stop_loss_price, 
        #                       take_profit_price=take_profit_price)
        # print("✅ 开多仓（含止损止盈）成功")

        # await asyncio.sleep(3)

        # # 验证持仓并平仓
        # print("\n🔍 验证持仓...")
        # positions = await trader.get_positions()
        # if positions:
        #     for pos in positions:
        #         print(f"持仓: {pos.symbol} {pos.side} 大小:{pos.size} 杠杆:{pos.leverage}x 保证金:${pos.margin:.2f}")
        
        # 清理测试持仓
        # await clean_existing_positions(trader)

    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_trading_interface())
