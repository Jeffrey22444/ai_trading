"""Strategy field contract and validation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


FIELD_REFERENCE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.*-]+)\s*\}\}")

TIMEFRAME_FIELDS = {
    "current_price",
    "price_change",
    "price_change_percent",
    "data_points",
    "latest_timestamp",
    "ema20",
    "ema50",
    "macd_line",
    "signal_line",
    "macd_histogram",
    "rsi7",
    "rsi14",
    "atr",
    "natr",
    "nearest_support",
    "nearest_resistance",
}

DERIVATIVES_FIELDS = {
    "open_interest",
    "funding_rate",
    "funding_interval",
    "funding_timestamp",
    "mark_price",
    "index_price",
    "premium",
}

OVERALL_SIGNAL_FIELDS = {
    "trend_direction",
    "trend_consistency",
    "avg_rsi7",
    "rsi7_signal",
    "avg_rsi14",
    "rsi14_signal",
    "macd_consensus",
}


@dataclass
class StrategyValidationResult:
    valid: bool
    referenced_fields: list[str]
    unknown_fields: list[str]


def get_strategy_field_catalog(timeframes: list[str]) -> dict[str, Any]:
    timeframe_paths = {
        timeframe: sorted(f"timeframes.{timeframe}.{field}" for field in TIMEFRAME_FIELDS)
        for timeframe in timeframes
    }
    return {
        "timeframes": timeframe_paths,
        "derivatives": sorted(f"derivatives.{field}" for field in DERIVATIVES_FIELDS),
        "overall_signals": sorted(
            f"overall_signals.{field}" for field in OVERALL_SIGNAL_FIELDS
        ),
        "placeholder_syntax": "{{timeframes.4h.atr}}",
        "notes": [
            "策略中若要引用后端字段，必须使用双大括号占位符。",
            "自然语言解释可以自由写，但命名字段引用必须来自这个目录。",
        ],
    }


def extract_field_references(strategy: str) -> list[str]:
    return FIELD_REFERENCE_PATTERN.findall(strategy or "")


def validate_strategy_field_references(
    strategy: str, timeframes: list[str]
) -> StrategyValidationResult:
    references = extract_field_references(strategy)
    unknown = sorted(
        {
            reference
            for reference in references
            if not _is_allowed_reference(reference, timeframes)
        }
    )
    return StrategyValidationResult(
        valid=not unknown,
        referenced_fields=sorted(set(references)),
        unknown_fields=unknown,
    )


def _is_allowed_reference(reference: str, timeframes: list[str]) -> bool:
    parts = reference.split(".")
    if len(parts) == 3:
        scope, middle, field_name = parts
        if scope == "timeframes":
            return middle in timeframes and field_name in TIMEFRAME_FIELDS
        return False

    if len(parts) == 2:
        scope, field_name = parts
        if scope == "derivatives":
            return field_name in DERIVATIVES_FIELDS
        if scope == "overall_signals":
            return field_name in OVERALL_SIGNAL_FIELDS

    return False
