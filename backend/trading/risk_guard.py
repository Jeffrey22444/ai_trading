"""Hard execution-time checks for AI-generated opening decisions."""

from decimal import Decimal, ROUND_DOWN


CENT = Decimal("0.01")


def normalize_position_size_usd(
    *,
    position_size_usd: float,
    available_balance: float,
    max_position_size_percent: float,
) -> float:
    """Clamp a cent-rounding limit overage down; reject any material overage."""
    requested = Decimal(str(position_size_usd))
    max_exact = Decimal(str(available_balance)) * Decimal(
        str(max_position_size_percent)
    )
    if requested > max_exact and requested - max_exact > CENT:
        raise ValueError(
            f"开仓金额超过可用余额的 {max_position_size_percent:.0%} 限制"
        )

    normalized = min(requested, max_exact).quantize(CENT, rounding=ROUND_DOWN)
    if normalized <= 0:
        raise ValueError("开仓金额必须大于 0")
    return float(normalized)


def validate_open_decision(
    *,
    action: str,
    position_size_usd: float,
    current_price: float,
    stop_loss_price: float | None,
    take_profit_price: float | None,
    available_balance: float,
    max_position_size_percent: float,
    testnet: bool,
    allow_live_trading: bool,
) -> float:
    """Reject an opening decision before it reaches the exchange."""
    if not testnet and not allow_live_trading:
        raise ValueError("实盘开仓已禁用；必须显式启用 allow_live_trading")

    normalized_position_size = normalize_position_size_usd(
        position_size_usd=position_size_usd,
        available_balance=available_balance,
        max_position_size_percent=max_position_size_percent,
    )

    if stop_loss_price is None or take_profit_price is None:
        raise ValueError("开仓必须同时设置止损价和止盈价")

    if action == "OPEN_LONG" and not (
        stop_loss_price < current_price < take_profit_price
    ):
        raise ValueError("多头止损止盈方向无效")

    if action == "OPEN_SHORT" and not (
        take_profit_price < current_price < stop_loss_price
    ):
        raise ValueError("空头止损止盈方向无效")

    return normalized_position_size
