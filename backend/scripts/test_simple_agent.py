#!/usr/bin/env python3
"""
Agent 测试脚本 - 通过 API 测试工作流程
使用 HTTP API 调用来测试完整的交易系统
"""
import asyncio
import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv
from database.database import init_database
from agent.models import decision_service
from utils.logger import setup_logger

# 设置 backend/.env 文件路径
backend_dir = Path(__file__).parent.parent
env_file = backend_dir / ".env"

# 加载 .env 文件
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ 已加载环境配置文件: {env_file}")
else:
    print(f"⚠️  未找到 .env 文件: {env_file}")

# 确保环境变量正确设置
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "你的OpenAI_API_Key"  # 替换为你的 key

# 设置日志
logger = setup_logger()


def print_banner():
    """打印欢迎横幅"""
    print("=" * 60)
    print("🚀 简化版 AlphaTransformer Agent 测试")
    print("=" * 60)
    print("测试新的简化 state 和 workflow")
    print()


def test_agent_via_api():
    """通过 API 测试 Agent"""
    print("🧪 通过 API 测试 Agent 工作流程")
    print("-" * 40)
    
    # API 基础 URL
    base_url = "http://localhost:8000"
    api_base = f"{base_url}/api/v1"
    
    try:
        # 1. 检查系统状态
        print("1️⃣ 检查系统状态...")
        response = requests.get(f"{api_base}/health")
        if response.status_code == 200:
            print("   ✅ 系统运行正常")
        else:
            print(f"   ❌ 系统状态异常: {response.status_code}")
            return
        
        # 2. 获取配置信息
        print("2️⃣ 获取配置信息...")
        response = requests.get(f"{api_base}/config")
        if response.status_code == 200:
            config_data = response.json()
            symbols = config_data.get("agent", {}).get("symbols", [])
            print(f"   📋 配置的交易标的: {symbols}")
        else:
            print(f"   ❌ 获取配置失败: {response.status_code}")
            return
        
        # 3. 触发 Agent 分析
        print("3️⃣ 触发 Agent 分析...")
        response = requests.post(f"{api_base}/agent/analyze")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Agent 分析完成")
            print(f"   🤖 决策: {result.get('action', 'Unknown')}")
            print(f"   ⏱️  耗时: {result.get('duration_ms', 0):.2f}ms")
            
            # 显示推理摘要
            reasoning = result.get('reasoning', '')
            if reasoning and len(reasoning) > 150:
                reasoning_preview = reasoning[:150] + "..."
            else:
                reasoning_preview = reasoning
            print(f"   💭 推理: {reasoning_preview}")
        else:
            print(f"   ❌ Agent 分析失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return
        
        # 4. 查看决策历史
        print("4️⃣ 查看决策历史...")
        response = requests.get(f"{api_base}/decisions?limit=10")
        if response.status_code == 200:
            decisions = response.json()
            print(f"   📊 最近 {len(decisions)} 条决策:")
            
            action_counts = {}
            for decision in decisions:
                action = decision.get('action', 'UNKNOWN')
                action_counts[action] = action_counts.get(action, 0) + 1
            
            for action, count in action_counts.items():
                emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(action, "❓")
                print(f"   {emoji} {action}: {count} 次")
                
        print("\n✅ API 测试完成！")
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 API 服务器")
        print("   请确保 FastAPI 服务正在运行: uvicorn api.main:app --reload")
    except Exception as e:
        print(f"❌ API 测试失败: {e}")


async def test_database_directly():
    """直接测试数据库（可选）"""
    print("\n💾 直接测试数据库...")
    
    try:
        # 初始化数据库
        await init_database()
        
        # 获取最近的决策
        decisions = await decision_service.get_recent_decisions(limit=10)
        
        if decisions:
            print(f"   数据库中有 {len(decisions)} 条决策记录")
            
            # 显示最近几条
            for i, decision in enumerate(decisions[:3], 1):
                print(f"   {i}. {decision.action} {decision.symbol} - {decision.timestamp}")
        else:
            print("   数据库中暂无决策记录")
            
    except Exception as e:
        print(f"   ❌ 数据库测试失败: {e}")


async def main():
    """主测试流程"""
    print_banner()
    
    # 检查 API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "你的OpenAI_API_Key":
        print("❌ 请设置正确的 OPENAI_API_KEY")
        print("   1. 编辑 backend/.env 文件，或")
        print("   2. 编辑此脚本第 25 行")
        return
    
    print(f"✅ OpenAI API Key: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    print("🚀 开始测试 Agent 工作流程...\n")
    
    # 优先通过 API 测试
    test_agent_via_api()
    
    # 可选：直接测试数据库
    await test_database_directly()
    
    print("\n" + "=" * 60)
    print("🎉 简化版 Agent 测试完成！")
    print("新的 state 更简洁，agent 使用工具获取数据")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()