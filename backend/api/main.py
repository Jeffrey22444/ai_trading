"""
FastAPI main application
"""

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
backend_dir = Path(__file__).parent.parent
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)

from api.routes import router  # noqa: E402
from database.database import init_database, close_database  # noqa: E402
from market.hyperliquid_market import market_data_client  # noqa: E402
from utils.logger import setup_logger  # noqa: E402
from config.settings import config  # noqa: E402


# Setup logging
logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    polling_task = None
    # Execute on startup
    logger.info("Starting AlphaTransformer AI Trading System...")

    # Initialize database
    try:
        await init_database()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

    # Initialize trading history service
    try:
        from trading.history_service import get_history_service

        history_service = get_history_service()
        await history_service.initialize_if_needed()
        logger.info("交易历史服务初始化完成")
    except Exception as e:
        logger.error(f"交易历史服务初始化失败: {e}")
        # 这个错误不应该阻止系统启动，记录警告即可

    # Check configuration
    missing_vars = config.validate_required_env_vars()
    if missing_vars:
        logger.warning(f"缺少环境变量: {missing_vars}")
        logger.info("系统将在测试模式下运行")
    else:
        logger.info("配置验证通过")

    # Initialize historical data (Phase 3 components)
    try:
        await market_data_client.initialize_historical_data()
        logger.info("历史数据初始化完成")
    except Exception as e:
        logger.error(f"历史数据初始化失败: {e}")

    # Start Hyperliquid market-data polling.
    try:
        connected = await market_data_client.connect()
        polling_task = asyncio.create_task(market_data_client.run_polling_loop())
        if connected:
            logger.info("Hyperliquid 行情轮询启动成功")
        else:
            logger.error("Hyperliquid 行情轮询首次连接失败，将在后台继续重试")
    except Exception as e:
        logger.error(f"Hyperliquid 行情轮询异常: {e}")

    logger.info("🚀 AlphaTransformer 系统启动完成")

    yield

    # Execute on shutdown
    logger.info("正在关闭系统...")
    await market_data_client.close()
    if polling_task:
        polling_task.cancel()
        with suppress(asyncio.CancelledError):
            await polling_task
    await close_database()
    logger.info("系统关闭完成")


# Create FastAPI application
app = FastAPI(
    title="AlphaTransformer AI Trading System",
    description="AI-powered cryptocurrency trading system",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 配置为允许的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    """Handle ValueError exceptions"""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "type": "ValueError",
            }
        },
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request, exc: RuntimeError):
    """Handle RuntimeError exceptions"""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "SYSTEM_ERROR",
                "message": str(exc),
                "type": "RuntimeError",
            }
        },
    )


# Register routes
app.include_router(router, prefix="/api/v1", tags=["system"])


# Root route
@app.get("/")
async def root():
    return {
        "message": "AlphaTransformer AI Trading System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "status": "running",
    }


if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=config.system.host,
        port=config.system.port,
        reload=True,
        reload_excludes=["data/*", "*.db", "*.db-*"],
        log_level=config.system.log_level.lower(),
    )
