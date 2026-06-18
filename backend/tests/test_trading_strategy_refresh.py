from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import router
from services import prompt_service


def test_refresh_trading_strategy_clears_cache_and_returns_source(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    prompt_service._strategy_cache = "stale strategy"
    prompt_service._cache_valid = True

    reloaded = {"called": False}

    def fake_reload_config():
        reloaded["called"] = True

    async def fake_get_trading_strategy():
        return "fresh strategy"

    async def fake_resolve_source():
        return "database"

    monkeypatch.setattr("api.routes.reload_config", fake_reload_config)
    monkeypatch.setattr("api.routes.get_trading_strategy", fake_get_trading_strategy)
    monkeypatch.setattr("api.routes._resolve_trading_strategy_source", fake_resolve_source)

    response = client.post("/api/v1/trading/strategy/refresh")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["source"] == "database"
    assert reloaded["called"] is True
    assert prompt_service._strategy_cache is None
    assert prompt_service._cache_valid is False


def test_reset_trading_strategy_writes_template_to_runtime_database(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    async def fake_reset_to_template():
        return "# template strategy\n\n准备开仓且系统量化护栏 action_allowed=false。"

    monkeypatch.setattr(
        "api.routes.reset_trading_strategy_to_template",
        fake_reset_to_template,
    )

    response = client.delete("/api/v1/trading/strategy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["source"] == "database"
    assert payload["message"] == "交易策略已重置为模板"
    assert payload["validation"]["valid"] is True
