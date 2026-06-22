# AI Provider Configuration Examples

This guide shows how to configure different AI service providers by modifying the `agent.yaml` configuration file.

## Configuration Parameters

Only 3 parameters needed:
- `model_name`: The model name (e.g., gpt-4o, deepseek-chat)
- `base_url`: API base URL (null for OpenAI, custom for others)  
- `api_key`: API key environment variable

## OpenAI (Default)

```yaml
agent:
  model_name: "gpt-4o"
  base_url: null  # Use default OpenAI API
  api_key: "${OPENAI_API_KEY}"
```

## DeepSeek

```yaml
agent:
  model_name: "deepseek-chat"
  base_url: "https://api.deepseek.com/v1"
  api_key: "${DEEPSEEK_API_KEY}"
```

## Structured Output Compatibility

### Native Structured Output (OpenAI gpt-4o only)
- Uses OpenAI's native `response_format` feature
- Automatic schema validation
- Best performance and accuracy

### JSON Mode Fallback (All other providers)
- Uses JSON formatting in prompts
- Manual parsing with error handling
- Compatible with DeepSeek, Qwen, Claude, etc.

### Provider Support Matrix

| Provider | Models | Structured Output | JSON Mode | Status |
|----------|--------|------------------|-----------|---------|
| OpenAI | gpt-4o series | ✅ Native | ✅ | Full Support |
| OpenAI | gpt-4, gpt-3.5 | ❌ | ✅ | JSON Mode |
| DeepSeek | deepseek-chat | ❌ | ✅ | JSON Mode |
| Qwen | qwen-plus, qwen-max | ❌ | ✅ | JSON Mode |
| Local | varies | ❌ | ⚠️ | Model Dependent |

## Error Handling

The system automatically:
1. Detects if native structured output is supported
2. Falls back to JSON mode for other providers
3. Handles JSON parsing errors gracefully
4. Returns safe HOLD decisions if parsing fails

## Example: Switching to DeepSeek

1. **Update config/agent.yaml:**
```yaml
agent:
  model_name: "deepseek-chat"
  base_url: "https://api.deepseek.com/v1"
  api_key: "${DEEPSEEK_API_KEY}"
```

2. **Set environment variable:**
```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

3. **Restart the system** - JSON mode will be used automatically

The system will work identically, just using JSON parsing instead of native structured output.