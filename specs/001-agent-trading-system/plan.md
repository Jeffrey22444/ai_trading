# AlphaTransformer Agent Trading System - Technical Plan

## Overview
AI-powered autonomous trading system similar to nof1.ai using Agent-Tools architecture with LangGraph orchestration.

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Database**: SQLite with SQLAlchemy ORM
- **AI Framework**: LangGraph + OpenAI API
- **Technical Analysis**: TA-Lib
- **Market Data**: Hyperliquid OHLCV through CCXT REST polling
- **Configuration**: YAML with environment variable substitution
- **Package Management**: uv

### Frontend (Future Phases)
- **Framework**: Next.js 16+ with React 19
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **State Management**: Zustand

## Project Structure

```
AlphaTransformer/
├── backend/
│   ├── agent/              # AI agent framework
│   │   ├── __init__.py
│   │   ├── state.py        # Agent state definitions
│   │   ├── workflow.py     # LangGraph workflow
│   │   ├── tools.py        # Trading tools
│   │   └── models.py       # Data models for decisions
│   ├── config/             # Configuration management
│   │   ├── agent.yaml      # Unified configuration
│   │   ├── agent_config.py # Configuration loader
│   │   └── settings.py     # Settings export
│   ├── market/             # Market data system
│   │   ├── types.py        # Data types
│   │   ├── data_cache.py   # K-line data caching
│   │   ├── hyperliquid_market.py   # Hyperliquid OHLCV client
│   │   └── websocket_client.py # WebSocket client
│   ├── trading/            # Trading execution
│   │   ├── __init__.py
│   │   ├── order_manager.py
│   │   └── position_tracker.py
│   ├── database/           # Database layer
│   │   ├── __init__.py
│   │   ├── models.py       # SQLAlchemy models
│   │   └── database.py     # Database connection
│   ├── api/                # REST API
│   │   ├── main.py         # FastAPI app
│   │   └── routes.py       # API routes
│   └── utils/              # Utilities
│       └── logger.py       # Logging setup
├── specs/                  # Feature specifications
├── frontend/               # Frontend application
└── docs/                   # Documentation
```

## Key Libraries & Dependencies

### Core Dependencies
- **fastapi**: Web framework and API server
- **uvicorn**: ASGI server for FastAPI
- **langchain**: AI/LLM integration framework
- **langgraph**: Agent workflow orchestration
- **openai**: LLM API client
- **sqlalchemy**: Database ORM
- **aiosqlite**: Async SQLite driver
- **talib**: Technical analysis library
- **websockets**: WebSocket client
- **httpx**: Async HTTP client
- **pydantic**: Data validation
- **pyyaml**: YAML configuration parsing

### Development Dependencies
- **pytest**: Testing framework
- **pytest-asyncio**: Async testing support
- **black**: Code formatting
- **ruff**: Linting and type checking

## Implementation Strategy

### Phase 1: Setup (Shared Infrastructure)
- Setup project structure and dependencies
- Configure SQLite database with basic models
- Implement configuration management system
- Setup logging and error handling

### Phase 2: Foundational (Blocking Prerequisites)
- Database schema and models implementation
- FastAPI application structure
- API routing and middleware setup
- Error handling and response formats

### Phase 3: User Story 2 - Real-time Market Data Processing
- Connect to Hyperliquid through CCXT and keep the K-line cache fresh
- Implement K-line data caching system
- Add data validation and quality checks
- Create unified market data access interface

### Phase 4: User Story 1 - AI Trading Agent Decision Making (MVP)
- Implement LangGraph workflow (analyze -> save -> execute)
- Create ReAct agent with trading tools
- Add TA-Lib technical analysis calculations
- Add decision recording and analysis
- OpenAI GPT-4 integration with confidence scoring

### Phase 5: User Story 3 - Order Execution and Position Management
- Build order management system
- Implement position tracking
- Add trade execution with safety checks
- Create account snapshot system

### Phase 6: User Story 4 - Real-time Monitoring Dashboard
- Build FastAPI endpoints for monitoring
- Add WebSocket streaming for real-time updates
- Implement agent control endpoints
- Add performance analytics

### Phase 7: Polish & Cross-Cutting Concerns
- Performance optimization
- Security hardening
- Documentation completion
- Testing and validation

## Data Models

### Core Entities
1. **Decision**: Every analysis decision (including HOLD)
2. **TradeExecution**: Actual trade execution records  
3. **AccountSnapshot**: Periodic account state snapshots

### Non-Persistent Data
- **Positions**: Retrieved from exchange API
- **Market Data**: Cached in memory, from exchange streams

## API Design

### REST Endpoints
- `GET /api/status` - System status
- `GET /api/decisions` - Decision history
- `GET /api/positions` - Current positions
- `GET /api/account` - Account information
- `POST /api/agent/start` - Start agent
- `POST /api/agent/stop` - Stop agent

### WebSocket Streams
- `/ws/decisions` - Real-time decision stream
- `/ws/positions` - Position updates
- `/ws/account` - Account snapshot updates

## Configuration Management

### Environment Variables
- `OPENAI_API_KEY`: OpenAI API key
- `HYPERLIQUID_WALLET_ADDRESS`: Hyperliquid main account address
- `HYPERLIQUID_PRIVATE_KEY`: Authorized API Wallet private key

### Configuration Files
- `config/agent.yaml`: Main configuration with all settings
- Supports environment variable substitution: `${VAR_NAME}`
- Testnet/production environment switching

## Testing Strategy

### Unit Tests
- Agent decision logic
- Technical analysis calculations
- Configuration loading
- Database models

### Integration Tests
- Market data processing
- Trading execution flow
- API endpoints
- WebSocket connections

### Testing Approach
- Focus on core functionality first
- Mock external APIs for reliable testing
- Test error handling and edge cases
- Performance testing for data processing
