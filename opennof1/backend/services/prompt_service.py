"""
提示词管理服务 - 数据库为运行时策略源，文件模板用于初始化和重置
"""
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy import select
from database.database import get_session_maker
from database.models import SystemConfig
from config.settings import config
from services.strategy_contract import (
    StrategyValidationResult,
    get_strategy_field_catalog,
    validate_strategy_field_references,
)

logger = logging.getLogger("AlphaTransformer")

TRADING_STRATEGY_KEY = "trading_strategy"
DEFAULT_TEMPLATE_PATH = "backend/config/trading_strategy.md"

# 缓存配置
_strategy_cache: Optional[str] = None
_cache_valid = False


def get_trading_strategy_template_path() -> Path:
    """Return the repository-local strategy template path."""
    configured_path = (
        getattr(config.agent, "trading_strategy_template_path", None)
        or DEFAULT_TEMPLATE_PATH
    )
    path = Path(configured_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


def get_trading_strategy_template() -> str:
    """Load the versioned default strategy template."""
    path = get_trading_strategy_template_path()
    if not path.exists():
        raise FileNotFoundError(f"交易策略模板不存在: {path}")
    strategy = path.read_text(encoding="utf-8").strip()
    if not strategy:
        raise ValueError(f"交易策略模板为空: {path}")
    return strategy


async def _get_strategy_row(session):
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == TRADING_STRATEGY_KEY)
    )
    return result.scalar_one_or_none()


async def seed_trading_strategy_from_template() -> str:
    """Ensure the database has the runtime strategy, seeded from the template."""
    strategy = get_trading_strategy_template()
    async with get_session_maker()() as session:
        config_row = await _get_strategy_row(session)
        if config_row and config_row.value.strip():
            return config_row.value.strip()

        if config_row:
            config_row.value = strategy
            config_row.description = "Runtime trading strategy seeded from template"
        else:
            session.add(
                SystemConfig(
                    key=TRADING_STRATEGY_KEY,
                    value=strategy,
                    description="Runtime trading strategy seeded from template",
                )
            )
        await session.commit()
    return strategy


async def reset_trading_strategy_to_template() -> str:
    """Replace the runtime database strategy with the versioned template."""
    strategy = get_trading_strategy_template()
    async with get_session_maker()() as session:
        config_row = await _get_strategy_row(session)
        if config_row:
            config_row.value = strategy
            config_row.description = "Runtime trading strategy reset from template"
        else:
            session.add(
                SystemConfig(
                    key=TRADING_STRATEGY_KEY,
                    value=strategy,
                    description="Runtime trading strategy reset from template",
                )
            )
        await session.commit()

    clear_strategy_cache()
    return strategy

async def get_trading_strategy() -> str:
    """
    获取运行时交易策略。数据库是唯一生效来源，缺失时用模板初始化。
    """
    global _strategy_cache, _cache_valid
    
    # 先检查缓存
    if _cache_valid and _strategy_cache is not None:
        return _strategy_cache
    
    try:
        async with get_session_maker()() as session:
            config_row = await _get_strategy_row(session)
            
            if config_row and config_row.value.strip():
                logger.info("使用数据库中的运行时交易策略")
                _strategy_cache = config_row.value.strip()
                _cache_valid = True
                return _strategy_cache
    
    except Exception as e:
        logger.warning(f"读取数据库交易策略失败，将尝试模板初始化: {e}")
    
    logger.info("数据库交易策略缺失，使用模板初始化运行时策略")
    _strategy_cache = await seed_trading_strategy_from_template()
    _cache_valid = True
    return _strategy_cache

async def set_trading_strategy(strategy: str) -> bool:
    """
    设置用户自定义的交易策略（存储到数据库）
    """
    global _strategy_cache, _cache_valid
    
    try:
        if not strategy or not strategy.strip():
            raise ValueError("交易策略内容不能为空")
        
        strategy = strategy.strip()
        
        async with get_session_maker()() as session:
            # 查找现有配置
            result = await session.execute(
                select(SystemConfig).where(SystemConfig.key == TRADING_STRATEGY_KEY)
            )
            config_row = result.scalar_one_or_none()
            
            if config_row:
                # 更新现有配置
                config_row.value = strategy
                logger.info("更新数据库中的交易策略配置")
            else:
                # 创建新配置
                new_config = SystemConfig(
                    key="trading_strategy",
                    value=strategy,
                    description="用户自定义的运行时交易策略配置"
                )
                session.add(new_config)
                logger.info("创建新的交易策略配置")
            
            await session.commit()
            
            # 清除缓存，强制下次重新读取
            _strategy_cache = None
            _cache_valid = False
            
            return True
            
    except Exception as e:
        logger.error(f"设置交易策略失败: {e}")
        return False


def validate_trading_strategy(strategy: str) -> StrategyValidationResult:
    """Validate explicit backend-field references inside a strategy body."""
    return validate_strategy_field_references(strategy, list(config.agent.timeframes))


def get_trading_strategy_field_catalog() -> dict:
    """Return the field catalog the strategy is allowed to reference."""
    return get_strategy_field_catalog(list(config.agent.timeframes))

def clear_strategy_cache():
    """清除策略缓存（用于测试或强制刷新）"""
    global _strategy_cache, _cache_valid
    _strategy_cache = None
    _cache_valid = False
    logger.info("交易策略缓存已清除")
