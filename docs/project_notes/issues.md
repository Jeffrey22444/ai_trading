# Work Log

This is a concise project work log. Use GitHub commits and issues as the source of truth when available.

## Current Entries

### 2026-06-22 - Local Ops: Regime Deterministic Execution Core
- **Status**: In Progress
- **Description**: Created branch `regime` from clean `main` and added deterministic regime execution primitives for config/schema validation, regime normalization, router, F1-F4/Q scoring, direction edge rules, risk budget/gates, order construction, post-fill protection, position state transitions, reconciliation, and loop gating.
- **URL**: local branch `regime`
- **Notes**: Baseline backend tests passed before edits (`112 passed, 1 warning`). Current backend tests pass (`136 passed, 1 warning`). AI analysis now outputs only regime classification; deterministic code converts regime + F1-F4/Q + Direction + existing quant guardrails into entry/hold decisions and applies the regime risk gate. Execution uses bounded retries, persists position state in the existing analysis JSON, and releases capital only after the post-close position refresh confirms flat.

### 2026-06-22 - GH: Revert AI_trading Root Migration And Keep Work Log Tracked
- **Status**: Completed
- **Description**: Reverted the repository-root migration so GitHub content returns to the `opennof1` project root layout, while keeping workspace work-log files under version control.
- **URL**: https://github.com/Jeffrey22444/ai_trading
- **Notes**: `AGENTS.md` and `docs/project_notes/` are retained in the tracked tree; local checkout is intended to use `opennof1/` as the Git worktree root again.

### 2026-06-22 - GH: Promote AI_trading As Repository Root
- **Status**: Completed
- **Description**: Moved Git version control from `opennof1/` to the `AI_trading/` workspace root so the repository can include `opennof1/`, `docs/project_notes/`, and root-level agent instructions.
- **URL**: https://github.com/Jeffrey22444/ai_trading
- **Notes**: Preserved the existing Git remote and history; added a root `.gitignore` aligned with the existing project ignores.

### 2026-06-22 - Local Ops: Profit Lock Position Protection
- **Status**: Completed
- **Description**: Created branch `profit-lock` and added code-level position management: in-memory peak-profit tracking, break-even stop metadata, trailing-stop exit protection, explicit `ENTRY_HOLD`/`POSITION_HOLD` semantics, and a workflow `exit_decision` step between entry AI analysis and execution.
- **URL**: local branch `profit-lock`
- **Notes**: Backend pytest passed with `112 passed, 1 warning`; scoped Ruff on changed backend files passed; frontend production build passed after rerunning outside sandbox due Next.js IPC listen permission.

### 2026-06-21 - Local Ops: Ponytail Overengineering Cleanup
- **Status**: Completed
- **Description**: Created branch `pony-fix` and applied the Ponytail audit cleanup: removed stale Binance-era spec docs, old standalone PnL analysis scripts, the single-implementation exchange abstraction layer, the redundant market-data wrapper, duplicate `requirements.txt`, and unused runtime dependencies.
- **URL**: local branch `pony-fix`
- **Notes**: Backend pytest passed with `106 passed, 1 warning`; scoped Ruff on changed backend files passed. Full backend Ruff still reports pre-existing unrelated cleanup issues in untouched modules/scripts.

### 2026-06-21 - Local Ops: Fix 3m Entry Quality Freshness Misclassification
- **Status**: Completed
- **Description**: Fixed conservative entry quality freshness so normal 3m K-lines around 190 seconds old no longer trigger stale-data HOLD, while genuinely stale 3m data still blocks entries.
- **URL**: local backend tests
- **Notes**: Added timeframe-aware freshness (`timeframe duration + 75s buffer`), explicit Kline/IndicatorFrame open and close timestamps, and checks fields for `market_data_allowed_age_seconds` and `timestamp_source`. Targeted tests passed with `39 passed`; full backend pytest passed with `106 passed`.

### 2026-06-18 - Local Ops: Strategy v2 Conservative Entry Safety
- **Status**: Completed
- **Description**: Implemented the 第3版策略 safety task list on branch `第3版策略`: conservative entry-quality filtering, reference price/timeframe/timestamp observability, execution-time price drift/chase protection, and stricter AI strategy discipline.
- **URL**: local branch `第3版策略`
- **Notes**: Backend pytest passed with `101 passed`; targeted quant/risk/trader tests passed with `45 passed`; scoped Ruff on changed backend files passed. Full backend Ruff still reports pre-existing unrelated cleanup issues in old analysis scripts and unused imports.

### 2026-06-18 - Local Ops: Remove Core-Symbol D5 Floor
- **Status**: Completed
- **Description**: Adjusted strategy v2 D5 scoring so BTC/ETH/SOL no longer receive an unconditional minimum D5 score of 1 when treated as core symbols.
- **URL**: local backend tests
- **Notes**: Core-symbol D5 now reflects only the symbol's own configured trend. ETH/SOL/BTC still are not hard-vetoed by opposite BTC benchmark direction, while non-core symbols continue to use benchmark-context D5 logic. Targeted quant tests and full backend pytest passed; full-repo ruff/black still report pre-existing unrelated cleanup issues.

### 2026-06-18 - Local Ops: Fix Frontend Cycle Timezone Display
- **Status**: Completed
- **Description**: Updated the frontend cycle timestamp display to follow Beijing time instead of browser/default timezone parsing.
- **URL**: local frontend
- **Notes**: Added `frontend/src/lib/time.ts` and wired `DecisionsList` to format backend timestamps as `Asia/Shanghai` with a `BJT` suffix. Verified sample `2026-06-18 08:23:13` displays as `06/18 16:23 BJT`; TypeScript and frontend production build passed.

### 2026-06-18 - Local Ops: Add Existing-Position Exit Guardrail
- **Status**: Completed
- **Description**: Fixed the Cycle 168 failure mode where AI held existing SHORT positions even after quantified long-side evidence emerged, because `action_allowed=false` was mistakenly treated as a reason not to close.
- **URL**: local backend/config/docs
- **Notes**: Added `scoring.exit_score_threshold` with default `5.0`; `analysis_node.py` now converts HOLD or blocked opposite opens into `CLOSE_SHORT`/`CLOSE_LONG` when the opposite score reaches the exit threshold and exceeds the current-position side score. Updated the runtime SQLite strategy text and `backend/config/trading_strategy.md` so opening blocks and closing permissions are explicitly separate.

### 2026-06-18 - Local Ops: Consolidate Runtime Strategy Source
- **Status**: Completed
- **Description**: Consolidated strategy handling so the runtime strategy is edited through the frontend and stored in SQLite, while `backend/config/trading_strategy.md` is the versioned template used for initialization and Reset.
- **URL**: local backend/frontend/docs
- **Notes**: Removed the large strategy body from `agent.yaml`; `agent.yaml` now holds quant parameters only. `prompt_service.py` no longer uses `database > agent.yaml > code default` strategy precedence. Settings still supports direct strategy editing, and Reset restores the database strategy from the template.

### 2026-06-18 - Local Ops: Main Branch Receives Strategy v2 Merge
- **Status**: Completed
- **Description**: Confirmed the former `strategy-v2-quant-guardrails` work is now contained in `main`, after the user renamed the previous `migration/hyperliquid-testnet` line to `main` and manually deleted the strategy branch.
- **URL**: local Git tracking `origin/main`
- **Notes**: Local `main` and tracked `origin/main` both point to `9a91e43 feat: add strategy v2 quant guardrails`; `git branch --contains 9a91e43` shows `main`. A direct `git ls-remote origin refs/heads/main` verification attempted afterward but GitHub returned `Empty reply from server`, so the conclusion is based on the current local remote-tracking ref and branch containment checks.

### 2026-06-18 - Local Ops: Implement Strategy v2 Quant Guardrails
- **Status**: Completed
- **Description**: Added backend deterministic strategy guardrails for v2: multi-dimensional LONG/SHORT scoring, objective ATR/swing stops, Kelly-based position sizing with a 100 USD minimum, and decision-level leverage enforcement.
- **URL**: local branch `strategy-v2-quant-guardrails`
- **Notes**: This is a code-backed strategy upgrade, not prompt-only. ETH/SOL are treated as core high-liquidity assets; BTC is a risk backdrop, not a hard veto for them. Runtime SQLite strategy override was synchronized to the code-guardrail v2 prompt. Follow-up alignment added API/frontend quant fields, strategy placeholder validation for `quant_guardrail.*`, a config operation guide, and the workspace directory map update. Backend pytest passed with `73 passed`; targeted Ruff checks passed; frontend production build passed outside sandbox due Next.js IPC listen permissions; independent sub-agent acceptance passed with merge-before-commit note to include untracked quant files. The work was committed as `9a91e43 feat: add strategy v2 quant guardrails` and is now contained in `main`.

### 2026-06-17 - Local Ops: Sweep Hyperliquid-Only Docs And Validation Scripts
- **Status**: Completed
- **Description**: Removed stale Binance-era and `BTCUSDT`/`ETHUSDT` local-validation leftovers from runtime docs and helper scripts, and aligned examples with the Hyperliquid-only symbol contract `BTC`/`ETH`/`SOL`.
- **URL**: local docs/backend/frontend
- **Notes**: Rewrote `opennof1/contracts/api.md`, corrected `quickstart.md` and `quickstart_zh.md`, updated `backend/test_api.sh`, normalized helper-script examples, changed `BalanceSnapshot.currency` default to `USDC`, and kept legacy symbol references only as explicitly labeled compatibility context. Targeted backend verification passed with `14 passed`.

### 2026-06-16 - Local Ops: Fix Hyperliquid Trade Stats Field Mapping
- **Status**: Completed
- **Description**: Fixed trading metrics so `/api/v1/trading/stats` falls back to Hyperliquid `closedPnl` when `realizedPnl` is absent, restoring non-zero `winRate`, `profitLossRatio`, and `expectancy`.
- **URL**: local backend
- **Notes**: Verified against the current local SQLite trade history; targeted backend test coverage now includes both `realizedPnl` and `closedPnl` cases.

### 2026-06-16 - Local Ops: Replace Placeholder Risk Metrics With Trade Quality Metrics
- **Status**: Completed
- **Description**: Updated `/api/v1/trading/stats` and the dashboard stats strip to expose and display `winRate`, `profitLossRatio`, and `expectancy` derived from closed-order realized PnL after fees.
- **URL**: local backend/frontend
- **Notes**: Removed the old placeholder `maxDrawdown` and `sharpeRatio` fields from the stats contract; targeted backend test coverage passed and frontend TypeScript validation passed.

### 2026-06-16 - Local Ops: Remove Outdated Binance-Era Tutorial
- **Status**: Completed
- **Description**: Deleted `opennof1_架构与部署教程.md` because it still documented the old Binance/WebSocket architecture and could mislead current Hyperliquid-only work.
- **URL**: local docs
- **Notes**: Also removed the stale reference from `HANDOFF_codex_opennof1_wquguru.md`.

### 2026-06-16 - Local Ops: Promote Full Wquguru-Derived Strategy Into agent.yaml
- **Status**: Completed
- **Description**: Replaced the shortened `agent.trading_strategy` text in `opennof1/backend/config/agent.yaml` with the full Chinese strategy adapted from `trading_strategy_wquguru.md`.
- **URL**: local config
- **Notes**: Historical note from before the 2026-06-18 strategy-source consolidation: runtime strategy precedence then was `database > agent.yaml > code default`; if the backend had cached a prior config-backed strategy, restart the backend or clear cache through the strategy reset/write path before expecting immediate live effect. Current runtime strategy source is SQLite, with `backend/config/trading_strategy.md` used for initialization and Reset.

### 2026-06-16 - Local Ops: Add Explicit Strategy Refresh Endpoint
- **Status**: Completed
- **Description**: Added a controlled strategy refresh path that reloads `backend/config/agent.yaml` into the shared in-memory config object and clears the prompt-service strategy cache.
- **URL**: local API/UI
- **Notes**: New backend route is `POST /api/v1/trading/strategy/refresh`; settings page now exposes `REFRESH ACTIVE CONFIG`. This solves both stale `prompt_service` cache and stale boot-time `config.agent.trading_strategy` state.

### 2026-06-16 - Local Ops: Guard ReAct Analysis Tool Against Ambiguous Symbol Input
- **Status**: Completed
- **Description**: Hardened the technical-analysis tool so ambiguous ReAct tool input now falls back to all configured symbols instead of generating a fake symbol that always misses the K-line cache.
- **URL**: local backend tests
- **Notes**: Added regression coverage in `opennof1/backend/tests/test_analysis_tools.py`; targeted validation passed with `3 passed`.

### 2026-06-16 - Local Ops: Align Strategy Indicators With Analysis Pipeline
- **Status**: Completed
- **Description**: Extended the backend analysis pipeline to surface ATR, nearest support/resistance, open interest (OI), and funding rate alongside existing EMA/MACD/RSI/NATR outputs.
- **URL**: local backend tests
- **Notes**: Added a shared derivatives-context cache refreshed by `market_data_client`; targeted validation passed with `11 passed`.

### 2026-06-16 - Local Ops: Add Strategy Field Contract And Market Context Endpoint
- **Status**: Completed
- **Description**: Added `/api/v1/market/context/{symbol}` to expose the structured market context the agent can reference, plus strategy schema/validation endpoints and write-time rejection for unknown backend field placeholders.
- **URL**: local backend tests
- **Notes**: Strategies can now explicitly reference backend fields with placeholders like `{{timeframes.4h.atr}}`; targeted validation passed with `15 passed`.

### 2026-06-16 - Local Ops: Replace Hardcoded WIN RATE With Real-Time Backend Calculation
- **Status**: Completed
- **Description**: Changed `/api/v1/trading/stats` to sync recent trades before calculating stats and derive `winRate` from stored trade history using realized PnL after fees.
- **URL**: local backend tests
- **Notes**: `WIN RATE` is no longer the hardcoded placeholder `65`; targeted validation passed with `17 passed`.

### 2026-06-16 - GH: Hyperliquid-Only Runtime Cleanup
- **Status**: Completed
- **Description**: Removed Binance runtime code, Binance symbol mapping, old market API/WebSocket clients, and stale exchange docs; runtime now rejects non-Hyperliquid exchange names.
- **URL**: https://github.com/Jeffrey22444/ai_trading
- **Notes**: Commit `585876a refactor: make runtime hyperliquid only`.

### 2026-06-16 - GH: Technical Analysis Symbol Normalization
- **Status**: Completed
- **Description**: Fixed AI tool cache misses when the LLM passed `BTCUSDT`/combined symbol text instead of cache keys `BTC`, `ETH`, `SOL`.
- **URL**: https://github.com/Jeffrey22444/ai_trading
- **Notes**: Commit `a1e8880 fix: normalize technical analysis symbols`; backend tests `55 passed`.

### 2026-06-16 - Local Ops: Manual Trading Control Card
- **Status**: Completed
- **Description**: Documented backend/frontend start commands and manual automatic-trading control commands for the user.
- **URL**: none
- **Notes**: Backend service occupies its terminal; run `curl` control commands from a second terminal.

### 2026-06-16 - Project Memory System Relocated to AI_trading
- **Status**: Completed
- **Description**: Created workspace-level `docs/project_notes/` under `/Users/jeffrey/Documents/AI_trading` and pointed `opennof1` tool entrypoints to it.
- **URL**: local docs
- **Notes**: Check these notes before debugging recurring issues or changing exchange architecture.

### 2026-06-15 - Hyperliquid Testnet Migration and Acceptance
- **Status**: Completed
- **Description**: Migrated local trading path to Hyperliquid testnet and verified account setup, faucet funds, API Wallet usage, and acceptance workflow.
- **URL**: https://github.com/Jeffrey22444/ai_trading
- **Notes**: Use `opennof1/LOCAL_RUNBOOK.md` and `opennof1/backend/scripts/p0_acceptance.py` for final acceptance context.
