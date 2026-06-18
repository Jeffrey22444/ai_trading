"""Shared models for deterministic strategy guardrails."""

from dataclasses import dataclass, field
from typing import Any


Direction = str


@dataclass(frozen=True)
class IndicatorFrame:
    current_price: float
    ema20: float | None
    ema50: float | None
    macd_histogram: float | None
    previous_macd_histogram: float | None
    rsi14: float | None
    atr: float | None
    natr: float | None
    highs: list[float] = field(default_factory=list)
    lows: list[float] = field(default_factory=list)
    closes: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class SymbolMarketContext:
    symbol: str
    timeframes: dict[str, IndicatorFrame]
    derivatives: dict[str, Any]
    previous_derivatives: dict[str, Any]

    @property
    def current_price(self) -> float | None:
        for timeframe in ("3m", "1h", "4h"):
            frame = self.timeframes.get(timeframe)
            if frame:
                return frame.current_price
        return None


@dataclass(frozen=True)
class DirectionScore:
    direction: Direction
    total_score: float
    breakdown: dict[str, float]
    notes: list[str]


@dataclass(frozen=True)
class ScoreResult:
    direction_bias: Direction
    total_score: float
    long_score: DirectionScore
    short_score: DirectionScore
    notes: list[str]


@dataclass(frozen=True)
class StopSide:
    stop_loss: float | None
    take_profit: float | None
    atr_stop: float | None
    swing_level: float | None
    stop_source: str
    risk_reward: float | None


@dataclass(frozen=True)
class StopResult:
    long: StopSide
    short: StopSide
    atr_4h: float | None
    current_price: float | None


@dataclass(frozen=True)
class PositionSizingResult:
    position_size_usd: float
    leverage: int
    margin_used_usd: float
    winrate: float | None
    kelly_fraction: float
    fractional_kelly: float
    capped_fraction: float
    can_open: bool
    hold_reason: str | None


@dataclass(frozen=True)
class QuantGuardrail:
    symbol: str
    score: ScoreResult
    stops: StopResult
    sizing: PositionSizingResult
    action_allowed: bool
    allowed_action: str
    hold_reason: str | None

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction_bias": self.score.direction_bias,
            "total_score": self.score.total_score,
            "long_score": {
                "total": self.score.long_score.total_score,
                "breakdown": self.score.long_score.breakdown,
                "notes": self.score.long_score.notes,
            },
            "short_score": {
                "total": self.score.short_score.total_score,
                "breakdown": self.score.short_score.breakdown,
                "notes": self.score.short_score.notes,
            },
            "stops": {
                "long": self.stops.long.__dict__,
                "short": self.stops.short.__dict__,
                "atr_4h": self.stops.atr_4h,
                "current_price": self.stops.current_price,
            },
            "sizing": self.sizing.__dict__,
            "action_allowed": self.action_allowed,
            "allowed_action": self.allowed_action,
            "hold_reason": self.hold_reason,
        }

