# Scripts 目录

这个目录包含了 AlphaTransformer 的测试脚本和分析工具。

## 📁 目录结构

- **测试脚本** (`*.py`) - 系统功能测试
- **分析工具** (`analysis/`) - 交易性能分析和监控工具

## 📁 文件说明

### 测试脚本
- `test_openai.py` - OpenAI GPT-4 连接测试
- `test_agent.py` - 完整 LangGraph Agent 工作流程测试  
- `run_tests.py` - 统一测试运行脚本
- `debug_positions.py` - 持仓调试工具
- `test_futures_trading.py` - 期货交易功能测试
- `test_simple_agent.py` - 简化代理测试

### 分析工具
- **`analysis/`** - 详细的交易分析和监控工具 ([查看文档](./analysis/README.md))

## 🚀 使用方法

### 方法 1: 使用统一运行脚本 (推荐)

```bash
# 测试 OpenAI 连接
python scripts/run_tests.py openai

# 测试完整 Agent 工作流程
python scripts/run_tests.py agent

# 运行所有测试
python scripts/run_tests.py all
```

### 方法 2: 直接运行单个脚本

```bash
# 测试 OpenAI 连接
python scripts/test_openai.py

# 测试完整 Agent 工作流程  
python scripts/test_agent.py
```

## ⚙️ 配置 API Keys

### 选项 1: 使用 .env 文件 (推荐)

在 `backend/.env` 文件中设置:
```
OPENAI_API_KEY=你的OpenAI_API密钥
HYPERLIQUID_WALLET_ADDRESS=你的Hyperliquid测试网主账户地址
HYPERLIQUID_PRIVATE_KEY=已授权的API-Wallet私钥
```

### 选项 2: 直接在脚本中设置

编辑相应的脚本文件，找到包含 `os.environ["OPENAI_API_KEY"]` 的行并替换为你的 API 密钥。

## 🧪 测试内容

### OpenAI 测试 (`test_openai.py`)
- ✅ OpenAI GPT-4 连接测试
- ✅ 基本交易决策生成测试
- ✅ 多种市场场景测试
- ✅ 工作流程集成测试

### Agent 测试 (`test_agent.py`)
- ✅ 完整 LangGraph 工作流程测试
- ✅ 数据库操作测试
- ✅ 决策保存功能测试
- ✅ 多场景决策测试
- ✅ 数据库统计显示

## 📊 测试结果

成功的测试会显示:
- ✅ OpenAI 连接正常
- 🤖 AI 生成的交易决策
- 💾 数据库中的决策记录
- 📈 决策统计信息

## 🔍 故障排除

如果遇到问题:
1. 检查 API Keys 是否正确设置
2. 确认网络连接正常
3. 查看错误日志信息
4. 确保 `data/` 目录有写入权限
