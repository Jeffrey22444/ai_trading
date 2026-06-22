# HANDOFF — opennof1 + wquguru 逆向 Prompt 集成(Codex 执行包)

> **目的**:把「路线 A」交给 Codex(coding agent)在本地执行。本文件是 Codex 的唯一上下文来源,包含背景、已核实的代码事实、精确任务、验收标准与防坑提示。
> **代码事实快照**:基于直读 `github.com/wfnuser/opennof1` 源码,2026-06-14。Codex 执行前应 `git pull` 最新版并对照本文「需 Codex 二次核实」清单复查。
> **总原则**:全程在币安**测试网(testnet)**验证;不改框架对外契约(JSON 输出格式 / 动作枚举)除非进入「进阶任务」。

---

## 0. TL;DR(给 Codex 的任务摘要)
1. 把一段「wquguru 风格的交易策略」写入 opennof1 的 `trading_strategy` 配置(主任务,**不改代码**)。
2. 确认 AI 输出能被框架正确解析(动作枚举 / 字段对齐),否则修正策略文本。
3. 切换到测试网、跑通端到端、自检验收清单。
4. (可选进阶)把 wquguru 的「Sharpe 自我校准」「invalidation_condition 结构化」等机制以**非破坏性**方式加进框架。

---

## 1. 背景与决策依据

### 1.1 三个概念别混淆
- **wquguru 逆向 prompt** = nof1.ai Alpha Arena 的「交易思路 + 输出格式」逆向文档(一段 prompt 文本)。源:https://gist.github.com/wquguru/7d268099b8c04b7e5b6ad6fae922ae83
- **opennof1** = 完整可运行的 AI 交易框架(抓行情/算指标/调 LLM/真实下单/记录)。源:https://github.com/wfnuser/opennof1
- **路线 A** = 用 opennof1 框架承载 wquguru 的「策略灵魂」,**不照搬其输出格式**。

### 1.2 为什么不能照搬 wquguru 的 prompt
wquguru 原版定义的输出字段是 `signal / coin / quantity / leverage / profit_target / stop_loss / invalidation_condition / confidence / risk_usd / justification`。
opennof1 框架**自己**定义了一套不同的字段(见 §2.2)。若把 wquguru 的 JSON 定义塞进 `trading_strategy`,会与框架的 system prompt 冲突 → LLM 输出无法解析 → `parse_json_response` 失败 → 全部降级为 `HOLD`(什么都不做)。

**因此:`trading_strategy` 里只放「分析方法 + 风控 + 纪律 + 决策流程」,绝不重定义 JSON 或动作枚举。**

---

## 2. 已核实的代码事实(Codex 必须以此为准)

### 2.1 prompt 三层覆盖(`backend/services/prompt_service.py`)
- 优先级:**数据库 SystemConfig(key="trading_strategy") > `agent.yaml` 的 `agent.trading_strategy` > 代码常量 `DEFAULT_TRADING_STRATEGY`**。
- `get_trading_strategy()` 返回最终策略文本;`set_trading_strategy()` 写入数据库(网页改即走这条)。
- 有内存缓存(`_strategy_cache`),改数据库后缓存失效逻辑需注意(若改框架,留心缓存刷新)。

### 2.2 ★框架的输出契约(`backend/agent/nodes/analysis_node.py` 中的 `SymbolDecision`)
LLM 必须输出的 JSON 字段(**这是硬约束**):
```
symbol            : str   例 "ETHUSDT"
action            : str   枚举: OPEN_LONG | OPEN_SHORT | CLOSE_LONG | CLOSE_SHORT | HOLD
reasoning         : str   决策理由(把 confidence/invalidation/risk 用文字写这里)
position_size_usd : float 仅开仓有效;期望仓位的【美元价值】(非币数量)
stop_loss_price   : float 仅开仓;止损【价格】
take_profit_price : float 仅开仓;止盈【价格】
```
顶层还有 `overall_summary: str`。
**注意差异**:框架用「美元价值」非「币数量」;杠杆**不由 LLM 指定**(配置层统一设);平仓拆成 CLOSE_LONG/CLOSE_SHORT(全平,无部分平仓)。

### 2.3 prompt 拼装方式(`analysis_node.py`)
- 框架先跑 ReAct agent 抓数据算指标 → 得到 `analysis_content`。
- 再生成固定 `system_prompt`(含账户状态、动作定义、JSON 格式要求)。
- **`trading_strategy` 作为 `HumanMessage` 传入**(用户策略指引),system_prompt 作为 `SystemMessage`。
- 非 gpt-4o 模型走 JSON mode + `parse_json_response()` 正则提取;解析失败 → 全 `HOLD`。

### 2.4 下单执行(`backend/trading/binance_futures.py`、`trading_execution_node.py`)
- 执行顺序:**先全部平仓 → 重查余额 → 再全部开仓**(防资金算错)。
- 方法:`open_long/open_short`(内部 `set_leverage` + 市价单 + 挂 SL/TP)、`close_long/close_short`、`format_quantity`(按交易对精度)。
- 杠杆来自 `config.exchange.default_leverage`,保证金 `margin_mode`(默认 cross)。

### 2.5 配置(`backend/config/agent.yaml`)
- `agent.model_name="deepseek-chat"`,`base_url="https://api.deepseek.com/v1"`,`api_key="${OPENAI_API_KEY}"`。
- `symbols=[ETHUSDT,SOLUSDT,DOGEUSDT,XRPUSDT]`,`timeframes=[3m,1h,4h]`,`decision_interval=180`。
- `exchange.testnet=false`(**Codex 必须改为 true 做验证**),testnet 端点已内置。
- `default_leverage=1`,`margin_mode="cross"`。

### 2.6 运行环境(无 Docker)
- 系统依赖:TA-Lib(`brew install ta-lib` / `apt-get install libta-lib-dev`)。
- 后端:`cd backend && uv sync && uv run python main.py`。
- 前端:`cd frontend && pnpm install && pnpm run dev`(http://localhost:3000)。
- 高危网页操作默认禁用,需 `ALLOW_CONTROL_OPERATIONS=true`。
- 协议:**Apache 2.0**。

---

## 3. 主任务(P0,不改代码)

**目标**:把 `trading_strategy` 替换为 wquguru 风格策略并验证生效。

**输入素材**:策略全文见同目录文件 `trading_strategy_wquguru.md`(含中/英两版,已对齐 §2.2 字段)。优先用中文版(DeepSeek 中文更强)。

**执行步骤**:
1. `git clone` / `git pull` 最新 opennof1。
2. 装依赖(§2.6),`cp backend/.env.example backend/.env` 并填 `OPENAI_API_KEY`(DeepSeek)+ 币安**测试网** Key/Secret。
3. 改 `backend/config/agent.yaml`:`exchange.testnet: true`。
4. 把 `trading_strategy_wquguru.md` 中文版全文写入 `agent.yaml` 的 `agent.trading_strategy`(保持 YAML 块缩进);或启动后用网页/接口写库(优先级更高)。
5. 启动后端 + 前端,跑 ≥5 个决策周期。

**验收标准(P0 完成定义)**:
- [ ] 后端日志无「解析 JSON 响应失败」;`trading decision` 中每个 `action` 都是 5 个合法枚举之一。
- [ ] 至少出现过一次因「信号不一致」而 `HOLD` 的决策(证明纪律生效,不是乱开仓)。
- [ ] 开仓决策的 `stop_loss_price`/`take_profit_price` 方向正确(多头:SL<现价<TP;空头相反)。
- [ ] 面板正常展示测试网持仓与盈亏。
- [ ] `position_size_usd` 不超过可用余额 20%(策略约束体现)。

**若验收失败的排查方向**:
- 解析失败 → 检查策略文本里是否误含 JSON/动作枚举的重定义,删掉。
- AI 总 HOLD/总满仓 → 检查策略文本是否被正确加载(看日志「使用…交易策略配置」那行的来源)。
- 缓存未刷新 → 重启后端或检查 `prompt_service` 缓存失效。

---

## 4. 进阶任务(P1,可选,需改框架代码 — 谨慎,保持非破坏)

> 这些是 wquguru prompt 里有、但 opennof1 现在没有的机制。**每项都需先在测试网验证,且不得破坏 §2.2 的对外 JSON 契约。** 建议每项单独 PR、可回滚。

### P1-A:Sharpe / 表现反馈回灌(对应 wquguru 的「自我校准」)
- 现状:框架不向 prompt 注入近期表现。
- 目标:在 `analysis_node` 拼 system_prompt 时,读取近 N 轮的盈亏/胜率(`history_service.py` / 数据库),作为「近期表现反馈」文字注入,引导 AI 自我校准。
- 验收:注入文本出现在发给 LLM 的消息中;亏损序列后 AI 倾向缩小仓位(行为可观察)。

### P1-B:invalidation_condition 结构化(对应 wquguru 的「失效条件」字段)
- 现状:框架 `SymbolDecision` 无此字段,只能塞进 `reasoning`。
- 目标:给 `SymbolDecision` 增加可选字段 `invalidation_condition: Optional[str]`,并在 system_prompt 的 JSON schema 里同步声明、存库展示。
- ⚠️ 这是**改对外契约**,务必同步改:Pydantic 模型、json_schema 文本、`parse_json_response`、数据库模型、前端展示。漏一处会解析失败。

### P1-C:多时间框架/指标扩展
- 现状:已支持 3m/1h/4h + RSI/MACD/EMA/NATR。
- 可选:加布林带、成交量分布、Funding/OI 的更细注入(wquguru 强调 OI 与 Funding)。在 `analysis_tools.py` / `market` 层扩展。

### P1-D:风控熔断(对应 wquguru 的回撤/单日亏损限制)
- 目标:账户从峰值回撤 >X% 或单日亏损 >Y% 时,强制只允许 HOLD/CLOSE。可在 `trading_execution_node` 前加一道闸,或在 system_prompt 注入硬约束 + 执行层兜底。
- 验收:人为构造亏损触发后,系统拒绝新开仓。

---

## 5. 防坑清单(Codex 务必牢记)
1. **测试网优先**:任何验证都在 `testnet: true`;真钱前需人工二次确认。
2. **不破坏 JSON 契约**:P0 绝不在策略文本里重定义字段;P1-B 改契约要全链路同步。
3. **币安期货下单精度**:数量要过 `format_quantity`(精度)和最小名义价值;否则下单被拒。
4. **杠杆不由 LLM 出**:别让策略文本要求 AI 指定 leverage。
5. **缩进**:`agent.yaml` 是 YAML,`trading_strategy: |` 块缩进错会启动失败。
6. **缓存**:改数据库策略后注意 `prompt_service` 缓存刷新。
7. **密钥安全**:`.env` 不入 git;币安 API 关提现、限 IP、只开读取+期货。
8. **语言**:DeepSeek 用中文策略服从度更好;换模型时同步调 `model_name`/`base_url`。

## 6. 需 Codex 二次核实的点(快照可能已变)
- `SymbolDecision` 字段是否新增/改名(以最新 `analysis_node.py` 为准)。
- 是否已新增 Docker(本快照无)。
- 网页改策略的具体接口/路由(`backend/api/routes.py`)与前端入口。
- `history_service.py` 是否已暴露现成的「近期表现」聚合(影响 P1-A 工作量)。

## 7. 参考文件(同目录)
- `trading_strategy_wquguru.md` — 待写入的策略全文(中英),含字段对照表。
- `nof1_reverse_prompt_zh_en.md` — wquguru 逆向 prompt 完整中英对照(策略灵魂的原始出处)。

## 8. 来源
- opennof1 源码:https://github.com/wfnuser/opennof1(`analysis_node.py`/`prompt_service.py`/`agent.yaml`/`binance_futures.py`/`workflow.py`)
- wquguru 逆向 prompt:https://gist.github.com/wquguru/7d268099b8c04b7e5b6ad6fae922ae83
- 部署/环境:https://github.com/wfnuser/opennof1/blob/main/README_zh.md 、 ENVIRONMENT_zh.md
- 币安测试网:https://testnet.binancefuture.com/
