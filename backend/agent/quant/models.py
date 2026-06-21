"""Shared models for deterministic strategy guardrails."""

from dataclasses import dataclass, field
from datetime import datetime
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
    timestamp: datetime | None = None
    open_timestamp: datetime | None = None
    close_timestamp: datetime | None = None


@dataclass(frozen=True)
class SymbolMarketContext:
    symbol: str
    timeframes: dict[str, IndicatorFrame]
    derivatives: dict[str, Any]
    previous_derivatives: dict[str, Any]

    @property
    def current_price(self) -> float | None:
        reference = self.get_reference_frame()
        if reference:
            return reference[1].current_price
        return None

    def get_reference_frame(self) -> tuple[str, IndicatorFrame] | None:
        for timeframe in ("3m", "1h", "4h"):
            frame = self.timeframes.get(timeframe)
            if frame:
                return timeframe, frame
        return None

    @property
    def reference_price(self) -> float | None:
        reference = self.get_reference_frame()
        return reference[1].current_price if reference else None

    @property
    def reference_timeframe(self) -> str | None:
        reference = self.get_reference_frame()
        return reference[0] if reference else None

    @property
    def reference_timestamp(self) -> datetime | None:
        reference = self.get_reference_frame()
        return reference[1].timestamp if reference else None


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
class EntryQualityResult:
    can_enter: bool
    hold_reason: str | None
    checks: dict[str, Any]


@dataclass(frozen=True)
class QuantGuardrail:
    symbol: str
    score: ScoreResult
    stops: StopResult
    sizing: PositionSizingResult
    entry_quality: EntryQualityResult
    reference_price: float | None
    reference_timeframe: str | None
    reference_timestamp: datetime | None
    action_allowed: bool
    allowed_action: str
    hold_reason: str | None

    def to_prompt_dict(self) -> dict[str, Any]:
        reference_timestamp = (
            self.reference_timestamp.isoformat() if self.reference_timestamp else None
        )
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
            "reference_price": self.reference_price,
            "reference_timeframe": self.reference_timeframe,
            "reference_timestamp": reference_timestamp,
            "stops": {
                "long": self.stops.long.__dict__,
                "short": self.stops.short.__dict__,
                "atr_4h": self.stops.atr_4h,
                "current_price": self.stops.current_price,
            },
            "sizing": self.sizing.__dict__,
            "entry_quality": self.entry_quality.__dict__,
            "action_allowed": self.action_allowed,
            "allowed_action": self.allowed_action,
            "hold_reason": self.hold_reason,
        }
