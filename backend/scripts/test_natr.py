"""
测试 NATR 指标是否正确添加
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

from agent.tools.analysis_tools import tech_analysis_tool


async def test_natr():
    """测试 NATR 指标"""
    
    try:
        print("🔍 测试 BTC 的技术分析（包含 NATR）...")
        
        # 调用技术分析工具
        result = tech_analysis_tool("BTC")
        
        print(f"分析结果:")
        print(f"标的: {result.get('symbol')}")
        print(f"时间戳: {result.get('analysis_timestamp')}")
        
        # 检查每个时间框架的 NATR
        timeframes = result.get('timeframes', {})
        for timeframe, data in timeframes.items():
            print(f"\n⏱️ {timeframe} 时间框架:")
            
            if "error" in data:
                print(f"  ❌ 错误: {data['error']}")
                continue
                
            # 显示关键指标包括 NATR
            current_price = data.get('current_price')
            natr = data.get('natr')
            
            print(f"  当前价格: ${current_price}")
            print(f"  NATR (波动率): {natr}%" if natr else "  NATR: None")
            print(f"  EMA20: {data.get('ema20')}")
            print(f"  EMA50: {data.get('ema50')}")
            print(f"  RSI7: {data.get('rsi7')}")
            print(f"  RSI14: {data.get('rsi14')}")
        
        # 检查综合信号
        overall = result.get('overall_signals', {})
        print(f"\n📊 综合信号:")
        for key, value in overall.items():
            print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_natr())
