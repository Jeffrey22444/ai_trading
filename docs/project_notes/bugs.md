# Bug Log

This file tracks recurring or instructive bugs and the fixes that should be reused. Keep entries concise and dated.

## Current Entries

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

