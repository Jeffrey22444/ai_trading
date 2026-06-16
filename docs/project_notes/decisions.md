# Architectural Decisions

Use this file for ADR-style decisions. Check it before proposing architecture changes.

## Current Decisions

### ADR-001: Runtime Is Hyperliquid-Only (2026-06-16)

**Context:**
- The project shifted from Binance/Demo Trading to Hyperliquid testnet.
- Keeping multiple exchange paths created ambiguity in config, symbols, docs, and tests.

**Decision:**
- Runtime supports Hyperliquid perpetuals only.
- `ExchangeConfig` rejects non-`hyperliquid` names.
- Trading uses Hyperliquid CCXT swap symbols at the boundary: `BASE/USDC:USDC`.

**Alternatives Considered:**
- Keep Binance compatibility -> Rejected: higher maintenance cost and easy to call the wrong exchange path.
- Build a generic multi-exchange layer now -> Rejected: premature for the current testnet objective.

**Consequences:**
- Clearer runtime and safer validation.
- Reintroducing another exchange requires a new explicit ADR and tests.

### ADR-002: Market Data Uses CCXT REST Polling, Not WebSocket (2026-06-16)

**Context:**
- Hyperliquid migration needed stable K-line data for AI decisions.
- Existing WebSocket naming came from the old Binance implementation.

**Decision:**
- `HyperliquidMarketClient` fetches OHLCV with CCXT REST polling.
- Polling refreshes configured symbols/timeframes and writes to the shared `kline_cache`.
- Health is based on recent successful refresh freshness, not a WebSocket connection.

**Alternatives Considered:**
- Keep WebSocket terminology -> Rejected: misleading and caused incorrect health semantics.
- Add true WebSocket immediately -> Deferred until a clear need exists.

**Consequences:**
- Simpler, debuggable market data path.
- Not tick-real-time; default polling interval is 30 seconds.

### ADR-003: AI Strategy Text Is Runtime-Editable in SQLite (2026-06-16)

**Context:**
- The settings page lets the user edit trading strategy text during local operation.
- Strategy edits should affect decisions without requiring code edits.

**Decision:**
- Strategy priority is database > `backend/config/agent.yaml` > code default.
- Frontend `SAVE STRATEGY` writes to SQLite via `POST /api/v1/trading/strategy`.
- `RESET TO DEFAULT` deletes the database override and falls back to `agent.yaml`.

**Alternatives Considered:**
- Write frontend edits directly to `agent.yaml` -> Rejected: unsafe for runtime edits and git noise.
- Keep strategy only in config files -> Rejected: slower iteration while testing.

**Consequences:**
- Frontend edits affect future AI decisions but do not produce git diffs.
- To make a strategy a permanent default, manually sync it into `agent.yaml` and commit.

### ADR-004: Automatic Trading Requires Explicit Start (2026-06-16)

**Context:**
- Backend startup must initialize market data safely without automatically starting AI trade decisions.
- The frontend has high-risk controls.

**Decision:**
- Backend market-data polling starts on API startup.
- The AI scheduler does not start automatically; use `POST /api/v1/agent/start` or the settings page control.
- Frontend control operations require `ALLOW_CONTROL_OPERATIONS=true`.
- `allow_live_trading: false` remains the default safety lock.

**Alternatives Considered:**
- Auto-start scheduler on backend startup -> Rejected: too risky for local testing.
- Always enable frontend controls -> Rejected: accidental clicks can trigger automated decision loops.

**Consequences:**
- Running backend is not the same as enabling automatic trading.
- Code reload can stop the scheduler; re-check `/api/v1/agent/status` after edits.

### ADR-005: Project Memory Lives in docs/project_notes (2026-06-16)

**Context:**
- The project has accumulated setup details, exchange decisions, safety constraints, and bug fixes across sessions.
- Future AI tools should not rediscover the same facts from scratch.

**Decision:**
- Store durable project memory in `docs/project_notes/` using four files: `bugs.md`, `decisions.md`, `key_facts.md`, and `issues.md`.
- Configure `CLAUDE.md` and `AGENTS.md` to check these files before architectural changes, debugging, and config lookup.

**Alternatives Considered:**
- Rely on chat history or handoff files only -> Rejected: not durable enough across tools and windows.
- Store memory in a hidden AI-specific folder -> Rejected: less discoverable for humans.

**Consequences:**
- Memory becomes normal project documentation.
- Entries must be kept concise and manually pruned when stale.

