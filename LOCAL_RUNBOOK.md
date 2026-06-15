# Local Runbook

## Current Safety Defaults

- AI provider: DeepSeek (`deepseek-chat`)
- Market data: Binance Futures public test environment
- Trade execution: Binance Demo Trading through CCXT
- Live opening: disabled (`allow_live_trading: false`)
- Backend bind address: `127.0.0.1`
- Frontend control operations: disabled unless explicitly enabled

## Verified Startup Commands

Backend API and market-data service:

```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run python -m api.main
```

Frontend:

```bash
cd frontend
CI=true pnpm run dev
```

Open:

- Dashboard: http://localhost:3000
- Backend health: http://127.0.0.1:8000/api/v1/health
- Backend config: http://127.0.0.1:8000/api/v1/config

The scheduler does not start automatically. Start it only after the final
credential checks through `POST /api/v1/agent/start`.

## Credentials Required At Final Validation

Create `backend/.env` from `backend/.env.example`, then set:

```dotenv
OPENAI_API_KEY=<DeepSeek API key>
BINANCE_API_KEY=<Binance Demo Trading API key>
BINANCE_API_SECRET=<Binance Demo Trading API secret>
```

Use Binance Demo Trading credentials from:
https://demo.binance.com/en/my/settings/api-management

Do not use production Binance credentials while `allow_live_trading` is false.

## Verification Commands

```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check trading tests agent/nodes/trading_execution_node.py config/agent_config.py

# With the backend running and final credentials configured:
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/p0_acceptance.py

cd ../frontend
CI=true pnpm run build
```

`p0_acceptance.py` refuses to run unless DeepSeek, testnet mode, Binance Demo
Trading, and the live-trading lock are all configured correctly. It then runs
five real decision cycles against Demo Trading and checks the P0 acceptance
criteria automatically.
