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
    reference_price: float | None = None,
    max_entry_price_drift_pct: float | None = None,
    max_chase_price_drift_pct: float | None = None,
) -> float:
    """Reject an opening decision before it reaches the exchange."""
    if not testnet and not allow_live_trading:
        raise ValueError("实盘开仓已禁用；必须显式启用 allow_live_trading")

    if reference_price is not None:
        if reference_price <= 0:
            raise ValueError("参考价格必须大于 0")
        drift_pct = abs(current_price - reference_price) / reference_price
        if (
            max_entry_price_drift_pct is not None
            and drift_pct > max_entry_price_drift_pct
        ):
            raise ValueError("执行价格相对评分参考价偏离过大")
        if max_chase_price_drift_pct is not None:
            if (
                action == "OPEN_LONG"
                and current_price
                > reference_price * (1 + max_chase_price_drift_pct)
            ):
                raise ValueError("OPEN_LONG 执行价高于参考价，触发追价保护")
            if (
                action == "OPEN_SHORT"
                and current_price
                < reference_price * (1 - max_chase_price_drift_pct)
            ):
                raise ValueError("OPEN_SHORT 执行价低于参考价，触发追价保护")

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
