import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from agent.stability import persistence
from agent.stability.persistence import (
    close_plan,
    reconcile_flat_position,
    reconcile_flat_symbol,
    upsert_open_plan,
)
from config.settings import config
from database.models import Base, PositionPlan


@pytest.fixture()
async def plan_db(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(persistence, "get_session_maker", lambda: session_maker)
    return session_maker


def _decision(action="OPEN_LONG", **overrides):
    values = {
        "symbol": "BTC",
        "action": action,
        "stop_loss_price": 95.0,
        "take_profit_price": 110.0,
        "stability_shadow": {"active_regime": "TREND"},
    }
    values.update(overrides)
    return values


def _result(action="OPEN_LONG", **overrides):
    values = {
        "status": "success",
        "action": action,
        "symbol": "BTC",
        "order_id": "open-1",
        "quantity": 0.2,
        "price": 100.0,
        "position_state": {
            "symbol": "BTC",
            "side": "LONG" if action.endswith("LONG") else "SHORT",
            "entry_price": 100.0,
            "size": 0.2,
            "opened_at": "2026-06-25T01:00:00",
        },
    }
    values.update(overrides)
    return values


async def _plans(session_maker):
    async with session_maker() as session:
        rows = await session.execute(select(PositionPlan).order_by(PositionPlan.id))
        return rows.scalars().all()


@pytest.mark.asyncio
async def test_open_order_creates_exactly_one_position_plan(plan_db):
    decision = _decision()
    result = _result()

    await upsert_open_plan("BTC", decision, result)
    await upsert_open_plan("BTC", decision, result)

    plans = await _plans(plan_db)
    assert len(plans) == 1
    assert plans[0].entry_order_id == "open-1"
    assert plans[0].side == "LONG"


@pytest.mark.asyncio
async def test_close_order_closes_matching_side_plan(plan_db):
    await upsert_open_plan("BTC", _decision("OPEN_LONG"), _result("OPEN_LONG", order_id="long-open"))
    await upsert_open_plan(
        "BTC",
        _decision("OPEN_SHORT"),
        _result(
            "OPEN_SHORT",
            order_id="short-open",
            price=101.0,
            position_state={"symbol": "BTC", "side": "SHORT", "entry_price": 101.0, "size": 0.3},
        ),
    )

    await close_plan(
        "BTC",
        {"action": "CLOSE_LONG", "exit_class": "TEST_EXIT"},
        {"status": "success", "action": "CLOSE_LONG", "order_id": "long-close", "quantity": 0.2},
    )

    plans = await _plans(plan_db)
    long_plan = next(plan for plan in plans if plan.side == "LONG")
    short_plan = next(plan for plan in plans if plan.side == "SHORT")
    assert long_plan.status == "CLOSED"
    assert long_plan.close_order_id == "long-close"
    assert short_plan.status == "OPEN"


@pytest.mark.asyncio
async def test_same_symbol_opposite_round_trips_do_not_cross_link(plan_db):
    await upsert_open_plan("BTC", _decision("OPEN_SHORT"), _result("OPEN_SHORT", order_id="short-open"))
    await close_plan(
        "BTC",
        {"action": "CLOSE_SHORT"},
        {"status": "success", "action": "CLOSE_SHORT", "order_id": "short-close", "quantity": 0.2},
    )
    await upsert_open_plan(
        "BTC",
        _decision("OPEN_LONG"),
        _result(
            "OPEN_LONG",
            order_id="long-open",
            price=102.0,
            position_state={"symbol": "BTC", "side": "LONG", "entry_price": 102.0, "size": 0.25},
        ),
    )

    plans = await _plans(plan_db)
    short_plan = next(plan for plan in plans if plan.side == "SHORT")
    long_plan = next(plan for plan in plans if plan.side == "LONG")
    assert short_plan.close_order_id == "short-close"
    assert long_plan.status == "OPEN"
    assert long_plan.close_order_id is None


@pytest.mark.asyncio
async def test_multiple_fills_for_one_order_map_to_one_plan(plan_db):
    first_fill = _result(order_id="multi-open", quantity=0.1)
    second_fill = _result(order_id="multi-open", quantity=0.2)

    await upsert_open_plan("BTC", _decision(), first_fill)
    await upsert_open_plan("BTC", _decision(), second_fill)

    plans = await _plans(plan_db)
    assert len(plans) == 1
    assert plans[0].entry_order_id == "multi-open"


@pytest.mark.asyncio
async def test_exchange_flat_reconciliation_closes_correct_stale_plan(plan_db):
    await upsert_open_plan("BTC", _decision("OPEN_LONG"), _result("OPEN_LONG", order_id="long-open"))
    await upsert_open_plan(
        "BTC",
        _decision("OPEN_SHORT"),
        _result(
            "OPEN_SHORT",
            order_id="short-open",
            price=101.0,
            position_state={"symbol": "BTC", "side": "SHORT", "entry_price": 101.0, "size": 0.3},
        ),
    )

    await reconcile_flat_position("BTC", "LONG", order_id="flat-close")

    plans = await _plans(plan_db)
    assert next(plan for plan in plans if plan.side == "LONG").status == "CLOSED"
    assert next(plan for plan in plans if plan.side == "SHORT").status == "OPEN"


@pytest.mark.asyncio
async def test_exchange_flat_symbol_reconciliation_clears_stale_open_plan(plan_db):
    await upsert_open_plan("ETH", _decision("OPEN_LONG", symbol="ETH"), _result("OPEN_LONG", symbol="ETH", order_id="eth-open"))

    await reconcile_flat_symbol("ETH")

    plans = await _plans(plan_db)
    assert plans[0].status == "CLOSED"
    assert plans[0].last_exit_class == "EXCHANGE_FLAT"


def test_default_config_mode_remains_shadow():
    assert config.stability_refactor.mode == "shadow"
