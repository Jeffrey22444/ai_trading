# Key Facts

Store non-sensitive project facts here. Do not store API keys, private keys, wallet private keys, tokens, passwords, or `.env` values.

## Project Location

- Checkout path: `/Users/jeffrey/Documents/AI_trading/opennof1`
- Active branch: `migration/hyperliquid-testnet`
- User GitHub target: `https://github.com/Jeffrey22444/ai_trading`
- Local `origin` may point to upstream `https://github.com/wfnuser/OpenNof1.git`; verify before pushing.

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

- `.env` path: `backend/.env`; never print or commit it.
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
- Strategy is stored in SQLite `backend/data/trading.db` under `SystemConfig.key == "trading_strategy"`.
- Strategy priority: database > `backend/config/agent.yaml` > code default.
- Frontend edits do not modify `agent.yaml` or create git diffs.

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

- Local runbook: `LOCAL_RUNBOOK.md`
- Backend app: `backend/api/main.py`
- API routes: `backend/api/routes.py`
- Hyperliquid market data: `backend/market/hyperliquid_market.py`
- Shared market cache: `backend/market/data_cache.py`
- Technical analysis tool: `backend/agent/tools/analysis_tools.py`
- AI decision node: `backend/agent/nodes/analysis_node.py`
- Trader: `backend/trading/hyperliquid_trader.py`
- Symbol normalization: `backend/trading/symbols.py`
- Strategy service: `backend/services/prompt_service.py`

## Security Reminder

- Never store real private keys, API keys, or `.env` contents in this directory.
- If a command would expose secrets, stop and ask the user to run it locally.

