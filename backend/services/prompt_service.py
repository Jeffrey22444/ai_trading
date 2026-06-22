"""Runtime prompt service for the deterministic regime architecture."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy import select

from config.settings import config
from database.database import get_session_maker
from database.models import SystemConfig
from services.strategy_contract import (
    StrategyValidationResult,
    get_strategy_field_catalog,
    validate_strategy_field_references,
)

logger = logging.getLogger("AlphaTransformer")

REGIME_PROMPT_KEY = "regime_classifier_prompt"
REGIME_PROMPT_VERSION_KEY = "regime_classifier_prompt_version"
REGIME_PROMPT_HASH_KEY = "regime_classifier_prompt_hash"
STRATEGY_ARCHITECTURE_VERSION_KEY = "strategy_architecture_version"
STRATEGY_CONTRACT_HASH_KEY = "strategy_contract_hash"
LEGACY_TRADING_STRATEGY_KEY = "trading_strategy"
LEGACY_TRADING_STRATEGY_ARCHIVE_KEY = "legacy_trading_strategy_archive"
PROMPT_CONTRACT_MISMATCH = "PROMPT_CONTRACT_MISMATCH"

CONTRACT_PATH = "backend/config/strategy_contract.yaml"
DEFAULT_REGIME_TEMPLATE_PATH = "backend/config/regime_classifier_prompt.md"

_prompt_cache: Optional[str] = None
_prompt_cache_hash: Optional[str] = None

# Backward-compatible test-visible names.
_strategy_cache: Optional[str] = None
_cache_valid = False

LEGACY_PROMPT_TERMS = {
    "D1-D5",
    "Kelly",
    "position_size_usd",
    "stop_loss_price",
    "take_profit_price",
    "leverage",
    "direction_bias",
    "action_allowed",
    "OPEN_LONG",
    "OPEN_SHORT",
    "CLOSE_LONG",
    "CLOSE_SHORT",
    "ENTRY_HOLD",
    "POSITION_HOLD",
}

TRADE_OUTPUT_FIELDS = {
    "action",
    "position_size_usd",
    "stop_loss_price",
    "take_profit_price",
    "leverage",
    "setup",
    "lifecycle",
    "exit",
    "risk_budget",
}


@dataclass(frozen=True)
class PromptValidationResult:
    valid: bool
    reason: Optional[str] = None
    frontmatter: Optional[dict] = None


@dataclass(frozen=True)
class RegimePromptStatus:
    ok: bool
    compatible: bool
    error_code: Optional[str]
    architecture_mode: str
    architecture_version: str
    prompt_role: str
    expected_prompt_version: str
    active_prompt_version: str
    template_prompt_version: str
    output_schema_version: str
    source: str
    active_hash: str
    template_hash: str
    contract_hash: str
    legacy_trading_strategy_present: bool
    mismatch_reason: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["prompt_version"] = self.active_prompt_version
        data["prompt_source"] = self.source
        data["prompt_hash"] = self.active_hash
        return data


def _repo_path(relative_or_absolute: str) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_hash(value: dict) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")))


def load_strategy_contract(path: str = CONTRACT_PATH) -> dict:
    contract_path = _repo_path(path)
    if not contract_path.exists():
        raise FileNotFoundError(f"strategy contract missing: {contract_path}")
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    if contract.get("architecture", {}).get("mode") != "regime_deterministic":
        raise ValueError("strategy contract mode must be regime_deterministic")
    prompt = contract.get("prompt") or {}
    if prompt.get("role") != "REGIME_CLASSIFIER_ONLY":
        raise ValueError("prompt.role must be REGIME_CLASSIFIER_ONLY")
    template_path = prompt.get("template_path")
    if not template_path or not _repo_path(template_path).exists():
        raise ValueError("prompt.template_path must point to an existing file")
    return contract


def get_regime_prompt_template_path() -> Path:
    configured_path = (
        getattr(config.agent, "regime_classifier_prompt_template_path", None)
        or load_strategy_contract()["prompt"]["template_path"]
        or DEFAULT_REGIME_TEMPLATE_PATH
    )
    return _repo_path(configured_path)


def get_regime_prompt_template() -> str:
    path = get_regime_prompt_template_path()
    prompt = path.read_text(encoding="utf-8").strip()
    result = validate_regime_prompt_contract(prompt)
    if not result.valid:
        raise ValueError(f"regime prompt template invalid: {result.reason}")
    return prompt


def _parse_frontmatter(prompt: str) -> tuple[dict, str]:
    if not prompt.startswith("---\n"):
        return {}, prompt
    end = prompt.find("\n---", 4)
    if end == -1:
        return {}, prompt
    frontmatter = yaml.safe_load(prompt[4:end]) or {}
    body = prompt[end + 4 :].strip()
    return frontmatter, body


def validate_regime_prompt_contract(prompt: str) -> PromptValidationResult:
    try:
        contract = load_strategy_contract()
    except Exception as exc:
        return PromptValidationResult(False, str(exc))

    frontmatter, body = _parse_frontmatter(prompt.strip())
    if not frontmatter:
        return PromptValidationResult(False, "missing prompt frontmatter", frontmatter)

    expected = {
        "architecture_mode": contract["architecture"]["mode"],
        "architecture_version": contract["architecture"]["version"],
        "prompt_role": contract["prompt"]["role"],
        "prompt_version": contract["prompt"]["version"],
        "output_schema_version": contract["prompt"]["output_schema_version"],
    }
    for key, value in expected.items():
        if frontmatter.get(key) != value:
            return PromptValidationResult(
                False, f"{key} mismatch: expected {value}", frontmatter
            )

    if contract.get("validation", {}).get("reject_legacy_prompt_terms", True):
        found = sorted(term for term in LEGACY_PROMPT_TERMS if term in body)
        if found:
            return PromptValidationResult(
                False, f"legacy prompt terms present: {', '.join(found)}", frontmatter
            )
    return PromptValidationResult(True, frontmatter=frontmatter)


def reject_trade_action_fields(payload: object) -> bool:
    if isinstance(payload, dict):
        if TRADE_OUTPUT_FIELDS.intersection(payload):
            return True
        return any(reject_trade_action_fields(value) for value in payload.values())
    if isinstance(payload, list):
        return any(reject_trade_action_fields(item) for item in payload)
    return False


async def _get_config_row(session, key: str):
    result = await session.execute(select(SystemConfig).where(SystemConfig.key == key))
    return result.scalar_one_or_none()


async def _upsert_config(session, key: str, value: str, description: str) -> None:
    row = await _get_config_row(session, key)
    if row:
        row.value = value
        row.description = description
    else:
        session.add(SystemConfig(key=key, value=value, description=description))


def _template_status_fields() -> tuple[dict, str, str, str]:
    contract = load_strategy_contract()
    template = get_regime_prompt_template()
    return contract, template, _sha256(template), _canonical_hash(contract)


async def _legacy_present(session) -> bool:
    legacy = await _get_config_row(session, LEGACY_TRADING_STRATEGY_KEY)
    return bool(legacy and legacy.value.strip())


async def get_regime_prompt_status() -> RegimePromptStatus:
    contract, template, template_hash, contract_hash = _template_status_fields()
    prompt = contract["prompt"]
    architecture = contract["architecture"]
    runtime = contract["runtime"]

    async with get_session_maker()() as session:
        legacy_present = await _legacy_present(session)
        db_row = await _get_config_row(session, runtime["db_prompt_key"])
        active = db_row.value.strip() if db_row and db_row.value.strip() else ""

        if active:
            active_hash = _sha256(active)
            validation = validate_regime_prompt_contract(active)
            active_version = (
                validation.frontmatter or {}
            ).get("prompt_version", "unknown_or_legacy")
            if validation.valid:
                return RegimePromptStatus(
                    ok=True,
                    compatible=True,
                    error_code=None,
                    architecture_mode=architecture["mode"],
                    architecture_version=architecture["version"],
                    prompt_role=prompt["role"],
                    expected_prompt_version=prompt["version"],
                    active_prompt_version=active_version,
                    template_prompt_version=prompt["version"],
                    output_schema_version=prompt["output_schema_version"],
                    source="database",
                    active_hash=active_hash,
                    template_hash=template_hash,
                    contract_hash=contract_hash,
                    legacy_trading_strategy_present=legacy_present,
                )
            return _mismatch_status(
                contract,
                source="database",
                active_hash=active_hash,
                template_hash=template_hash,
                contract_hash=contract_hash,
                legacy_present=legacy_present,
                reason=validation.reason or "database regime prompt is incompatible",
                active_version=active_version,
            )

        if legacy_present and runtime.get("migration_policy") == "BLOCK_ON_MISMATCH":
            return _mismatch_status(
                contract,
                source="mismatch",
                active_hash="",
                template_hash=template_hash,
                contract_hash=contract_hash,
                legacy_present=True,
                reason="legacy trading_strategy exists without compatible regime prompt",
                active_version="unknown_or_legacy",
            )

        return RegimePromptStatus(
            ok=True,
            compatible=True,
            error_code=None,
            architecture_mode=architecture["mode"],
            architecture_version=architecture["version"],
            prompt_role=prompt["role"],
            expected_prompt_version=prompt["version"],
            active_prompt_version=prompt["version"],
            template_prompt_version=prompt["version"],
            output_schema_version=prompt["output_schema_version"],
            source="template",
            active_hash=template_hash,
            template_hash=template_hash,
            contract_hash=contract_hash,
            legacy_trading_strategy_present=False,
        )


def _mismatch_status(
    contract: dict,
    *,
    source: str,
    active_hash: str,
    template_hash: str,
    contract_hash: str,
    legacy_present: bool,
    reason: str,
    active_version: str,
) -> RegimePromptStatus:
    return RegimePromptStatus(
        ok=False,
        compatible=False,
        error_code=PROMPT_CONTRACT_MISMATCH,
        architecture_mode=contract["architecture"]["mode"],
        architecture_version=contract["architecture"]["version"],
        prompt_role=contract["prompt"]["role"],
        expected_prompt_version=contract["prompt"]["version"],
        active_prompt_version=active_version,
        template_prompt_version=contract["prompt"]["version"],
        output_schema_version=contract["prompt"]["output_schema_version"],
        source=source,
        active_hash=active_hash,
        template_hash=template_hash,
        contract_hash=contract_hash,
        legacy_trading_strategy_present=legacy_present,
        mismatch_reason=reason,
        message="Runtime database prompt is incompatible with deterministic regime architecture.",
    )


async def get_regime_classifier_prompt() -> str:
    global _prompt_cache, _prompt_cache_hash, _strategy_cache, _cache_valid

    status = await get_regime_prompt_status()
    if not status.compatible:
        raise RuntimeError(PROMPT_CONTRACT_MISMATCH)

    if status.source == "database":
        async with get_session_maker()() as session:
            row = await _get_config_row(session, REGIME_PROMPT_KEY)
            prompt = row.value.strip()
    else:
        prompt = await reset_regime_prompt_to_template()

    prompt_hash = _sha256(prompt)
    if _prompt_cache and _prompt_cache_hash == prompt_hash:
        return _prompt_cache

    _prompt_cache = prompt
    _prompt_cache_hash = prompt_hash
    _strategy_cache = prompt
    _cache_valid = True
    return prompt


async def reset_regime_prompt_to_template() -> str:
    prompt = get_regime_prompt_template()
    contract = load_strategy_contract()
    prompt_hash = _sha256(prompt)
    contract_hash = _canonical_hash(contract)
    async with get_session_maker()() as session:
        await _upsert_config(
            session,
            REGIME_PROMPT_KEY,
            prompt,
            "Runtime regime classifier prompt reset from template",
        )
        await _upsert_config(
            session,
            REGIME_PROMPT_VERSION_KEY,
            contract["prompt"]["version"],
            "Runtime regime classifier prompt version",
        )
        await _upsert_config(
            session,
            REGIME_PROMPT_HASH_KEY,
            prompt_hash,
            "Runtime regime classifier prompt hash",
        )
        await _upsert_config(
            session,
            STRATEGY_ARCHITECTURE_VERSION_KEY,
            contract["architecture"]["version"],
            "Deterministic strategy architecture version",
        )
        await _upsert_config(
            session,
            STRATEGY_CONTRACT_HASH_KEY,
            contract_hash,
            "Deterministic strategy contract hash",
        )
        await session.commit()
    clear_regime_prompt_cache()
    return prompt


async def migrate_legacy_trading_strategy_to_archive() -> bool:
    async with get_session_maker()() as session:
        legacy = await _get_config_row(session, LEGACY_TRADING_STRATEGY_KEY)
        if not legacy or not legacy.value.strip():
            return False
        archive = await _get_config_row(session, LEGACY_TRADING_STRATEGY_ARCHIVE_KEY)
        archived = json.dumps(
            {"archived_at": "runtime", "strategy": legacy.value}, ensure_ascii=False
        )
        if archive:
            archive.value = archived
            archive.description = "Archived legacy trading strategy prompt"
        else:
            session.add(
                SystemConfig(
                    key=LEGACY_TRADING_STRATEGY_ARCHIVE_KEY,
                    value=archived,
                    description="Archived legacy trading strategy prompt",
                )
            )
        legacy.value = ""
        legacy.description = "Deprecated legacy prompt archived"
        await session.commit()
    clear_regime_prompt_cache()
    return True


def clear_regime_prompt_cache() -> None:
    global _prompt_cache, _prompt_cache_hash, _strategy_cache, _cache_valid
    _prompt_cache = None
    _prompt_cache_hash = None
    _strategy_cache = None
    _cache_valid = False
    logger.info("regime prompt cache cleared")


async def set_trading_strategy(strategy: str) -> bool:
    if not validate_regime_prompt_contract(strategy).valid:
        return False
    async with get_session_maker()() as session:
        await _upsert_config(
            session,
            REGIME_PROMPT_KEY,
            strategy.strip(),
            "User supplied runtime regime classifier prompt",
        )
        await _upsert_config(
            session,
            REGIME_PROMPT_HASH_KEY,
            _sha256(strategy.strip()),
            "Runtime regime classifier prompt hash",
        )
        await session.commit()
    clear_regime_prompt_cache()
    return True


def validate_trading_strategy(strategy: str) -> StrategyValidationResult:
    """Legacy field-reference validator kept for existing schema endpoint."""
    return validate_strategy_field_references(strategy, list(config.agent.timeframes))


def get_trading_strategy_field_catalog() -> dict:
    return get_strategy_field_catalog(list(config.agent.timeframes))


def clear_strategy_cache() -> None:
    clear_regime_prompt_cache()
