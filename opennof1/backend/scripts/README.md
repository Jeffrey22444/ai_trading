# Scripts 目录

这个目录放的是当前 Hyperliquid-only 运行时的辅助脚本和分析说明。

## 当前文件

- `hyperliquid_acceptance.py` - Hyperliquid 验收脚本
- `p0_acceptance.py` - P0 本地验收脚本
- `test_agent_trading.py` - Agent 交易链路测试
- `test_simple_agent.py` - 简化版 Agent 测试
- `test_futures_trading.py` - 交易接口与下单辅助检查
- `test_position_matching.py` - 持仓匹配与平仓路径检查
- `debug_positions.py` - 打印原始和归一化后的持仓信息
- `test_natr.py` - 技术分析工具 NATR 输出检查
- `analysis/README.md` - 分析工具说明

## 使用前提

- 在 `backend/.env` 配置：
  - `OPENAI_API_KEY`
  - `HYPERLIQUID_WALLET_ADDRESS`
  - `HYPERLIQUID_PRIVATE_KEY`
- 从 `opennof1/backend` 目录运行脚本更稳妥。
- 运行时逻辑标的统一使用 `BTC`、`ETH`、`SOL`。
- 若脚本内部需要交易所格式，应由后端在 CCXT 边界自行转换为 `BASE/USDC:USDC`。

## 常用命令

```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/backend

uv run python scripts/p0_acceptance.py
uv run python scripts/hyperliquid_acceptance.py
uv run python scripts/test_simple_agent.py
uv run python scripts/test_natr.py
```

## 本地验证建议

先跑低风险检查，再跑会触达交易账户的脚本：

1. `../contracts/api.md` 里的只读接口
2. `scripts/test_natr.py`
3. `scripts/test_simple_agent.py`
4. `scripts/hyperliquid_acceptance.py`
5. `scripts/test_futures_trading.py`

## 注意

- 这里的脚本说明只面向当前本地运行时，不再把 Binance 或 `BTCUSDT` 视为规范输入。
- 仓位、订单、成交等历史数据里如果出现旧格式字符串，应视为兼容/遗留数据，而不是新的本地验证标准。
