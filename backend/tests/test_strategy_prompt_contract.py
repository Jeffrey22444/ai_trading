from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.nodes.analysis_node import parse_regime_response
from agent.regime.models import Regime
from services import prompt_service


def test_strategy_contract_loads_regime_deterministic_manifest():
    contract = prompt_service.load_strategy_contract()

    assert contract["architecture"]["mode"] == "regime_deterministic"
    assert contract["prompt"]["role"] == "REGIME_CLASSIFIER_ONLY"
    assert Path("../").joinpath(contract["prompt"]["template_path"])


def test_regime_prompt_frontmatter_matches_manifest_and_avoids_legacy_terms():
    prompt = prompt_service.get_regime_prompt_template()
    validation = prompt_service.validate_regime_prompt_contract(prompt)

    assert validation.valid is True
    assert validation.frontmatter["prompt_role"] == "REGIME_CLASSIFIER_ONLY"
    for term in prompt_service.LEGACY_PROMPT_TERMS:
        assert term not in prompt.split("---", 2)[-1]


def test_regime_prompt_validation_rejects_missing_frontmatter():
    validation = prompt_service.validate_regime_prompt_contract("You classify regime.")

    assert validation.valid is False
    assert validation.reason == "missing prompt frontmatter"


def test_regime_output_with_trade_fields_falls_back_to_unknown():
    result = parse_regime_response(
        """
        {
          "symbol_regimes": [
            {
              "symbol": "BTC",
              "regime": "TREND",
              "confidence": 0.9,
              "evidence": ["ema_alignment"],
              "expires_at": "2099-01-01T00:00:00Z",
              "action": "OPEN_LONG"
            }
          ],
          "market_summary": "bad payload"
        }
        """,
        required_symbols=["BTC"],
    )

    assert result.symbol_regimes[0].regime == Regime.UNKNOWN


@pytest.mark.asyncio
async def test_legacy_db_prompt_without_regime_prompt_is_mismatch(monkeypatch):
    async def fake_get_row(_session, key):
        if key == prompt_service.LEGACY_TRADING_STRATEGY_KEY:
            return SimpleNamespace(value="old trading prompt")
        return None

    monkeypatch.setattr(prompt_service, "_get_config_row", fake_get_row)
    monkeypatch.setattr(prompt_service, "get_session_maker", lambda: _session_factory)

    status = await prompt_service.get_regime_prompt_status()

    assert status.compatible is False
    assert status.error_code == prompt_service.PROMPT_CONTRACT_MISMATCH


@pytest.mark.asyncio
async def test_valid_db_regime_prompt_is_active_database_source(monkeypatch):
    template = prompt_service.get_regime_prompt_template()

    async def fake_get_row(_session, key):
        if key == prompt_service.REGIME_PROMPT_KEY:
            return SimpleNamespace(value=template)
        return None

    monkeypatch.setattr(prompt_service, "_get_config_row", fake_get_row)
    monkeypatch.setattr(prompt_service, "get_session_maker", lambda: _session_factory)

    status = await prompt_service.get_regime_prompt_status()

    assert status.compatible is True
    assert status.source == "database"
    assert status.active_prompt_version == "regime_classifier_prompt_v1"


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


def _session_factory():
    return _DummySession()
