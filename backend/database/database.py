"""
Database connection and session management
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool
from pathlib import Path
from config.settings import config
from utils.logger import logger

# Base class for all database models
class Base(DeclarativeBase):
    pass

# Database engine
engine = None
async_session_maker = None

def get_database_url() -> str:
    """Get database URL from config"""
    # 使用绝对路径避免权限问题
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / "data" / "trading.db"
    db_path.parent.mkdir(exist_ok=True)
    
    # 确保数据库文件可写
    if db_path.exists():
        db_path.chmod(0o664)
    
    logger.info(f"数据库路径: {db_path}")
    return f"sqlite+aiosqlite:///{db_path}"

async def init_database():
    """Initialize database connection"""
    global engine, async_session_maker
    
    try:
        database_url = get_database_url()
        logger.info(f"初始化数据库: {database_url}")
        
        # Create async engine
        engine = create_async_engine(
            database_url,
            echo=config.system.log_level == "DEBUG",
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,
                "timeout": 20
            }
        )
        
        # Create all tables
        from database.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session maker
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info("数据库连接初始化成功")
        logger.info("数据库表创建完成")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

def get_session_maker():
    """Get the session maker (must be called after init_database)"""
    if async_session_maker is None:
        raise RuntimeError("数据库未初始化，请先调用 init_database()")
    return async_session_maker


async def close_database():
    """Close database connection"""
    global engine
    if engine:
        await engine.dispose()
        logger.info("数据库连接已关闭")

# Dependency for FastAPI
async def get_db_session() -> AsyncSession:
    """FastAPI dependency for database session"""
    async with get_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()