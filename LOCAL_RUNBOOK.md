# Local Runbook

## Current Safety Defaults

- AI provider: DeepSeek (`deepseek-chat`)
- Market data: Hyperliquid testnet through CCXT polling
- Trade execution: Hyperliquid testnet through CCXT
- Live opening: disabled (`allow_live_trading: false`)
- Backend bind address: `127.0.0.1`
- Frontend control operations: disabled unless explicitly enabled
- Logical symbols used by AI/API/UI: `BTC`, `ETH`, `SOL`
- Exchange symbols used only at the CCXT boundary: `BASE/USDC:USDC`
- CCXT is pinned to `4.5.58`, the verified version that loads Hyperliquid
  testnet markets correctly.

## Verified Startup Commands

Backend API and market-data polling service:

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

The scheduler does not start automatically. Start it only after credential and
safety checks through `POST /api/v1/agent/start`.

## Credentials Required At Final Validation

Create `backend/.env` from `backend/.env.example`, then set:

```dotenv
OPENAI_API_KEY=<DeepSeek API key>
HYPERLIQUID_WALLET_ADDRESS=<dedicated Hyperliquid testnet wallet address>
HYPERLIQUID_PRIVATE_KEY=<dedicated Hyperliquid testnet wallet private key>
```

Fund the dedicated wallet with Hyperliquid testnet faucet USDC before final
validation. Never reuse a funded mainnet wallet private key.

## Verification Commands

```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check config/agent_config.py trading/factory.py trading/hyperliquid_trader.py trading/symbols.py trading/history_service.py trading/position_service.py market/hyperliquid_market.py agent/nodes/trading_execution_node.py api/routes.py tests scripts/p0_acceptance.py scripts/hyperliquid_acceptance.py

# With Hyperliquid testnet credentials and faucet USDC configured:
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/hyperliquid_acceptance.py

# With the backend running and all final credentials configured:
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/p0_acceptance.py

cd ../frontend
CI=true pnpm run build
```

`hyperliquid_acceptance.py` deterministically verifies a small testnet long,
both reduce-only protection orders, full close, a small short, both protection
orders, and full close. It refuses to touch a symbol that already has a
position.

`p0_acceptance.py` separately verifies DeepSeek, Hyperliquid testnet,
the live-trading lock, the active Chinese strategy, and five complete AI
decision cycles. Keeping these checks separate avoids depending on the AI to
randomly choose both trade directions during acceptance.

## Final Acceptance Order

1. Confirm `.env` values are configured without printing them.
2. Run tests and the targeted Ruff command.
3. Run `scripts/hyperliquid_acceptance.py`.
4. Start the backend API and confirm `/api/v1/health` is healthy.
5. Run `scripts/p0_acceptance.py`.
6. Build and inspect the frontend.
7. Stop all local services.
