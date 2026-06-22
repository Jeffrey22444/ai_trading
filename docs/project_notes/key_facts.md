# Key Facts

Store non-sensitive project facts here. Do not store API keys, private keys, wallet private keys, tokens, passwords, or `.env` values.

## Project Location

- Workspace path: `/Users/jeffrey/Documents/AI_trading`
- Active checkout path: `/Users/jeffrey/Documents/AI_trading/opennof1`
- Active branch in `opennof1`: `migration/hyperliquid-testnet`
- User GitHub target: `https://github.com/Jeffrey22444/ai_trading`
- `opennof1` local `origin` may point to upstream `https://github.com/wfnuser/OpenNof1.git`; verify before pushing.

## Runtime Architecture

- Backend: FastAPI, SQLite, SQLAlchemy, LangGraph/LangChain, CCXT.
- Frontend: Next.js 14, TypeScript, Tailwind.
- AI provider default: DeepSeek via OpenAI-compatible API (`deepseek-chat`).
- Exchange runtime: Hyperliquid perpetuals only.
- Market data: Hyperliquid CCXT REST OHLCV polling.
- Trading execution: Hyperliquid CCXT swap orders.
- Logical symbols used by AI/API/UI/cache: `BTC`, `ETH`, `SOL`.
- Exchange symbols should only appear at CCXT boundary: `BASE/USDC:USDC`.
- Configured timeframes: `3m`, `1h`, `4h`.

## Local Ports and URLs

- Backend API: `http://127.0.0.1:8000`
- Frontend: `http://localhost:3000`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`
- Cache info: `http://127.0.0.1:8000/api/v1/cache/info`
- Market context: `http://127.0.0.1:8000/api/v1/market/context/BTC`
- Agent status: `http://127.0.0.1:8000/api/v1/agent/status`

## Local Commands

**Backend:**
```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/backend
UV_CACHE_DIR=/tmp/uv-cache uv run python -m api.main
```

**Frontend read-only mode:**
```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/frontend
CI=true pnpm run dev
```

**Frontend control mode:**
```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/frontend
ALLOW_CONTROL_OPERATIONS=true CI=true pnpm run dev
```

**Agent controls:**
```bash
curl http://127.0.0.1:8000/api/v1/agent/status
curl -X POST http://127.0.0.1:8000/api/v1/agent/start
curl -X POST http://127.0.0.1:8000/api/v1/agent/stop
```

## Credentials and Safety

- `.env` path: `opennof1/backend/.env`; never print or commit it.
- Required env vars:
  - `OPENAI_API_KEY`
  - `HYPERLIQUID_WALLET_ADDRESS`
  - `HYPERLIQUID_PRIVATE_KEY`
- `HYPERLIQUID_WALLET_ADDRESS` is the Hyperliquid main account address.
- `HYPERLIQUID_PRIVATE_KEY` is the authorized API Wallet private key, not the main wallet private key.
- Default safety:
  - `exchange.testnet: true`
  - `exchange.allow_live_trading: false`
  - Frontend control actions blocked unless `ALLOW_CONTROL_OPERATIONS=true`.
- Hyperliquid testnet account currently observed around `$999` USDC equity during local testing.

## Strategy Persistence

- Frontend strategy edits call `POST /api/v1/trading/strategy`.
- Active-config refresh calls `POST /api/v1/trading/strategy/refresh`.
- Strategy is stored in SQLite `opennof1/backend/data/trading.db` under `SystemConfig.key == "trading_strategy"`.
- Strategy priority: database > `opennof1/backend/config/agent.yaml` > code default.
- As of 2026-06-16, the checked local database has no `trading_strategy` override row, so the effective default strategy comes from `agent.yaml`.
- `POST /api/v1/trading/strategy/refresh` reloads `backend/config/agent.yaml` into the shared in-memory config object and clears the prompt-service strategy cache for the already-running backend process.
- Frontend edits do not modify `agent.yaml` or create git diffs.
- Strategy field contract endpoints:
  - `GET /api/v1/trading/strategy/schema`
  - `POST /api/v1/trading/strategy/validate`
- Explicit backend field references in strategy text must use placeholders such as `{{timeframes.4h.atr}}`; unknown placeholders are rejected on `POST /api/v1/trading/strategy`.

## Verification Commands

```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/backend
UV_CACHE_DIR=/tmp/uv-cache uv run --offline pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run --offline ruff check agent/tools/analysis_tools.py agent/nodes/analysis_node.py tests/test_analysis_tools.py
```

Full backend test status after symbol-normalization fix:
- 2026-06-16: `55 passed, 1 warning`

Frontend production build previously passed when run outside the sandbox:
```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/frontend
CI=true pnpm run build
```

## Important Files

- Local runbook: `opennof1/LOCAL_RUNBOOK.md`
- Backend app: `opennof1/backend/api/main.py`
- API routes: `opennof1/backend/api/routes.py`
- Hyperliquid market data: `opennof1/backend/market/hyperliquid_market.py`
- Shared market cache: `opennof1/backend/market/data_cache.py`
- Technical analysis tool: `opennof1/backend/agent/tools/analysis_tools.py`
- Analysis output now includes EMA, MACD, RSI, ATR, NATR, nearest support/resistance, and cached derivative context (`OI`, `Funding`, mark/index price).
- AI decision node: `opennof1/backend/agent/nodes/analysis_node.py`
- Trader: `opennof1/backend/trading/hyperliquid_trader.py`
- Symbol normalization: `opennof1/backend/trading/symbols.py`
- Strategy service: `opennof1/backend/services/prompt_service.py`
- Derivatives context cache: `opennof1/backend/market/derivatives_cache.py`
- Strategy refresh control: `opennof1/backend/api/routes.py` and `opennof1/frontend/src/app/settings/page.tsx`

## Local Docs Status

- `opennof1_架构与部署教程.md` was deleted on 2026-06-16 because it described the old Binance/WebSocket path and had become misleading after the Hyperliquid-only migration.
- `trading_strategy_wquguru.md` is currently a source/reference document; its full Chinese strategy text has already been promoted into `opennof1/backend/config/agent.yaml`.

## Security Reminder

- Never store real private keys, API keys, or `.env` contents in this directory.
- If a command would expose secrets, stop and ask the user to run it locally.
