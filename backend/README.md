# AlphaTransformer

Hyperliquid cryptocurrency market-data monitoring service based on Python FastAPI and CCXT REST polling.

## Quick Start

### Using uv (Recommended)

```bash
# 1. Start service
./run.sh

# Or manually run
uv run alpha-transformer-api
```

### Traditional Method

```bash
pip install -r requirements.txt
python -m api.main
```

## Configuration

Edit `config/symbols.yaml` file to configure monitored symbols.

## API Documentation

Visit http://localhost:8000/docs after starting the service.

## Development

```bash
# Install development dependencies
uv sync --group dev

# Run tests
uv run pytest

# Code checking
uv run ruff check .

# Code formatting
uv run black .
```
