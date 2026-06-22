from dataclasses import dataclass
from datetime import datetime


EARLY = "EARLY"
IN_PROFIT = "IN_PROFIT"
PROFIT_PEAK = "PROFIT_PEAK"
PROFIT_DRAWDOWN = "PROFIT_DRAWDOWN"


@dataclass
class PositionState:
    entry_price: float
    current_price: float
    unrealized_pnl_pct: float
    peak_profit_pct: float
    drawdown_from_peak_pct: float
    holding_time_seconds: int
    regime: str
    stop_loss: float | None = None
    trailing_stop: float | None = None
    should_exit: bool = False


_position_cache: dict[str, tuple[datetime, float]] = {}


def update_position_state(position, now: datetime | None = None) -> PositionState:
    now = now or datetime.now()
    key = f"{position.symbol}:{position.side}:{position.entry_price}"
    first_seen, peak = _position_cache.get(key, (now, float("-inf")))
    profit_pct = _profit_pct(position)
    peak = max(peak, profit_pct)
    _position_cache[key] = (first_seen, peak)

    drawdown = max(0.0, peak - profit_pct)
    stop_loss = position.entry_price if profit_pct >= 0.5 else None
    trailing_stop = peak - 0.3 if peak > 1.0 else None
    should_exit = trailing_stop is not None and profit_pct < trailing_stop

    if should_exit or (peak >= 1.0 and drawdown >= 0.3):
        regime = PROFIT_DRAWDOWN
    elif profit_pct >= 1.0:
        regime = PROFIT_PEAK
    elif profit_pct >= 0.5:
        regime = IN_PROFIT
    else:
        regime = EARLY

    return PositionState(
        entry_price=position.entry_price,
        current_price=position.mark_price,
        unrealized_pnl_pct=profit_pct,
        peak_profit_pct=peak,
        drawdown_from_peak_pct=drawdown,
        holding_time_seconds=int((now - first_seen).total_seconds()),
        regime=regime,
        stop_loss=stop_loss,
        trailing_stop=trailing_stop,
        should_exit=should_exit,
    )


def _profit_pct(position) -> float:
    value = getattr(position, "percentage_pnl", None)
    if value is not None:
        return float(value)

    if not position.entry_price:
        return 0.0
    raw = (position.mark_price - position.entry_price) / position.entry_price * 100
    return raw if str(position.side).upper() == "LONG" else -raw


def reset_position_states() -> None:
    _position_cache.clear()
