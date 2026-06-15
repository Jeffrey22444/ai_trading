# AlphaTransformer Trading System - Data Model

## Overview
Minimalist data model design using Agent-Tools architecture. The system stores complete analysis results with multi-symbol independent decisions and multi-timeframe technical analysis using TA-Lib.

## Persistent Entities

### 1. TradingAnalysis
Records complete analysis results for all symbols, including multi-timeframe technical analysis and decisions.

```python
class TradingAnalysis:
    id: int
    timestamp: datetime
    symbol_decisions: dict  # JSON: {symbol: {action, reasoning, execution_result, execution_status}}
    overall_summary: str  # AI's overall market analysis
    duration_ms: Optional[float]  # Analysis processing time
    error: Optional[str]  # Analysis error if any
```

**Fields:**
- `id`: Primary key
- `timestamp`: When the analysis was completed
- `symbol_decisions`: JSON object containing decisions for each symbol
- `overall_summary`: AI agent's overall market analysis and strategy summary  
- `duration_ms`: Processing time in milliseconds (optional)
- `error`: Error message if analysis failed (optional)

**symbol_decisions structure:**
```json
{
  "BTCUSDT": {
    "action": "BUY",
    "reasoning": "MACD bullish crossover, RSI oversold",
    "execution_result": {"order_id": "12345", "status": "filled"},
    "execution_status": "completed"
  },
  "ETHUSDT": {
    "action": "HOLD", 
    "reasoning": "Neutral signals, waiting for clearer direction",
    "execution_result": null,
    "execution_status": "pending"
  }
}
```

### 2. AccountSnapshot
Periodic account state snapshots for performance tracking.

```python
class AccountSnapshot:
    id: int
    timestamp: datetime
    total_balance: float
    available_balance: float
    margin_balance: float
    unrealized_pnl: float
    positions_count: int
    metadata: dict
```

**Fields:**
- `id`: Primary key
- `timestamp`: When snapshot was taken
- `total_balance`: Total account balance
- `available_balance`: Available for trading
- `margin_balance`: Balance including margin
- `unrealized_pnl`: Current unrealized P&L
- `positions_count`: Number of open positions
- `metadata`: Additional account data (JSON)

## Agent State Model

### AgentState
LangGraph workflow state for multi-symbol analysis.

```python
class AgentState(TypedDict):
    symbol_decisions: Dict[str, SymbolDecision]  # Per-symbol decisions
    overall_summary: Optional[str]  # AI's overall analysis
    error: Optional[str]  # Error information
    analysis_metadata: Optional[Dict[str, Any]]  # Additional context

class SymbolDecision(TypedDict):
    action: str  # BUY/SELL/HOLD
    reasoning: str  # AI reasoning for this symbol
    execution_result: Optional[Dict[str, Any]]  # Trading execution result
    execution_status: str  # "pending", "completed", "failed"
```

**State Flow:**
1. `analysis_node`: Creates SymbolDecision for each symbol using OpenAI Structured Output
2. `trading_execution_node`: Executes trades and updates execution results
3. `save_analysis_node`: Persists complete state to TradingAnalysis table

## Non-Persistent Data

### Positions
Retrieved from exchange API on demand, not stored locally.

```python
class Position:
    symbol: str
    side: str  # LONG/SHORT
    size: float
    entry_price: float
    mark_price: float
    pnl: float
    percentage_pnl: float
    leverage: float
    margin: float
```

### Market Data
Cached in memory using deque, automatically managed.

```python
class Kline:
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    # ... additional fields
```

## Database Schema

### SQLite Tables

```sql
CREATE TABLE trading_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    symbol_decisions TEXT NOT NULL,  -- JSON object
    overall_summary TEXT,
    duration_ms REAL,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    total_balance REAL NOT NULL,
    available_balance REAL NOT NULL,
    margin_balance REAL NOT NULL,
    unrealized_pnl REAL DEFAULT 0.0,
    positions_count INTEGER DEFAULT 0,
    metadata TEXT,  -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trading_analyses_timestamp ON trading_analyses(timestamp);
CREATE INDEX idx_account_snapshots_timestamp ON account_snapshots(timestamp);
```

## Data Flow

### Analysis Recording
1. Agent analyzes market data using multi-timeframe technical analysis
2. OpenAI Structured Output generates decisions for all symbols
3. Complete analysis saved to `trading_analyses` table
4. Individual symbol trade execution results updated in symbol_decisions JSON

### Account Monitoring
1. Account snapshots taken periodically (15 minutes default)
2. Historical performance can be calculated from snapshots
3. Real-time P&L calculated from current positions

### Data Retention
- **Trading Analyses**: Keep forever (for analysis and audit)
- **Account Snapshots**: Keep for 90 days (configurable via agent_config.yaml)

## Query Patterns

### Performance Analysis
```sql
-- Win rate by symbol (from JSON decisions)
SELECT 
    json_extract(symbol_decisions, '$.BTCUSDT.action') as btc_action,
    COUNT(*) as total_analyses
FROM trading_analyses 
WHERE json_extract(symbol_decisions, '$.BTCUSDT.action') != 'HOLD'
  AND timestamp >= datetime('now', '-7 days');

-- Daily analysis frequency
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as analysis_count,
    AVG(duration_ms) as avg_duration_ms
FROM trading_analyses 
GROUP BY DATE(timestamp)
ORDER BY date;

-- Recent analysis summaries
SELECT timestamp, overall_summary, 
       json_extract(symbol_decisions, '$') as all_decisions
FROM trading_analyses 
ORDER BY timestamp DESC 
LIMIT 20;
```

### Symbol Analysis
```sql
-- Symbol-specific decision patterns
SELECT 
    timestamp,
    json_extract(symbol_decisions, '$.BTCUSDT.action') as btc_action,
    json_extract(symbol_decisions, '$.BTCUSDT.reasoning') as btc_reasoning,
    json_extract(symbol_decisions, '$.ETHUSDT.action') as eth_action
FROM trading_analyses 
WHERE json_extract(symbol_decisions, '$.BTCUSDT.action') IS NOT NULL
ORDER BY timestamp DESC 
LIMIT 50;

-- Execution status tracking
SELECT 
    json_extract(symbol_decisions, '$.BTCUSDT.execution_status') as btc_exec_status,
    COUNT(*) as count
FROM trading_analyses 
GROUP BY json_extract(symbol_decisions, '$.BTCUSDT.execution_status');
```

## Integration Points

### Agent Workflow Integration
- `analysis_node`: Uses OpenAI Structured Output, creates multi-symbol decisions
- `trading_execution_node`: Updates execution results in symbol_decisions
- `save_analysis_node`: Persists complete TradingAnalysis record

### Technical Analysis Tools
- Multi-timeframe analysis using TA-Lib (5m, 1h, 4h configurable)
- Indicators: MACD, RSI, Bollinger Bands, EMA, SMA, ADX, Stochastic
- Cross-timeframe signal generation for AI decision making

### Configuration System
- `agent_config.yaml`: Symbols, timeframes, model settings
- Environment variable substitution (${OPENAI_API_KEY}, ${HYPERLIQUID_WALLET_ADDRESS})
- Startup validation with immediate exit on configuration errors
