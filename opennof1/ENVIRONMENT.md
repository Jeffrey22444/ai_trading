# Environment Configuration

> 📖 **中文文档**: [环境变量配置](./ENVIRONMENT_zh.md)

This guide explains how to properly configure the `.env` file for AlphaTransformer.

## Quick Setup

```bash
cd backend
cp .env.example .env
# Edit .env with your API keys
```

## Environment Variables

### AI Provider Configuration

**AI API Key Configuration**
```bash
# This key must match the AI provider configured in agent.yaml
# Default: DeepSeek (change agent.yaml to use other providers)
OPENAI_API_KEY=your-api-key-here
```

**Get API Keys:**
- **DeepSeek (Default)**: https://platform.deepseek.com/api-keys - Most cost-effective
- **OpenAI**: https://platform.openai.com/api-keys - For switching to GPT-4o
- **Anthropic**: https://console.anthropic.com/ - For switching to Claude

**Switch AI Provider:**
To use other models, modify `backend/config/agent.yaml`:
```yaml
agent:
  model_name: "deepseek-chat"  # Change to: gpt-4o, claude-3-5-sonnet, etc.
  base_url: "https://api.deepseek.com/v1"  # Update base_url accordingly
  api_key: "${OPENAI_API_KEY}"  # Use unified environment variable
```

### Trading Exchange Configuration

**Hyperliquid Testnet**
```bash
HYPERLIQUID_WALLET_ADDRESS=your-main-account-address
HYPERLIQUID_PRIVATE_KEY=your-authorized-api-wallet-private-key
```

**How to configure Hyperliquid credentials:**
1. Connect the main account at https://app.hyperliquid-testnet.xyz/
2. Create and authorize an API Wallet for that account.
3. Use the main account address as `HYPERLIQUID_WALLET_ADDRESS`.
4. Use only the API Wallet private key as `HYPERLIQUID_PRIVATE_KEY`.

**For Testing (Recommended):**
- Keep `exchange.testnet: true` and `allow_live_trading: false`.
- Fund the main account with testnet faucet USDC.
- Run `scripts/hyperliquid_acceptance.py` before enabling scheduled decisions.

### Database Configuration

**SQLite (Default)**
```bash
# DATABASE_URL=sqlite:///./alphatransformer.db
```
- No setup required
- Database file created automatically
- Perfect for development and single-user deployment

## Security Best Practices

### API Key Security
- **Never commit .env to git** (already in .gitignore)
- Use environment variables in production
- Rotate API keys regularly
- Use minimal required permissions

### Hyperliquid Wallet Security
- Never put the main wallet private key in this project.
- Authorize a dedicated API Wallet and rotate it when needed.
- Use testnet during development and keep position sizes small.

## Example Complete .env File

```bash
# AI Provider API Key (must match the provider configured in agent.yaml)
# Default configuration uses DeepSeek
OPENAI_API_KEY=your-api-key-here

# Hyperliquid testnet
HYPERLIQUID_WALLET_ADDRESS=0x-main-account-address
HYPERLIQUID_PRIVATE_KEY=0x-authorized-api-wallet-private-key

# Database (optional override)
# DATABASE_URL=sqlite:///./alphatransformer.db

# Logging (optional)
# LOG_LEVEL=INFO
```

## Validation

Test your configuration:
```bash
cd backend
uv run python -c "
from config.agent_config import load_config
config = load_config()
print('✅ Configuration loaded successfully')
print(f'Model: {config.agent.model_name}')
print(f'API Key configured: {bool(config.agent.api_key)}')
"
```

## Troubleshooting

**"Invalid API key" errors:**
- Check for extra spaces or quotes in .env
- Verify the API key is active
- Ensure correct provider endpoints

**"Permission denied" errors:**
- Verify the API Wallet is authorized for the configured account
- Verify the main account has testnet USDC
- Confirm `exchange.testnet` is enabled

**Environment variables not loading:**
- Ensure .env is in backend/ directory
- Check file permissions
- Restart the application after changes
