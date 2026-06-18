"""
Configuration loading with environment variable support
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from pydantic import BaseModel, field_validator


def is_missing_secret(value: str) -> bool:
    """Treat unresolved variables and documented placeholders as missing."""
    normalized = (value or "").strip().lower()
    return (
        not normalized
        or normalized.startswith("${")
        or normalized.startswith("your_")
        or normalized.startswith("replace")
        or "placeholder" in normalized
    )


def substitute_env_vars(text: str) -> str:
    """替换字符串中的环境变量 ${VAR_NAME}"""
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replace_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))  # 如果找不到环境变量，保持原样

    return pattern.sub(replace_var, text)


def load_config_with_env_vars(config_path: Path) -> Dict[str, Any]:
    """加载配置文件并替换环境变量"""
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_content = f.read()

    # 替换环境变量
    processed_content = substitute_env_vars(config_content)

    # 解析YAML
    try:
        config = yaml.safe_load(processed_content)
        return config
    except yaml.YAMLError as e:
        raise ValueError(f"配置文件YAML格式错误: {e}")


class AgentConfig(BaseModel):
    model_name: str
    base_url: Optional[str] = None  # Custom base URL for different providers
    api_key: str
    decision_interval: int
    symbols: list[str]
    timeframes: list[str]
    trading_strategy: Optional[str] = None  # User-configurable trading strategy


class ExchangeConfig(BaseModel):
    name: str
    wallet_address: str = ""
    private_key: str = ""
    testnet: bool = True
    allow_live_trading: bool = False

    # Futures trading settings (for CCXT)
    default_leverage: int = 1
    margin_mode: str = "cross"  # cross or isolated
    enable_rate_limit: bool = True
    timeout: int = 10000  # milliseconds
    retries: int = 3
    @field_validator("name")
    @classmethod
    def require_hyperliquid(cls, value: str) -> str:
        if value.lower() != "hyperliquid":
            raise ValueError("当前版本仅支持 Hyperliquid")
        return "hyperliquid"

    def get_ccxt_config(self) -> Dict[str, Any]:
        """获取CCXT交易所配置（用于期货交易）"""
        return {
            "walletAddress": self.wallet_address,
            "privateKey": self.private_key,
            "enableRateLimit": self.enable_rate_limit,
            "timeout": self.timeout,
            "retries": self.retries,
            "options": {
                "defaultType": "swap",
            },
        }

    def missing_credential_env_vars(self) -> list[str]:
        """Return missing credential names for the selected exchange."""
        required = (
            ("HYPERLIQUID_WALLET_ADDRESS", self.wallet_address),
            ("HYPERLIQUID_PRIVATE_KEY", self.private_key),
        )
        return [name for name, value in required if is_missing_secret(value)]


class RiskConfig(BaseModel):
    max_position_size_percent: float
    max_daily_loss_percent: float
    stop_loss_percent: float


class KellyConfig(BaseModel):
    fraction: float = 0.35
    hard_cap: float = 0.20
    min_position_usd: float = 100.0
    payoff_ratio_b: float = 2.0


class LeverageConfig(BaseModel):
    max_leverage: int = 3
    score_to_leverage: Dict[str, int] = {
        "6-7": 1,
        "7-8": 2,
        "8-9": 3,
        "9-10": 3,
    }
    fraction_by_leverage: Dict[int, float] = {
        1: 0.35,
        2: 0.35,
        3: 0.30,
        4: 0.25,
        5: 0.25,
    }


class ScoringConfig(BaseModel):
    entry_score_threshold: float = 6.0
    min_direction_edge: float = 1.0
    trend_timeframes: list[str] = ["1h", "4h"]
    momentum_timeframe: str = "4h"
    fallback_momentum_timeframe: str = "1h"
    volatility_timeframe: str = "4h"
    score_weights: Dict[str, float] = {
        "D1": 1.0,
        "D2": 1.0,
        "D3": 1.0,
        "D4": 1.0,
        "D5": 1.0,
    }
    score_to_winrate: Dict[str, float] = {
        "6-7": 0.50,
        "7-8": 0.53,
        "8-9": 0.56,
        "9-10": 0.58,
    }
    benchmark_symbol: str = "BTC"
    core_symbols: list[str] = ["BTC", "ETH", "SOL"]
    high_volatility_natr: float = 5.0
    extreme_volatility_natr: float = 10.0
    extreme_funding_abs: float = 0.001


class StopConfig(BaseModel):
    timeframe: str = "4h"
    fallback_timeframe: str = "1h"
    atr_stop_multiplier: float = 1.5
    high_volatility_atr_stop_multiplier: float = 2.0
    swing_lookback: int = 20
    swing_strength_m: int = 2
    swing_buffer_atr_fraction: float = 0.10


class AccountSnapshotConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 15
    keep_days: int = 90


class LoggingConfig(BaseModel):
    level: str = "INFO"
    save_decisions: bool = True
    save_executions: bool = True
    save_snapshots: bool = True


class SystemConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    max_concurrent_decisions: int = 1


class AppConfig(BaseModel):
    agent: AgentConfig
    exchange: ExchangeConfig
    default_risk: RiskConfig
    kelly: KellyConfig = KellyConfig()
    leverage: LeverageConfig = LeverageConfig()
    scoring: ScoringConfig = ScoringConfig()
    stop: StopConfig = StopConfig()
    account_snapshot: AccountSnapshotConfig
    logging: LoggingConfig
    system: SystemConfig

    def validate_required_env_vars(self) -> list[str]:
        """检查必需的环境变量是否设置"""
        missing_vars = []

        if is_missing_secret(self.agent.api_key):
            missing_vars.append("OPENAI_API_KEY")

        missing_vars.extend(self.exchange.missing_credential_env_vars())

        return missing_vars

    def is_testnet_mode(self) -> bool:
        """检查是否为测试模式"""
        return (
            self.exchange.testnet
            or not self.agent.api_key
            or bool(self.exchange.missing_credential_env_vars())
        )


def load_app_config() -> AppConfig:
    """加载完整的应用配置"""
    config_path = Path(__file__).parent / "agent.yaml"

    # 加载并处理环境变量
    config_data = load_config_with_env_vars(config_path)

    # 创建配置对象
    return AppConfig(**config_data)


# 全局配置实例 - 延迟加载
config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取应用配置（延迟加载）"""
    global config
    if config is None:
        config = load_app_config()
    return config


def reload_config() -> AppConfig:
    """重新加载配置文件，并原地更新全局配置对象。"""
    global config
    new_config = load_app_config()

    if config is None:
        config = new_config
        return config

    for field_name in config.__class__.model_fields:
        setattr(config, field_name, getattr(new_config, field_name))

    return config


# 验证配置完整性
def validate_config():
    """验证配置的完整性，失败则退出程序"""
    cfg = get_config()
    errors = []

    # 检查必需配置项
    required_fields = [
        ("agent.model_name", cfg.agent.model_name),
        ("agent.api_key", cfg.agent.api_key),
        ("agent.decision_interval", cfg.agent.decision_interval),
        ("agent.symbols", cfg.agent.symbols),
        ("agent.timeframes", cfg.agent.timeframes),
        ("exchange.name", cfg.exchange.name),
    ]

    for field_name, field_value in required_fields:
        if not field_value:
            errors.append(f"缺少必需配置: {field_name}")

    # 检查数据类型和格式
    if not isinstance(cfg.agent.symbols, list) or len(cfg.agent.symbols) == 0:
        errors.append("agent.symbols 必须是非空列表")

    if not isinstance(cfg.agent.timeframes, list) or len(cfg.agent.timeframes) == 0:
        errors.append("agent.timeframes 必须是非空列表")

    # 检查时间框架格式
    valid_timeframes = [
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
    ]
    for tf in cfg.agent.timeframes:
        if tf not in valid_timeframes:
            errors.append(f"无效的时间框架: {tf}，支持的时间框架: {valid_timeframes}")

    # 检查API key格式
    if is_missing_secret(cfg.agent.api_key):
        errors.append("agent.api_key 环境变量未正确设置")

    for missing_var in cfg.exchange.missing_credential_env_vars():
        errors.append(f"{missing_var} 环境变量未正确设置")

    if errors:
        print("❌ 配置验证失败:")
        for error in errors:
            print(f"   - {error}")
        print("\n请检查 .env 文件和 config/agent.yaml 配置")
        print("系统将退出...")
        import sys

        sys.exit(1)

    print("✅ 配置验证通过")
