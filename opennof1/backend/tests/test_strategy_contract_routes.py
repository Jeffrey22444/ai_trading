from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import router


def _build_client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_validate_trading_strategy_accepts_registered_fields():
    client = _build_client()

    response = client.post(
        "/api/v1/trading/strategy/validate",
        json={
            "strategy": (
                "4h 波动率参考 {{timeframes.4h.atr}}，"
                "资金费率参考 {{derivatives.funding_rate}}，"
                "趋势方向参考 {{overall_signals.trend_direction}}，"
                "量化评分参考 {{quant_guardrail.total_score}}。"
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["unknown_fields"] == []
    assert "timeframes.4h.atr" in payload["referenced_fields"]
    assert "quant_guardrail.total_score" in payload["referenced_fields"]


def test_validate_trading_strategy_rejects_unknown_quant_guardrail_fields():
    client = _build_client()

    response = client.post(
        "/api/v1/trading/strategy/validate",
        json={"strategy": "使用 {{quant_guardrail.imaginary_score}} 决策"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["unknown_fields"] == ["quant_guardrail.imaginary_score"]


def test_update_trading_strategy_rejects_unknown_fields():
    client = _build_client()

    response = client.post(
        "/api/v1/trading/strategy",
        json={"strategy": "使用 {{timeframes.4h.imaginary_signal}} 决策"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["message"] == "交易策略引用了未注册的后端字段"
    assert detail["unknown_fields"] == ["timeframes.4h.imaginary_signal"]


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
