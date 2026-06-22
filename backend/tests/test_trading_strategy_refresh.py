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

    async def fake_get_status():
        return type(
            "Status",
            (),
            {
                "compatible": True,
                "source": "database",
                "message": None,
                "to_dict": lambda self: {"compatible": True, "source": "database"},
            },
        )()

    monkeypatch.setattr("api.routes.reload_config", fake_reload_config)
    monkeypatch.setattr("api.routes.get_regime_prompt_status", fake_get_status)

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
        return """---
architecture_mode: regime_deterministic
architecture_version: regime_deterministic_v1
prompt_role: REGIME_CLASSIFIER_ONLY
prompt_version: regime_classifier_prompt_v1
output_schema_version: regime_output_v1
---
You classify market regime only."""

    async def fake_get_status():
        return type(
            "Status",
            (),
            {"to_dict": lambda self: {"compatible": True, "source": "database"}},
        )()

    monkeypatch.setattr(
        "api.routes.reset_regime_prompt_to_template",
        fake_reset_to_template,
    )
    monkeypatch.setattr("api.routes.get_regime_prompt_status", fake_get_status)

    response = client.delete("/api/v1/trading/strategy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["source"] == "database"
    assert payload["message"] == "regime classifier prompt 已重置为模板"
    assert payload["validation"]["valid"] is True
