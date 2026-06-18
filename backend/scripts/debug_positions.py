"""
调试持仓信息
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
from trading.symbols import same_symbol


async def debug_positions():
    """调试持仓信息"""
    
    try:
        trader = get_trader()
        
        print("🔍 获取原始持仓数据...")
        raw_positions = trader.exchange.fetch_positions()
        
        print(f"原始持仓数据数量: {len(raw_positions)}")
        
        # 打印所有持仓信息（包括零持仓）
        for i, pos in enumerate(raw_positions):
            symbol = pos.get('symbol', 'N/A')
            side = pos.get('side', 'N/A')
            contracts = pos.get('contracts', 0)
            size = pos.get('size', 0)
            
            print(f"\n持仓 {i+1}:")
            print(f"  标的: {symbol}")
            print(f"  方向: {side}")
            print(f"  合约数量: {contracts}")
            print(f"  持仓大小: {size}")
            
            if any(same_symbol(symbol, candidate) for candidate in ["BTC", "ETH", "SOL"]) and contracts > 0:
                print(f"  *** 这是我们关注的有效持仓 ***")
                print(f"  详细信息:")
                for key, value in pos.items():
                    print(f"    {key}: {value}")
        
        print("\n" + "="*50)
        print("🔍 通过 get_positions() 获取的持仓...")
        
        positions = await trader.get_positions()
        print(f"处理后持仓数量: {len(positions)}")
        
        for i, pos in enumerate(positions):
            print(f"\n持仓 {i+1}:")
            print(f"  标的: {pos.symbol}")
            print(f"  方向: {pos.side}")
            print(f"  大小: {pos.size}")
            print(f"  入场价: ${pos.entry_price}")
            print(f"  标记价: ${pos.mark_price}")
            print(f"  盈亏: ${pos.unrealized_pnl}")
            print(f"  杠杆: {pos.leverage}x")
            
            # 特别检查 SOL
            if same_symbol(pos.symbol, "SOL"):
                print(f"  *** SOL 持仓详情 ***")
                print(f"    方向: {pos.side}")
                print(f"    是否多头: {pos.side == 'LONG'}")
                print(f"    大小: {pos.size}")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_positions())
