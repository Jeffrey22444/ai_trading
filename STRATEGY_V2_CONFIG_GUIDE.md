# Strategy v2 Configuration Guide

本文说明以后如何调整策略 v2 的配置，以及哪些改动不能只改配置或 prompt。

## 核心原则

- 客观行情数据由后端代码抓取和计算。
- D1-D5 评分、胜率映射、Kelly 仓位、止损止盈、杠杆档位由代码执行。
- AI 只能确认开仓、否决为 HOLD、判断已有持仓是否失效，并写 reasoning。
- AI 不得改写 `position_size_usd`、`stop_loss_price`、`take_profit_price`、`leverage`。

## 配置文件位置

主要配置在：

```text
backend/config/agent.yaml
```

配置模型在：

```text
backend/config/agent_config.py
```

修改 `agent.yaml` 后，如果后端已经在运行，需要刷新 active config：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/trading/strategy/refresh
```

或者重启后端。

## 可直接改配置的参数

### Kelly 仓位

```yaml
kelly:
  fraction: 0.35
  hard_cap: 0.20
  min_position_usd: 100
  payoff_ratio_b: 2.0
```

- `fraction`: 分数 Kelly 系数。越低越保守。
- `hard_cap`: 单标的最大敞口上限。`0.20` 表示最多可用余额的 20%。
- `min_position_usd`: 开仓金额下限。当前为 100 美元。
- `payoff_ratio_b`: 盈亏比，也用于止盈距离。`2.0` 表示止盈距离是止损距离的 2 倍。

### 杠杆

```yaml
leverage:
  max_leverage: 3
  score_to_leverage:
    "6-7": 1
    "7-8": 2
    "8-9": 3
    "9-10": 3
  fraction_by_leverage:
    1: 0.35
    2: 0.35
    3: 0.30
    4: 0.25
    5: 0.25
```

- `max_leverage`: 最高允许杠杆。
- `score_to_leverage`: 评分到杠杆档位。
- `fraction_by_leverage`: 不同杠杆下的 Kelly 系数。高杠杆应更保守。

### 评分

```yaml
scoring:
  entry_score_threshold: 6.0
  min_direction_edge: 1.0
  trend_timeframes: ["1h", "4h"]
  momentum_timeframe: "4h"
  fallback_momentum_timeframe: "1h"
  volatility_timeframe: "4h"
  benchmark_symbol: "BTC"
  core_symbols: [BTC, ETH, SOL]
  score_weights:
    D1: 1
    D2: 1
    D3: 1
    D4: 1
    D5: 1
  score_to_winrate:
    "6-7": 0.50
    "7-8": 0.53
    "8-9": 0.56
    "9-10": 0.58
```

- `entry_score_threshold`: 低于该分数强制 HOLD。
- `min_direction_edge`: LONG/SHORT 分差低于该值时强制 HOLD。
- `trend_timeframes`: D1 趋势一致性使用的时间框架。
- `momentum_timeframe`: D2 动量优先使用的时间框架。
- `fallback_momentum_timeframe`: D2/D4 的备用时间框架。
- `volatility_timeframe`: D3 波动率使用的时间框架。
- `core_symbols`: 核心高流动性资产。当前 BTC/ETH/SOL 不被 BTC 方向硬性否决。
- `score_weights`: D1-D5 权重。
- `score_to_winrate`: 评分到 Kelly 胜率 `p` 的保守映射。

### 止损止盈

```yaml
stop:
  timeframe: "4h"
  fallback_timeframe: "1h"
  atr_stop_multiplier: 1.5
  high_volatility_atr_stop_multiplier: 2.0
  swing_lookback: 20
  swing_strength_m: 2
  swing_buffer_atr_fraction: 0.10
```

- `timeframe`: 止损优先使用的时间框架。
- `fallback_timeframe`: 止损备用时间框架。
- `atr_stop_multiplier`: 常规 ATR 止损倍数。
- `high_volatility_atr_stop_multiplier`: 高波动时 ATR 止损倍数。
- `swing_lookback`: 查找 swing high/low 的 K 线数量。
- `swing_strength_m`: swing 点左右各比较多少根 K 线。
- `swing_buffer_atr_fraction`: swing 点之外额外留出的 ATR 缓冲。

## 不能只改配置的策略变化

以下改动必须同步改代码、测试和策略说明：

- 新增或删除评分维度，例如增加 D6。
- 改变 D1-D5 的含义，例如 D1 不再用 EMA。
- 改变 Kelly 公式本身。
- 改变 stop-loss 选择逻辑，例如从 ATR/swing 改成 Volume Profile。
- 让 AI 参与最终仓位计算。
- 增加新的市场数据字段，例如订单簿深度、成交量分布。
- 改变 API 返回结构或前端展示结构。

相关代码位置：

```text
backend/agent/quant/scoring.py
backend/agent/quant/stops.py
backend/agent/quant/position_sizing.py
backend/agent/quant/guardrails.py
backend/agent/nodes/analysis_node.py
backend/agent/nodes/trading_execution_node.py
backend/services/strategy_contract.py
frontend/src/lib/types.ts
frontend/src/lib/api.ts
frontend/src/components/trading/DecisionsList.tsx
```

## 修改后必须验证

后端：

```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/backend
UV_CACHE_DIR=/tmp/uv-cache uv run --offline pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run --offline ruff check agent/quant config/agent_config.py agent/nodes/analysis_node.py agent/nodes/trading_execution_node.py services/strategy_contract.py tests/test_quant_guardrails.py tests/test_strategy_contract_routes.py
```

前端：

```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/frontend
CI=true pnpm run build
```

合并前还要确认新增文件已被纳入 commit，尤其是：

```text
backend/agent/quant/
backend/tests/test_quant_guardrails.py
```

