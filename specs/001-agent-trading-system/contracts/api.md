# API Contracts - AlphaTransformer Trading System

## REST API Endpoints

### System Status
```
GET /api/status
Response: {
  "status": "running" | "stopped" | "error",
  "uptime": 3600,
  "last_decision": "2024-01-01T12:00:00Z",
  "connected_exchanges": ["hyperliquid"],
  "active_symbols": ["BTCUSDT", "ETHUSDT"]
}
```

### Agent Control
```
POST /api/agent/start
Request: {
  "symbols": ["BTCUSDT", "ETHUSDT"],  // optional, uses config default
  "decision_interval": 60  // optional, uses config default
}
Response: {
  "success": true,
  "session_id": "uuid-string",
  "started_at": "2024-01-01T12:00:00Z"
}

POST /api/agent/stop
Request: {
  "session_id": "uuid-string"  // optional, stops all sessions
}
Response: {
  "success": true,
  "stopped_at": "2024-01-01T12:00:00Z"
}
```

### Decision History
```
GET /api/decisions
Query Parameters:
- symbol: string (optional)
- action: string (BUY|SELL|HOLD)
- limit: integer (default 100, max 1000)
- offset: integer (default 0)
- start_date: string (ISO date)
- end_date: string (ISO date)

Response: {
  "total": 1500,
  "limit": 100,
  "offset": 0,
  "data": [
    {
      "id": 1,
      "timestamp": "2024-01-01T12:00:00Z",
      "action": "BUY",
      "symbol": "BTCUSDT",
      "reasoning": "Technical indicators suggest bullish momentum...",
      "confidence": 0.75,
      "quantity": 0.1,
      "price": 42000.0,
      "metadata": {}
    }
  ]
}
```

### Trade Executions
```
GET /api/trades
Query Parameters: same as /api/decisions

Response: {
  "total": 50,
  "data": [
    {
      "id": 1,
      "decision_id": 123,
      "timestamp": "2024-01-01T12:00:00Z",
      "action": "BUY",
      "symbol": "BTCUSDT",
      "quantity": 0.1,
      "price": 42000.0,
      "order_id": "hyperliquid_order_123",
      "status": "FILLED",
      "execution_price": 42000.5,
      "fees": 0.42,
      "metadata": {}
    }
  ]
}
```

### Account Information
```
GET /api/account
Response: {
  "total_balance": 10000.0,
  "available_balance": 8500.0,
  "margin_balance": 10000.0,
  "unrealized_pnl": 150.0,
  "positions_count": 3,
  "last_updated": "2024-01-01T12:00:00Z"
}

GET /api/positions
Response: {
  "positions": [
    {
      "symbol": "BTCUSDT",
      "side": "LONG",
      "size": 0.1,
      "entry_price": 41000.0,
      "mark_price": 42000.0,
      "pnl": 100.0,
      "percentage_pnl": 2.44,
      "leverage": 3.0,
      "margin": 1400.0
    }
  ]
}
```

### Account Snapshots
```
GET /api/snapshots
Query Parameters:
- start_date: string (ISO date)
- end_date: string (ISO date)
- limit: integer (default 100)

Response: {
  "total": 200,
  "data": [
    {
      "id": 1,
      "timestamp": "2024-01-01T12:00:00Z",
      "total_balance": 10000.0,
      "available_balance": 8500.0,
      "margin_balance": 10000.0,
      "unrealized_pnl": 150.0,
      "positions_count": 3,
      "metadata": {}
    }
  ]
}
```

### Performance Metrics
```
GET /api/performance
Query Parameters:
- period: string (1d|7d|30d|90d|all)
- symbol: string (optional)

Response: {
  "period": "7d",
  "start_balance": 9500.0,
  "end_balance": 10000.0,
  "total_return": 5.26,
  "daily_returns": [0.5, -0.2, 1.1, ...],
  "sharpe_ratio": 1.2,
  "max_drawdown": -2.5,
  "win_rate": 0.65,
  "total_trades": 20,
  "profitable_trades": 13,
  "losing_trades": 7,
  "avg_win": 50.0,
  "avg_loss": -25.0,
  "profit_factor": 2.0
}
```

## WebSocket Streams

### Decision Stream
```
WebSocket: /ws/decisions
Message Format: {
  "type": "decision",
  "data": {
    "id": 123,
    "timestamp": "2024-01-01T12:00:00Z",
    "action": "BUY",
    "symbol": "BTCUSDT",
    "reasoning": "Technical indicators suggest...",
    "confidence": 0.75,
    "quantity": 0.1,
    "price": 42000.0
  }
}
```

### Trade Execution Stream
```
WebSocket: /ws/trades
Message Format: {
  "type": "trade_execution",
  "data": {
    "id": 456,
    "decision_id": 123,
    "timestamp": "2024-01-01T12:00:05Z",
    "action": "BUY",
    "symbol": "BTCUSDT",
    "quantity": 0.1,
    "price": 42000.0,
    "status": "FILLED",
    "execution_price": 42000.5
  }
}
```

### Position Updates Stream
```
WebSocket: /ws/positions
Message Format: {
  "type": "position_update",
  "data": {
    "symbol": "BTCUSDT",
    "side": "LONG",
    "size": 0.1,
    "mark_price": 42000.0,
    "pnl": 100.0,
    "percentage_pnl": 2.44
  }
}
```

### Account Updates Stream
```
WebSocket: /ws/account
Message Format: {
  "type": "account_update",
  "data": {
    "total_balance": 10000.0,
    "available_balance": 8500.0,
    "unrealized_pnl": 150.0,
    "positions_count": 3,
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

## Error Response Format

All endpoints return consistent error format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid symbol provided",
    "details": {
      "field": "symbol",
      "value": "INVALID"
    }
  }
}
```

### Error Codes
- `VALIDATION_ERROR`: Invalid request parameters
- `NOT_FOUND`: Resource not found
- `UNAUTHORIZED`: Authentication required
- `RATE_LIMITED`: Too many requests
- `EXCHANGE_ERROR`: Exchange API error
- `AGENT_ERROR`: Agent execution error
- `SYSTEM_ERROR`: Internal system error

## HTTP Status Codes

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: System error
- `503 Service Unavailable`: System temporarily unavailable

## Rate Limiting

### REST API
- Public endpoints: 100 requests/minute
- Authenticated endpoints: 1000 requests/minute
- Agent control endpoints: 10 requests/minute

### WebSocket
- Connection limit: 5 concurrent connections per IP
- Message rate: No limit (server push)
- Connection timeout: 24 hours

## Authentication

### API Key Authentication (Future)
```
Authorization: Bearer <api_key>
```

### Session-based Authentication
- Session tokens issued on agent start
- Token valid for 24 hours
- Refresh token support

## Data Validation Rules

### Request Parameters
- `symbol`: Valid Hyperliquid perpetual symbol
- `action`: Must be one of BUY, SELL, HOLD
- `quantity`: Positive number, max 8 decimal places
- `price`: Positive number, max 8 decimal places
- `limit`: Integer 1-1000
- `dates`: ISO 8601 format

### Response Data
- Monetary values: 8 decimal places max
- Percentages: 4 decimal places max
- Timestamps: ISO 8601 UTC
- Booleans: JSON boolean type
- Null values: Omitted from JSON response
