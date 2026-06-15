"""
Position and Balance Management Service
Provides higher-level position and balance management functions
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

from trading.interface import Position
from trading.factory import get_trader
from trading.symbols import same_symbol

logger = logging.getLogger("AlphaTransformer")


class PositionService:
    """持仓和余额管理服务"""
    
    def __init__(self):
        self.trader = get_trader()
    
    async def get_account_summary(self) -> Dict:
        """获取账户概览"""
        try:
            balance = await self.trader.get_balance()
            positions = await self.trader.get_positions()
            
            # 计算持仓统计
            total_positions = len(positions)
            long_positions = len([p for p in positions if p.side == "LONG"])
            short_positions = len([p for p in positions if p.side == "SHORT"])
            
            # 计算总保证金占用
            total_margin_used = sum(p.margin for p in positions)
            
            # 计算风险指标
            margin_ratio = total_margin_used / balance.total_balance if balance.total_balance > 0 else 0
            
            return {
                "balance": {
                    "total_balance": balance.total_balance,
                    "available_balance": balance.available_balance,
                    "margin_balance": balance.margin_balance,
                    "unrealized_pnl": balance.unrealized_pnl,
                    "currency": balance.currency
                },
                "positions": {
                    "total_count": total_positions,
                    "long_count": long_positions,
                    "short_count": short_positions,
                    "total_margin_used": total_margin_used,
                    "margin_ratio": margin_ratio
                },
                "risk_metrics": {
                    "margin_usage_percent": margin_ratio * 100,
                    "available_margin_percent": (1 - margin_ratio) * 100 if margin_ratio < 1 else 0
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取账户概览失败: {e}")
            raise
    
    async def get_position_by_symbol(self, symbol: str) -> Optional[Position]:
        """获取指定标的的持仓"""
        try:
            positions = await self.trader.get_positions()
            
            for position in positions:
                if same_symbol(position.symbol, symbol):
                    return position
            
            return None
            
        except Exception as e:
            logger.error(f"获取 {symbol} 持仓失败: {e}")
            raise
    
    async def get_positions_by_side(self, side: str) -> List[Position]:
        """获取指定方向的所有持仓"""
        try:
            positions = await self.trader.get_positions()
            return [p for p in positions if p.side.upper() == side.upper()]
            
        except Exception as e:
            logger.error(f"获取 {side} 持仓失败: {e}")
            raise
    
    async def calculate_portfolio_pnl(self) -> Dict:
        """计算投资组合盈亏统计"""
        try:
            positions = await self.trader.get_positions()
            
            if not positions:
                return {
                    "total_unrealized_pnl": 0.0,
                    "total_realized_pnl": 0.0,  # TODO: 需要从历史交易计算
                    "profitable_positions": 0,
                    "losing_positions": 0,
                    "breakeven_positions": 0,
                    "win_rate": 0.0,
                    "largest_winner": 0.0,
                    "largest_loser": 0.0
                }
            
            # 分析持仓盈亏
            profitable_positions = len([p for p in positions if p.unrealized_pnl > 0])
            losing_positions = len([p for p in positions if p.unrealized_pnl < 0])
            breakeven_positions = len([p for p in positions if p.unrealized_pnl == 0])
            
            total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
            win_rate = profitable_positions / len(positions) if positions else 0
            
            pnl_values = [p.unrealized_pnl for p in positions]
            largest_winner = max(pnl_values) if pnl_values else 0.0
            largest_loser = min(pnl_values) if pnl_values else 0.0
            
            return {
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_realized_pnl": 0.0,  # TODO: 需要从历史交易计算
                "profitable_positions": profitable_positions,
                "losing_positions": losing_positions,
                "breakeven_positions": breakeven_positions,
                "win_rate": win_rate,
                "largest_winner": largest_winner,
                "largest_loser": largest_loser,
                "position_details": [
                    {
                        "symbol": p.symbol,
                        "side": p.side,
                        "size": p.size,
                        "unrealized_pnl": p.unrealized_pnl,
                        "percentage_pnl": p.percentage_pnl
                    }
                    for p in positions
                ]
            }
            
        except Exception as e:
            logger.error(f"计算投资组合盈亏失败: {e}")
            raise
    
    async def check_margin_health(self) -> Dict:
        """检查保证金健康状况"""
        try:
            balance = await self.trader.get_balance()
            positions = await self.trader.get_positions()
            
            total_margin_used = sum(p.margin for p in positions)
            margin_ratio = total_margin_used / balance.total_balance if balance.total_balance > 0 else 0
            
            # 风险等级评估
            if margin_ratio < 0.3:
                risk_level = "LOW"
                risk_message = "保证金使用率正常"
            elif margin_ratio < 0.6:
                risk_level = "MEDIUM"
                risk_message = "保证金使用率偏高，建议关注"
            elif margin_ratio < 0.8:
                risk_level = "HIGH"
                risk_message = "保证金使用率过高，存在强平风险"
            else:
                risk_level = "CRITICAL"
                risk_message = "保证金不足，立即处理"
            
            return {
                "total_balance": balance.total_balance,
                "total_margin_used": total_margin_used,
                "available_balance": balance.available_balance,
                "margin_ratio": margin_ratio,
                "margin_usage_percent": margin_ratio * 100,
                "risk_level": risk_level,
                "risk_message": risk_message,
                "unrealized_pnl": balance.unrealized_pnl,
                "liquidation_risk": margin_ratio > 0.8,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"检查保证金健康状况失败: {e}")
            raise


# 全局服务实例
_position_service_instance: Optional[PositionService] = None


def get_position_service() -> PositionService:
    """获取全局持仓服务实例"""
    global _position_service_instance
    if _position_service_instance is None:
        _position_service_instance = PositionService()
    return _position_service_instance
