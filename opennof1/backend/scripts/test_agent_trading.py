"""
测试完整的AI Agent交易工作流程
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

from agent.workflow import create_trading_workflow
from agent.tools.analysis_tools import create_tech_analysis_tool
from agent.state import AgentState
from database.database import init_database
from config.settings import config
from trading import get_trader


async def test_complete_workflow():
    """测试完整的AI Agent交易工作流程"""
    
    try:
        print("🚀 开始测试完整AI Agent交易工作流程...")
        
        # 1. 初始化数据库
        print("\n📊 初始化数据库...")
        await init_database()
        print("✅ 数据库初始化成功")
        
        # 2. 验证交易器
        print("\n💰 验证交易器...")
        trader = get_trader()
        balance = await trader.get_balance()
        print(f"账户余额: ${balance.total_balance:.2f}")
        print(f"可用余额: ${balance.available_balance:.2f}")
        
        # 3. 创建工作流程
        print("\n🔧 创建AI Agent工作流程...")
        tech_tool = create_tech_analysis_tool()
        tools = [tech_tool]
        workflow = create_trading_workflow(tools)
        print("✅ 工作流程创建成功")
        
        # 4. 创建初始状态
        initial_state: AgentState = {
            "symbol_decisions": {},
            "overall_summary": None,
            "error": None
        }
        
        # 5. 运行完整工作流程 (分析 + 交易执行)
        print(f"\n🤖 运行AI Agent工作流程...")
        print(f"监控标的: {config.agent.symbols}")
        print(f"使用模型: {config.agent.model_name}")
        
        result = await workflow.ainvoke(initial_state)
        
        # 6. 显示结果
        print("\n📋 AI决策结果:")
        print(f"整体分析: {result.get('overall_summary', 'N/A')}")
        
        symbol_decisions = result.get('symbol_decisions', {})
        print(f"\n📊 标的决策 ({len(symbol_decisions)} 个):")
        
        for symbol, decision in symbol_decisions.items():
            action = decision.get('action', 'N/A')
            reasoning = decision.get('reasoning', 'N/A')
            execution_status = decision.get('execution_status', 'N/A')
            
            print(f"\n📈 {symbol}:")
            print(f"  决策: {action}")
            print(f"  推理: {reasoning[:100]}...")
            print(f"  执行状态: {execution_status}")
            
            execution_result = decision.get('execution_result')
            if execution_result:
                status = execution_result.get('status', 'unknown')
                message = execution_result.get('message', 'N/A')
                print(f"  执行结果: {status}")
                print(f"  信息: {message}")
                
                if status == 'failed':
                    error = execution_result.get('error', 'N/A')
                    print(f"  错误: {error}")
        
        # 7. 检查最终状态
        print("\n🔍 检查最终账户状态...")
        final_balance = await trader.get_balance()
        final_positions = await trader.get_positions()
        
        print(f"最终余额: ${final_balance.total_balance:.2f}")
        print(f"可用余额: ${final_balance.available_balance:.2f}")
        print(f"未实现盈亏: ${final_balance.unrealized_pnl:.2f}")
        print(f"持仓数量: {len(final_positions)}")
        
        for pos in final_positions:
            print(f"  {pos.symbol} {pos.side} 大小:{pos.size} 盈亏:${pos.unrealized_pnl:.2f}")
        
        # 8. 检查是否有错误
        if result.get('error'):
            print(f"\n❌ 工作流程错误: {result['error']}")
            return False
            
        print("\n✅ AI Agent交易工作流程测试完成!")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_complete_workflow())
    if success:
        print("\n🎉 所有测试通过!")
    else:
        print("\n💥 测试失败!")
        sys.exit(1)