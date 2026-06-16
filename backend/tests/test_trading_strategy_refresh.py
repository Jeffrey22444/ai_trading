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
        return "config"

    monkeypatch.setattr("api.routes.reload_config", fake_reload_config)
    monkeypatch.setattr("api.routes.get_trading_strategy", fake_get_trading_strategy)
    monkeypatch.setattr("api.routes._resolve_trading_strategy_source", fake_resolve_source)

    response = client.post("/api/v1/trading/strategy/refresh")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["source"] == "config"
    assert reloaded["called"] is True
    assert prompt_service._strategy_cache is None
    assert prompt_service._cache_valid is False
