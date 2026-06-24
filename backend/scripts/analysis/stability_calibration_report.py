"""Print stability calibration metrics from local SQLite analysis data."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from statistics import mean, median


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(Path(__file__).parents[2] / "data" / "trading.db"))
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(build_report(args.db, args.limit), indent=2, ensure_ascii=False))


def build_report(db_path: str, limit: int) -> dict:
    rows = _rows(db_path, limit)
    observations = []
    for row in rows:
        payload = json.loads(row[0] or "{}")
        shadow = (payload.get("_metadata") or {}).get("stability_shadow") or {}
        for symbol, data in shadow.items():
            observations.append({"symbol": symbol, **data})
    plans = _plans(db_path)
    holding = [plan["cycles_held"] for plan in plans if plan["cycles_held"] is not None]
    return {
        "raw_regime_change_rate": _change_rate(observations, "raw_ai_regime"),
        "active_regime_change_rate": _change_rate(observations, "active_regime"),
        "raw_direction_change_rate": _change_rate(observations, "raw_direction"),
        "stable_direction_change_rate": _change_rate(observations, "stable_direction"),
        "same_symbol_reverse_within_2_cycles": _reverse_count(observations),
        "exit_class_distribution": _distribution(item.get("exit_class") for item in observations),
        "challenge_score_distribution": _distribution(_bucket(item.get("challenge_score")) for item in observations),
        "average_holding_cycles": mean(holding) if holding else None,
        "median_holding_cycles": median(holding) if holding else None,
        "15min_close_rate": None,
        "expectancy": None,
        "max_drawdown": None,
        "notes": "15min_close_rate/expectancy/max_drawdown require reliable closed-trade/equity samples.",
    }


def _rows(db_path: str, limit: int) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        try:
            return conn.execute(
                "select symbol_decisions from trading_analyses order by id desc limit ?",
                (limit,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []


def _plans(db_path: str) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute("select * from position_plans")]
        except sqlite3.OperationalError:
            return []


def _change_rate(items: list[dict], key: str) -> float | None:
    by_symbol: dict[str, list] = {}
    for item in items:
        by_symbol.setdefault(item["symbol"], []).append(item.get(key))
    pairs = 0
    changes = 0
    for values in by_symbol.values():
        for previous, current in zip(values, values[1:]):
            pairs += 1
            changes += int(previous != current)
    return changes / pairs if pairs else None


def _reverse_count(items: list[dict]) -> int:
    count = 0
    by_symbol: dict[str, list] = {}
    for item in items:
        by_symbol.setdefault(item["symbol"], []).append(item.get("stable_direction"))
    for values in by_symbol.values():
        for index, value in enumerate(values[2:], start=2):
            count += int(value in {"LONG", "SHORT"} and value != values[index - 1] and value == values[index - 2])
    return count


def _distribution(values) -> dict:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _bucket(value) -> str:
    if value is None:
        return "None"
    return str(int(float(value)))


if __name__ == "__main__":
    main()
