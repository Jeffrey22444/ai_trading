# Trading Analysis Tools

This folder is documentation-only right now. The runtime is Hyperliquid-only, so any examples here should use logical symbols such as `BTC`, `ETH`, and `SOL`.

## Symbol Convention

- Use `BTC`, `ETH`, `SOL` in analysis commands and local notes.
- Treat `BTCUSDT` / `ETHUSDT` as legacy compatibility inputs, not preferred examples.
- Exchange-formatted `BASE/USDC:USDC` symbols belong at the CCXT boundary only.

## Example

```bash
cd /Users/jeffrey/Documents/AI_trading/opennof1/backend

# Example pattern for a future analysis CLI
uv run python analysis/symbol_performance_analyzer.py --symbol BTC
```

If new analysis scripts are added later, keep their docs aligned with `../contracts/api.md` and the Hyperliquid-only symbol rules above.
