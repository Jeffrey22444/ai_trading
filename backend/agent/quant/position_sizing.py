"""Kelly-based deterministic position sizing."""

from __future__ import annotations

from agent.quant.models import PositionSizingResult, ScoreResult


def calculate_position_size(
    score: ScoreResult,
    available_balance: float,
    kelly_config,
    leverage_config,
    scoring_config,
) -> PositionSizingResult:
    if score.direction_bias == "NEUTRAL":
        return _hold("方向不清晰，强制 HOLD")
    if score.total_score < scoring_config.entry_score_threshold:
        return _hold("评分低于入场阈值，强制 HOLD")

    winrate = _score_to_winrate(score.total_score, scoring_config.score_to_winrate)
    if winrate is None:
        return _hold("评分无法映射胜率，强制 HOLD")

    leverage = min(
        _score_to_leverage(score.total_score, leverage_config.score_to_leverage),
        leverage_config.max_leverage,
    )
    kelly_fraction = leverage_config.fraction_by_leverage.get(
        leverage, kelly_config.fraction
    )
    payoff_ratio = kelly_config.payoff_ratio_b
    raw_kelly = (payoff_ratio * winrate - (1 - winrate)) / payoff_ratio
    if raw_kelly <= 0:
        return PositionSizingResult(
            position_size_usd=0.0,
            leverage=leverage,
            margin_used_usd=0.0,
            winrate=winrate,
            kelly_fraction=round(raw_kelly, 6),
            fractional_kelly=0.0,
            capped_fraction=0.0,
            can_open=False,
            hold_reason="凯利最优比例 <= 0，强制 HOLD",
        )

    fractional = raw_kelly * kelly_fraction
    capped = min(fractional, kelly_config.hard_cap)
    position_size = available_balance * capped
    if position_size < kelly_config.min_position_usd:
        return PositionSizingResult(
            position_size_usd=round(position_size, 2),
            leverage=leverage,
            margin_used_usd=round(position_size / leverage, 2) if leverage else 0.0,
            winrate=winrate,
            kelly_fraction=round(raw_kelly, 6),
            fractional_kelly=round(fractional, 6),
            capped_fraction=round(capped, 6),
            can_open=False,
            hold_reason=f"仓位低于 {kelly_config.min_position_usd:.0f} 美元下限，强制 HOLD",
        )

    return PositionSizingResult(
        position_size_usd=round(position_size, 2),
        leverage=leverage,
        margin_used_usd=round(position_size / leverage, 2),
        winrate=winrate,
        kelly_fraction=round(raw_kelly, 6),
        fractional_kelly=round(fractional, 6),
        capped_fraction=round(capped, 6),
        can_open=True,
        hold_reason=None,
    )


def _hold(reason: str) -> PositionSizingResult:
    return PositionSizingResult(
        position_size_usd=0.0,
        leverage=1,
        margin_used_usd=0.0,
        winrate=None,
        kelly_fraction=0.0,
        fractional_kelly=0.0,
        capped_fraction=0.0,
        can_open=False,
        hold_reason=reason,
    )


def _score_to_winrate(total_score: float, mapping: dict[str, float]) -> float | None:
    return _lookup_score_bucket(total_score, mapping)


def _score_to_leverage(total_score: float, mapping: dict[str, int]) -> int:
    return int(_lookup_score_bucket(total_score, mapping) or 1)


def _lookup_score_bucket(total_score: float, mapping: dict):
    for bucket, value in mapping.items():
        low, high = [float(part) for part in bucket.split("-", maxsplit=1)]
        if total_score >= low and total_score < high:
            return value
    if total_score >= 10 and "9-10" in mapping:
        return mapping["9-10"]
    return None

