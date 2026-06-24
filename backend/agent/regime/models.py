"""Schemas for the deterministic regime execution pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Regime(StrEnum):
    TREND = "TREND"
    RANGE = "RANGE"
    BREAKOUT = "BREAKOUT"
    UNKNOWN = "UNKNOWN"


class Setup(StrEnum):
    PULLBACK = "PULLBACK"
    CONTINUATION = "CONTINUATION"
    MEAN_REVERSION = "MEAN_REVERSION"
    MOMENTUM = "MOMENTUM"
    NONE = "NONE"


class Lifecycle(StrEnum):
    SCALP = "SCALP"
    SHORT = "SHORT"
    SWING = "SWING"


class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


class Gate(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"


class Decision(StrEnum):
    APPROVE = "APPROVE"
    BLOCK = "BLOCK"


class PositionStatus(StrEnum):
    INIT = "INIT"
    ACTIVE = "ACTIVE"
    PROFITING = "PROFITING"
    MATURITY = "MATURITY"
    EXIT = "EXIT"
    CLOSED = "CLOSED"


class FailureMode(StrEnum):
    NONE = "NONE"
    PARTIAL_FILL = "PARTIAL_FILL"
    RECONCILE = "RECONCILE"
    SAFE_MODE = "SAFE_MODE"
    PROTECTION_FAILED = "PROTECTION_FAILED"


class ExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MarketBar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class MarketData:
    symbol: str
    price: float
    volume: float
    volatility: float
    timestamp: int
    bars: list[MarketBar]

    def validate(self) -> None:
        if self.timestamp <= 0:
            raise ValueError("MarketData timestamp must be positive")
        if self.price <= 0:
            raise ValueError("MarketData price must be positive")


@dataclass(frozen=True)
class RegimeOutput:
    regime: Regime
    confidence: float
    expires_at: int


@dataclass(frozen=True)
class AllowedStrategy:
    setup: Setup
    lifecycle: Lifecycle


@dataclass(frozen=True)
class EntryScore:
    f1_trend_strength: float
    f2_momentum: float
    f3_volatility_context: float
    f4_entry_timing: float
    q: float


@dataclass(frozen=True)
class DirectionScore:
    d_long: float
    d_short: float
    edge: float
    side: Side


@dataclass(frozen=True)
class SetupSelection:
    regime: Regime
    side: Side
    setup: Setup
    block_reason: str | None = None


@dataclass(frozen=True)
class EntryCandidate:
    symbol: str
    regime: Regime
    setup: Setup | None
    lifecycle: Lifecycle | None
    score: EntryScore
    direction: DirectionScore
    budget_available: bool
    risk_gate: Gate
    decision: Decision


@dataclass(frozen=True)
class RiskBudget:
    equity: float
    max_risk_pct: float
    regime: Regime
    regime_weight: float
    regime_budget: float
    active_risk: float
    remaining_risk: float

    @property
    def budget_available(self) -> bool:
        return self.remaining_risk > 0


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: Side
    lifecycle: Lifecycle
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float


@dataclass(frozen=True)
class OpenRisk:
    regime: Regime
    side: Side
    entry_price: float
    stop_loss: float
    size: float
    quote_currency: str = "USDC"


@dataclass(frozen=True)
class Position:
    id: str
    symbol: str
    side: Side
    lifecycle: Lifecycle
    state: PositionStatus
    failure_mode: FailureMode
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    opened_at: int
    updated_at: int
    unrealized_pnl: float
    unrealized_r: float


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    filled_size: float = 0.0
    retry_count: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class ProtectionResult:
    position_state: PositionStatus
    failure_mode: FailureMode
    emergency_exit: bool
    symbol_entries_blocked: bool


@dataclass(frozen=True)
class ReconcileResult:
    position: Position | None
    entries_blocked: bool
    capital_released: bool


@dataclass(frozen=True)
class LoopDecision:
    steps: list[str]
    allow_entry: bool
    allow_exit: bool


@dataclass(frozen=True)
class IndicatorSet:
    close: float
    ema_fast: float | None
    ema_slow: float | None
    ema_fast_previous: float | None
    ema_mean: float | None
    atr: float | None
    atr_history: list[float] = field(default_factory=list)
    highs: list[float] = field(default_factory=list)
    lows: list[float] = field(default_factory=list)
    closes: list[float] = field(default_factory=list)
    macd_histogram: float | None = None
    previous_macd_histogram: float | None = None
