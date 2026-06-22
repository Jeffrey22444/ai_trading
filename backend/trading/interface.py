from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: str  # "LONG" or "SHORT"
    size: float  # 持仓数量
    entry_price: float  # 开仓价格
    mark_price: float  # 标记价格
    unrealized_pnl: float  # 未实现盈亏
    percentage_pnl: float  # 盈亏百分比
    leverage: float  # 杠杆倍数
    margin: float  # 占用保证金 (initial margin)
    timestamp: datetime


@dataclass
class Balance:
    """账户余额信息"""
    total_balance: float
    available_balance: float
    margin_balance: float
    unrealized_pnl: float
    currency: str
    timestamp: datetime
