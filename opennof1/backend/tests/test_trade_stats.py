from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from api.routes import router
from trading.history_service import TradingHistoryService, _unique_by_id


def _trade(
    order_id: str,
    realized_pnl: float | None,
    fee_cost: float = 0.0,
    *,
    closed_pnl: float | None = None,
):
    info = {}
    if realized_pnl is not None:
        info["realizedPnl"] = realized_pnl
    if closed_pnl is not None:
        info["closedPnl"] = closed_pnl

    return SimpleNamespace(
        order_id=order_id,
        fee_cost=fee_cost,
        raw_data={"info": info},
    )


def test_calculate_trade_metrics_from_trade_records_use_realized_pnl_after_fees():
    trade_records = [
        _trade("order-1", 10.0, 1.0),  # +9
        _trade("order-2", -5.0, 0.5),  # -5.5
        _trade("order-3", 2.0, 3.0),  # -1 after fee
        _trade("order-4", 0.0, 0.1),  # ignored (not a closing fill)
    ]

    metrics = TradingHistoryService._calculate_trade_metrics_from_trade_records(
        trade_records
    )

    assert metrics["winRate"] == pytest.approx(100 / 3)
    assert metrics["profitLossRatio"] == pytest.approx(9 / 3.25)
    assert metrics["expectancy"] == pytest.approx((1 / 3) * 9 - (2 / 3) * 3.25)


def test_calculate_trade_metrics_falls_back_to_closed_pnl_for_hyperliquid():
    trade_records = [
        _trade("order-1", None, 1.0, closed_pnl=10.0),  # +9
        _trade("order-2", None, 0.5, closed_pnl=-5.0),  # -5.5
        _trade("order-3", None, 3.0, closed_pnl=2.0),  # -1 after fee
        _trade("order-4", None, 0.1, closed_pnl=0.0),  # ignored
    ]

    metrics = TradingHistoryService._calculate_trade_metrics_from_trade_records(
        trade_records
    )

    assert metrics["winRate"] == pytest.approx(100 / 3)
    assert metrics["profitLossRatio"] == pytest.approx(9 / 3.25)
    assert metrics["expectancy"] == pytest.approx((1 / 3) * 9 - (2 / 3) * 3.25)


def test_trade_stats_route_syncs_recent_trades_before_calculating(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    calls = {"sync": False, "stats": False}

    class FakeHistoryService:
        async def sync_recent_trades(self, hours=24):
            calls["sync"] = hours == 24
            return 3

        async def get_trade_statistics(self, days=30):
            calls["stats"] = days == 30
            return {
                "totalTrades": 3,
                "totalVolume": 1000.0,
                "totalPnl": 25.0,
                "totalPnlPercent": 2.5,
                "winRate": 66.6666666667,
                "profitLossRatio": 1.8,
                "expectancy": 4.2,
                "avgTradeSize": 333.3333,
                "activePositions": 1,
            }

    monkeypatch.setattr(
        "trading.history_service.get_history_service", lambda: FakeHistoryService()
    )

    response = client.get("/api/v1/trading/stats")

    assert response.status_code == 200
    assert calls["sync"] is True
    assert calls["stats"] is True
    assert response.json()["winRate"] == 66.6666666667
    assert response.json()["profitLossRatio"] == 1.8
    assert response.json()["expectancy"] == 4.2


def test_unique_by_id_deduplicates_hyperliquid_trade_payloads():
    trades = [
        {"id": "trade-1", "amount": 1},
        {"id": "trade-1", "amount": 2},
        {"id": "trade-2", "amount": 3},
    ]

    assert _unique_by_id(trades) == [
        {"id": "trade-1", "amount": 1},
        {"id": "trade-2", "amount": 3},
    ]


@pytest.mark.asyncio
async def test_save_trade_record_ignores_duplicate_trade_id_integrity_error():
    service = object.__new__(TradingHistoryService)

    class DuplicateSession:
        def __init__(self):
            self.added = []
            self.rolled_back = False

        async def execute(self, stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

        def add(self, record):
            self.added.append(record)
            raise IntegrityError("insert", {}, Exception("duplicate trade_id"))

        async def rollback(self):
            self.rolled_back = True

    session = DuplicateSession()

    await service._save_trade_record(
        session,
        {
            "id": "duplicate-trade",
            "order": "order-1",
            "symbol": "BTC/USDC:USDC",
            "side": "sell",
            "amount": 0.1,
            "price": 100.0,
            "cost": 10.0,
            "fee": {"cost": 0.01, "currency": "USDC"},
            "timestamp": 1_781_784_238_916,
        },
    )

    assert session.rolled_back is True
