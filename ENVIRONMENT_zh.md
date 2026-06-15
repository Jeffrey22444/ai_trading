# 环境变量配置

> 📖 **English**: [Environment Configuration](./ENVIRONMENT.md)

本指南说明如何为 AlphaTransformer 正确配置 `.env` 文件。

## 快速设置

```bash
cd backend
cp .env.example .env
# 编辑 .env 文件添加你的 API keys
```

## 环境变量说明

### AI 提供商配置

**AI API Key 配置**
```bash
# 此 API Key 必须与 agent.yaml 中配置的 AI 提供商匹配
# 默认: DeepSeek (如需更换请同时修改 agent.yaml)
OPENAI_API_KEY=your-api-key-here
```

**获取 API Key:**
- **DeepSeek (默认)**: https://platform.deepseek.com/api-keys - 性价比最高
- **OpenAI**: https://platform.openai.com/api-keys - 如需切换到 GPT-4o
- **Anthropic**: https://console.anthropic.com/ - 如需切换到 Claude

**更换 AI Provider:**
如需更换其他模型，修改 `backend/config/agent.yaml`:
```yaml
agent:
  model_name: "deepseek-chat"  # 改为: gpt-4o, claude-3-5-sonnet 等
  base_url: "https://api.deepseek.com/v1"  # 对应修改 base_url  
  api_key: "${OPENAI_API_KEY}"  # 统一使用此环境变量
```

### 交易所配置

**Hyperliquid 测试网**
```bash
HYPERLIQUID_WALLET_ADDRESS=你的主账户地址
HYPERLIQUID_PRIVATE_KEY=已授权的API-Wallet私钥
```

**如何配置 Hyperliquid 凭证:**
1. 在 https://app.hyperliquid-testnet.xyz/ 连接主账户。
2. 为该账户创建并授权 API Wallet。
3. `HYPERLIQUID_WALLET_ADDRESS` 使用主账户地址。
4. `HYPERLIQUID_PRIVATE_KEY` 只使用 API Wallet 私钥。

**测试环境 (推荐):**
- 保持 `exchange.testnet: true` 和 `allow_live_trading: false`。
- 为主账户领取测试网 USDC。
- 启动定时决策前运行 `scripts/hyperliquid_acceptance.py`。

### 数据库配置

**SQLite (默认)**
```bash
# DATABASE_URL=sqlite:///./alphatransformer.db
```
- 无需设置
- 数据库文件自动创建
- 适用于开发和单用户部署

## 安全最佳实践

### API Key 安全
- **绝不将 .env 提交到 git** (已在 .gitignore 中)
- 生产环境使用环境变量
- 定期轮换 API keys
- 使用最小必需权限

### Hyperliquid 钱包安全
- 不要把主钱包私钥放入本项目。
- 使用专用 API Wallet，并在需要时轮换。
- 开发时使用测试网，并从小仓位开始。

## 完整 .env 文件示例

```bash
# AI 提供商 API Key (必须与 agent.yaml 中配置的提供商匹配)
# 默认配置使用 DeepSeek
OPENAI_API_KEY=your-api-key-here

# Hyperliquid 测试网
HYPERLIQUID_WALLET_ADDRESS=0x主账户地址
HYPERLIQUID_PRIVATE_KEY=0x已授权API-Wallet私钥

# 数据库 (可选覆盖)
# DATABASE_URL=sqlite:///./alphatransformer.db

# 日志 (可选)
# LOG_LEVEL=INFO
```

## 配置验证

测试你的配置:
```bash
cd backend
uv run python -c "
from config.agent_config import load_config
config = load_config()
print('✅ 配置加载成功')
print(f'模型: {config.agent.model_name}')
print(f'API Key 已配置: {bool(config.agent.api_key)}')
"
```

## 故障排除

**"Invalid API key" 错误:**
- 检查 .env 中是否有多余空格或引号
- 验证 API key 是否激活
- 确保使用正确的提供商端点

**"Permission denied" 错误:**
- 验证 API Wallet 已授权给配置的主账户
- 验证主账户拥有测试网 USDC
- 确认 `exchange.testnet` 已启用

**环境变量未加载:**
- 确保 .env 在 backend/ 目录中
- 检查文件权限
- 更改后重启应用程序

## AI 提供商对比

| 提供商 | 速度 | 成本 | 结构化输出 | 可靠性 |
|--------|------|------|-----------|---------|
| OpenAI gpt-4o | ⭐⭐⭐⭐ | ⭐⭐ | 原生 | ⭐⭐⭐⭐⭐ |
| DeepSeek | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | JSON 模式 | ⭐⭐⭐⭐ |
| Claude | ⭐⭐⭐ | ⭐⭐⭐ | JSON 模式 | ⭐⭐⭐⭐⭐ |

## 切换提供商

1. 更新 `backend/config/agent.yaml`
2. 在 `.env` 中设置对应的 API key
3. 重启交易代理

系统会自动检测提供商能力并相应调整解析方式。
