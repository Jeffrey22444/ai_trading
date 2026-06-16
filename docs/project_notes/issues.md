# Work Log

This is a concise project work log. Use GitHub commits and issues as the source of truth when available.

## Current Entries

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

### 2026-06-16 - Project Memory System
- **Status**: Completed
- **Description**: Created `docs/project_notes/` memory files and configured project AI entrypoints to maintain them.
- **URL**: local docs
- **Notes**: Check these notes before debugging recurring issues or changing exchange architecture.

### 2026-06-15 - Hyperliquid Testnet Migration and Acceptance
- **Status**: Completed
- **Description**: Migrated local trading path to Hyperliquid testnet and verified account setup, faucet funds, API Wallet usage, and acceptance workflow.
- **URL**: https://github.com/Jeffrey22444/ai_trading
- **Notes**: Use `LOCAL_RUNBOOK.md` and `backend/scripts/p0_acceptance.py` for final acceptance context.

