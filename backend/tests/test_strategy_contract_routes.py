from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import router


def _build_client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _valid_prompt():
    return """---
architecture_mode: regime_deterministic
architecture_version: regime_deterministic_v1
prompt_role: REGIME_CLASSIFIER_ONLY
prompt_version: regime_classifier_prompt_v1
output_schema_version: regime_output_v1
---
You classify market regime only."""


def test_validate_trading_strategy_accepts_regime_prompt_contract():
    client = _build_client()

    response = client.post(
        "/api/v1/trading/strategy/validate",
        json={"strategy": _valid_prompt()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["unknown_fields"] == []
    assert payload["referenced_fields"] == []


def test_validate_trading_strategy_rejects_missing_frontmatter():
    client = _build_client()

    response = client.post(
        "/api/v1/trading/strategy/validate",
        json={"strategy": "You classify market regime only."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["unknown_fields"] == ["missing prompt frontmatter"]


def test_update_trading_strategy_rejects_invalid_prompt_contract():
    client = _build_client()

    response = client.post(
        "/api/v1/trading/strategy",
        json={"strategy": "You classify market regime only."},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["message"] == "regime classifier prompt 不符合运行时合约"
    assert detail["unknown_fields"] == ["missing prompt frontmatter"]


def test_market_context_endpoint_returns_structured_agent_view(monkeypatch):
    client = _build_client()

    monkeypatch.setattr(
        "api.routes.tech_analysis_tool",
        lambda symbol: {
            "symbol": symbol,
            "timeframes": {"4h": {"atr": 123.4, "natr": 1.2}},
            "derivatives": {"funding_rate": 0.0001},
            "overall_signals": {"trend_direction": "上涨"},
            "analysis_timestamp": "2026-06-16T13:30:00",
        },
    )
    monkeypatch.setattr(
        "api.routes.market_data_client.get_status",
        lambda: SimpleNamespace(connected=True),
    )

    response = client.get("/api/v1/market/context/BTC")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BTC"
    assert payload["market_data_connected"] is True
    assert payload["context"]["timeframes"]["4h"]["atr"] == 123.4
    assert payload["context"]["derivatives"]["funding_rate"] == 0.0001
