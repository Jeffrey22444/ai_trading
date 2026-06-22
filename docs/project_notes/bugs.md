# Bug Log

This file tracks recurring or instructive bugs and the fixes that should be reused. Keep entries concise and dated.

## Current Entries

### 2026-06-21 - Entry Quality Misread Normal 3m K-Lines As Stale
- **Issue**: After conservative entry safeguards, AI decision cycles often forced HOLD because 3m market data age was around 190 seconds and exceeded the fixed 120-second stale threshold.
- **Root Cause**: `entry_quality` measured freshness from `IndicatorFrame.timestamp`, which was populated from `Kline.timestamp`; `Kline.timestamp` was the candle `open_time`, so normal 3m candles could appear nearly 180 seconds old before polling/network/scheduler delay.
- **Solution**: Added explicit `open_timestamp` and `close_timestamp` on `Kline`/`IndicatorFrame`, made entry freshness use close timestamp, and changed the allowed age to timeframe-aware duration plus a buffer.
- **Prevention**: Freshness checks for candle data should compare against close/update semantics and include timeframe duration, not just candle open time.

### 2026-06-18 - Duplicate Hyperliquid Trade Sync Broke Session
- **Issue**: After a BTC short opened, repeated stats/history syncs attempted to insert the same Hyperliquid `trade_id` and raised `sqlite3.IntegrityError: UNIQUE constraint failed: trade_records.trade_id`. The session then remained rolled back and later sync work failed.
- **Root Cause**: `sync_recent_trades()` could run concurrently from multiple frontend stats requests. `_save_trade_record()` used a per-row select-before-insert check, which is not safe against concurrent sessions or duplicate IDs returned in the same sync payload.
- **Solution**: Deduplicate trade payloads by `id`, prefetch existing trade IDs once per sync batch, skip known IDs before insert, and handle duplicate-key `IntegrityError` defensively.
- **Prevention**: Exchange history syncs must be idempotent at batch level; frontend polling may call stats endpoints concurrently.

### 2026-06-18 - Hyperliquid Testnet 504 Stopped Market Polling After Startup
- **Issue**: After refreshing the backend, Hyperliquid testnet returned CloudFront `504 Gateway Timeout` for `/info`; the backend still started, but market-data polling failed to start and would not retry unless the backend was restarted.
- **Root Cause**: `api/main.py` only created the polling task when the first `market_data_client.connect()` succeeded. A transient startup failure left `HyperliquidMarketClient.is_connected=False`, and `run_polling_loop()` was never scheduled.
- **Solution**: Start the polling task even when the first connection fails, and make `HyperliquidMarketClient.run_polling_loop()` retry `connect()` while disconnected. Add regression coverage in `backend/tests/test_hyperliquid_market.py`.
- **Prevention**: Startup market-data connection failures should degrade into background retry, not permanently disable polling.

### 2026-06-18 - Frontend Cycle Time Display Used Browser Timezone
- **Issue**: Cycle timestamps in the frontend showed incorrect hour values instead of Beijing time.
- **Root Cause**: Backend decision timestamps are stored without an explicit timezone, while the frontend parsed them with `new Date(timestamp)` and displayed them with the browser/default timezone.
- **Solution**: Add `frontend/src/lib/time.ts` to parse timezone-less backend timestamps as UTC and format cycle timestamps with `Asia/Shanghai`, displaying a `BJT` suffix. Use it in `DecisionsList`.
- **Prevention**: UI timestamp formatting should specify the target timezone explicitly; do not rely on browser defaults for persisted backend timestamps.

### 2026-06-18 - AI Held Opposing Shorts When Opening Guardrail Blocked
- **Issue**: Cycle 168 produced `HOLD` while BTC had a SHORT position and the quantified direction had turned LONG; ETH/SOL shorts were also held despite stronger long-side evidence.
- **Root Cause**: The analysis prompt said `action_allowed=false` only blocks opening, but there was no code-level existing-position exit guardrail. The LLM treated the opening block as a reason to keep holding the current short.
- **Solution**: Add a post-decision position-exit guardrail in `backend/agent/nodes/analysis_node.py`: existing SHORT closes when LONG score reaches `scoring.exit_score_threshold` and exceeds SHORT score; existing LONG closes on the inverse. Add regression tests in `backend/tests/test_analysis_response.py`.
- **Prevention**: Keep opening guardrails and existing-position exit guardrails separate in both code and strategy text. `action_allowed=false` must never be interpreted as blocking `CLOSE_LONG` or `CLOSE_SHORT`.

### 2026-06-16 - Hyperliquid Trade Metrics Showed All Zeros
- **Issue**: Dashboard `WIN RATE`, `P/L RATIO`, and `EXPECTANCY` displayed zero even though local trade history existed.
- **Root Cause**: Hyperliquid trade fills store realized close profit in `raw_data.info.closedPnl`, but the stats code only read `raw_data.info.realizedPnl`.
- **Solution**: Update trade-metric calculation to read `realizedPnl` first and fall back to `closedPnl`; add regression coverage in `backend/tests/test_trade_stats.py`.
- **Prevention**: When integrating exchange-specific trade history, inspect real stored `raw_data` before assuming normalized CCXT field names.

### 2026-06-16 - Running Backend Kept Using Old Strategy After agent.yaml Edit
- **Issue**: Editing `opennof1/backend/config/agent.yaml` did not immediately change live AI behavior in an already-running backend process.
- **Root Cause**: Two in-memory layers were stale: the shared boot-time `config.agent.trading_strategy` object and `backend/services/prompt_service.py`'s `_strategy_cache`.
- **Solution**: Add `POST /api/v1/trading/strategy/refresh` to reload the config object and clear the strategy cache; expose it in the settings page as `REFRESH ACTIVE CONFIG`.
- **Prevention**: After editing `agent.yaml`, either call the refresh endpoint/UI control or restart the backend before evaluating strategy behavior.

### 2026-06-16 - Technical Analysis Tool Reported Empty Cache
- **Issue**: New AI decision cycles said the technical analysis cache was empty even though `/api/v1/cache/info` showed 100 K-lines per symbol/timeframe.
- **Root Cause**: The LLM sometimes called the tool with `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, or combined symbol text, while the cache keys are logical symbols `BTC`, `ETH`, `SOL`.
- **Solution**: Normalize tool inputs with `from_exchange_symbol()` and support multi-symbol LLM input in `backend/agent/tools/analysis_tools.py`; normalize final decision symbols in `backend/agent/nodes/analysis_node.py`.
- **Prevention**: Any tool that reads market cache must normalize exchange-formatted symbols before lookup; keep tests in `backend/tests/test_analysis_tools.py`.

### 2026-06-16 - Frontend Showed Old "Cache Empty" Decisions
- **Issue**: Dashboard decision list kept showing old "缓存为空" summaries after market data had recovered.
- **Root Cause**: The frontend displays historical decisions; old cycles remain visible until newer cycles push them down the list.
- **Solution**: Verify live cache with `/api/v1/cache/info`, then inspect latest decisions with `/api/v1/decisions?limit=1&order=desc`.
- **Prevention**: Diagnose current backend state before assuming the visible frontend text is live state.

### 2026-06-16 - ReAct Tool Call Could Fabricate "No K-Line Data"
- **Issue**: Some new decision cycles intermittently claimed all symbols had no K-line data even though nearby cycles showed valid analysis again.
- **Root Cause**: The technical-analysis tool treated unrecognized or overly broad ReAct input as a literal symbol, producing guaranteed cache misses and misleading the final LLM summary into reporting empty market data.
- **Solution**: Change `backend/agent/tools/analysis_tools.py` to fall back to all configured symbols when no symbol can be parsed from the tool input, and lock it with a regression test in `backend/tests/test_analysis_tools.py`.
- **Prevention**: Any agent-facing market-data tool should treat ambiguous LLM input as a request for configured symbols, not as a synthetic cache key.

### 2026-06-15 - Cannot Use Existing User Address as Agent
- **Issue**: Hyperliquid rejected an API wallet setup with `Cannot use existing user address as agent`.
- **Root Cause**: The main/user wallet address was being reused as the API wallet/agent address.
- **Solution**: Use `HYPERLIQUID_WALLET_ADDRESS` for the main account and `HYPERLIQUID_PRIVATE_KEY` for a separate authorized API Wallet private key.
- **Prevention**: Never set the API Wallet private key to the main wallet private key; do not store secret values in memory or git.

### 2026-06-15 - Binance Runtime Leftovers After Hyperliquid Migration
- **Issue**: Runtime code and docs still had Binance clients, symbol mappings, and WebSocket wording after the Hyperliquid migration.
- **Root Cause**: Initial migration introduced Hyperliquid paths without deleting the old exchange abstraction surface.
- **Solution**: Removed Binance runtime files, deleted WebSocket client dependency, and made factory/config reject non-Hyperliquid exchanges.
- **Prevention**: Search for `binance`, `api_client`, `ws_client`, `websocket`, and symbol mappings after exchange migrations.
