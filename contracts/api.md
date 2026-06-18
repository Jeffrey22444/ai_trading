# API Contracts

This document describes the current local runtime contract for the Hyperliquid-only backend.

## Symbol Rules

- Runtime symbols are logical symbols: `BTC`, `ETH`, `SOL`.
- API routes, cache keys, UI payloads, and decision records should use logical symbols.
- Hyperliquid CCXT symbols such as `BTC/USDC:USDC` are an internal exchange-boundary detail.
- Legacy `BTCUSDT` / `ETHUSDT` / `SOLUSDT` strings may still appear in compatibility tests, but they are not the preferred runtime contract.

## Core Endpoints

### Health

```http
GET /api/v1/health
```

```json
{
  "status": "healthy",
  "timestamp": "2026-06-17T10:00:00.000000",
  "uptime_seconds": 0,
  "market_data_connected": true,
  "total_symbols": 3,
  "active_timeframes": 3
}
```

### Configured Symbols And Timeframes

```http
GET /api/v1/symbols
```

```json
{
  "symbols": ["BTC", "ETH", "SOL"],
  "timeframes": ["3m", "1h", "4h"]
}
```

### K-Lines

```http
GET /api/v1/klines/BTC/3m?limit=5
```

```json
{
  "symbol": "BTC",
  "timeframe": "3m",
  "data": [
    {
      "open_time": 1718611020000,
      "close_time": 1718611199999,
      "open_price": 66500.0,
      "high_price": 66520.5,
      "low_price": 66480.0,
      "close_price": 66510.0,
      "volume": 12.34,
      "quote_volume": 820000.0,
      "trades_count": 0,
      "is_final": true,
      "timestamp": "2026-06-17T10:00:00.000000"
    }
  ]
}
```

### Snapshot

```http
GET /api/v1/snapshot/BTC
```

```json
{
  "symbol": "BTC",
  "snapshot": {
    "3m": {
      "open_time": 1718611020000,
      "close_price": 66510.0,
      "volume": 12.34,
      "is_final": true,
      "timestamp": "2026-06-17T10:00:00.000000"
    },
    "1h": null,
    "4h": null
  },
  "timestamp": "2026-06-17T10:00:05.000000"
}
```

### Market Context

```http
GET /api/v1/market/context/BTC
```

```json
{
  "symbol": "BTC",
  "market_data_connected": true,
  "generated_at": "2026-06-17T10:00:10.000000",
  "context": {
    "symbol": "BTC",
    "timeframes": {
      "3m": {
        "current_price": 66510.0,
        "ema20": 66490.2,
        "ema50": 66410.8,
        "rsi14": 58.4
      }
    },
    "derivatives": {},
    "overall_signals": {},
    "analysis_timestamp": "2026-06-17T10:00:10.000000"
  }
}
```

### Cache Info

```http
GET /api/v1/cache/info
```

### Connection Status

```http
GET /api/v1/connection/status
```

Response fields:
- `exchange`
- `connected`
- `last_message`
- `reconnect_count`
- `error_message`

## Agent Endpoints

### Agent Status

```http
GET /api/v1/agent/status
```

```json
{
  "is_running": false,
  "decision_interval": 180,
  "symbols": ["BTC", "ETH", "SOL"],
  "timeframes": ["3m", "1h", "4h"],
  "model_name": "deepseek-chat",
  "last_run": null,
  "next_run": null,
  "uptime_seconds": null
}
```

### Start Agent

```http
POST /api/v1/agent/start
```

### Stop Agent

```http
POST /api/v1/agent/stop
```

### Run One Analysis Immediately

```http
POST /api/v1/agent/analyze
```

The response includes the execution-facing decision fields and the strategy v2
quant guardrail used to constrain AI output:

```json
{
  "symbol_decisions": {
    "BTC": {
      "symbol": "BTC",
      "action": "OPEN_LONG",
      "reasoning": "AI reasoning plus system guardrail note",
      "execution_status": "completed",
      "execution_result": {},
      "position_size_usd": 120.0,
      "stop_loss_price": 65000.0,
      "take_profit_price": 69000.0,
      "leverage": 3,
      "quant_guardrail": {
        "direction_bias": "LONG",
        "total_score": 8.0,
        "action_allowed": true,
        "allowed_action": "OPEN_LONG",
        "sizing": {
          "position_size_usd": 120.0,
          "leverage": 3,
          "winrate": 0.56,
          "margin_used_usd": 40.0
        },
        "stops": {
          "long": {
            "stop_loss": 65000.0,
            "take_profit": 69000.0,
            "stop_source": "atr",
            "risk_reward": 2.0
          }
        }
      }
    }
  },
  "overall_summary": "Market summary",
  "error": null,
  "duration_ms": 1000.0
}
```

## Decisions

### Recent Decisions

```http
GET /api/v1/decisions?limit=20&offset=0&order=desc
```

Each decision record stores `symbol_decisions` keyed by logical symbol names such as `BTC`, `ETH`, and `SOL`.
For strategy v2, each symbol decision may include `position_size_usd`,
`stop_loss_price`, `take_profit_price`, `leverage`, and `quant_guardrail`.
The frontend uses these fields to display score, bias, size, stops, and
guardrail HOLD reasons.

### Decision Stats

```http
GET /api/v1/decisions/stats?days=7
```

## Trading Endpoints

These routes depend on configured Hyperliquid credentials and should not be used as the first local smoke test.

### Balance

```http
GET /api/v1/trading/balance
```

### Positions

```http
GET /api/v1/trading/positions
```

### Account Summary

```http
GET /api/v1/trading/account/summary
```

### Market Price

```http
GET /api/v1/trading/market/BTC/price
```

### Order History

```http
GET /api/v1/trading/orders/history?symbol=BTC&limit=50
```

### Trade Stats

```http
GET /api/v1/trading/stats?days=30
```

## Strategy Endpoints

```http
GET /api/v1/trading/strategy
GET /api/v1/trading/strategy/schema
POST /api/v1/trading/strategy/validate
POST /api/v1/trading/strategy
DELETE /api/v1/trading/strategy
POST /api/v1/trading/strategy/refresh
```

Runtime strategy text is stored in the database so the Settings page can edit it directly. `backend/config/trading_strategy.md` is the versioned template used to seed or reset the database strategy. `backend/config/agent.yaml` contains quant parameters, not the strategy body.

Endpoint behavior:
- `GET /trading/strategy`: returns the current runtime database strategy and source.
- `POST /trading/strategy`: validates and saves the runtime database strategy.
- `DELETE /trading/strategy`: resets the database strategy from `backend/config/trading_strategy.md`.
- `POST /trading/strategy/refresh`: clears the in-memory cache and reloads config values.

The strategy field catalog accepts explicit references to:
- `timeframes.*`
- `derivatives.*`
- `overall_signals.*`
- `quant_guardrail.*`

Examples:
- `{{timeframes.4h.atr}}`
- `{{derivatives.funding_rate}}`
- `{{quant_guardrail.total_score}}`
- `{{quant_guardrail.sizing.position_size_usd}}`
- `{{quant_guardrail.stops.long.stop_loss}}`

Strategy v2 tuning guidance lives in `STRATEGY_V2_CONFIG_GUIDE.md`.

## Local Validation Order

Use this order for local validation:

1. `GET /api/v1/health`
2. `GET /api/v1/symbols`
3. `GET /api/v1/cache/info`
4. `GET /api/v1/klines/BTC/3m?limit=5`
5. `GET /api/v1/market/context/BTC`
6. `GET /api/v1/agent/status`

Only after these pass should you move on to credential-dependent `trading/*` endpoints.
