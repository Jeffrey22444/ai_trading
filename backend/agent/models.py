"""
Simplified trading analysis service
"""
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.database import get_session_maker
from database.models import TradingAnalysis
from config.settings import config
from utils.logger import logger


class AnalysisService:
    """Service for recording complete trading analysis"""
    
    @staticmethod
    async def save_analysis(
        symbol_decisions: Dict[str, Dict[str, Any]],
        overall_summary: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> TradingAnalysis:
        """Save a complete trading analysis to database"""
        
        session_maker = get_session_maker()
        async with session_maker() as session:
            try:
                analysis = TradingAnalysis(
                    overall_summary=overall_summary,
                    symbol_decisions=symbol_decisions,
                    duration_ms=duration_ms,
                    model_name=config.agent.model_name,
                    error=error
                )
                
                session.add(analysis)
                await session.commit()
                await session.refresh(analysis)
                
                logger.info(f"分析已保存: {analysis.analysis_id}, 包含 {len(symbol_decisions)} 个标的决策")
                return analysis
                
            except Exception as e:
                await session.rollback()
                logger.error(f"保存分析失败: {e}")
                raise
    
    @staticmethod
    async def get_recent_analyses(
        limit: int = 100,
        offset: int = 0,
        order: str = "desc"
    ) -> list[TradingAnalysis]:
        """Get recent analyses"""
        
        session_maker = get_session_maker()
        async with session_maker() as session:
            from sqlalchemy import select, desc, asc

            order_normalized = (order or "desc").lower()
            order_clause = desc if order_normalized != "asc" else asc

            stmt = select(TradingAnalysis).order_by(
                order_clause(TradingAnalysis.id),
                order_clause(TradingAnalysis.timestamp)
            )
            stmt = stmt.offset(offset).limit(limit)
            
            
            result = await session.execute(stmt)
            return result.scalars().all()
    
    @staticmethod
    async def get_analysis_stats(days: int = 7) -> Dict[str, Any]:
        """Get analysis statistics"""
        
        session_maker = get_session_maker()
        async with session_maker() as session:
            from sqlalchemy import text
            
            # 总分析数
            total_result = await session.execute(
                text(f"""
                    SELECT COUNT(*) as total
                    FROM trading_analyses 
                    WHERE timestamp >= datetime('now', '-{days} days')
                """)
            )
            total_stats = total_result.fetchone()
            
            # 平均耗时
            duration_result = await session.execute(
                text(f"""
                    SELECT AVG(duration_ms) as avg_duration
                    FROM trading_analyses 
                    WHERE timestamp >= datetime('now', '-{days} days')
                    AND duration_ms IS NOT NULL
                """)
            )
            duration_stats = duration_result.fetchone()
            
            return {
                "period_days": days,
                "total_analyses": total_stats[0] if total_stats else 0,
                "avg_duration_ms": float(duration_stats[0]) if duration_stats and duration_stats[0] else 0.0
            }


# Global analysis service instance
analysis_service = AnalysisService()
