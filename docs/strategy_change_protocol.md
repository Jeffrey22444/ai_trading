# Strategy Change Protocol

## When this checklist is required

Use this checklist whenever changing:
- regime definitions
- setup selector
- scoring formula
- direction engine
- risk budget
- lifecycle rules
- prompt schema
- prompt wording
- DB strategy persistence
- execution decision schema

## Required steps

1. Update deterministic code.
2. Update `backend/config/strategy_contract.yaml`.
3. Bump `architecture.version` if ownership or pipeline changes.
4. Bump `prompt.version` if prompt wording or schema changes.
5. Update `regime_classifier_prompt.md` frontmatter.
6. Run prompt contract tests.
7. Reset/migrate DB runtime prompt explicitly.
8. Verify `/api/v1/trading/strategy/status`.
9. Run one dry-run analysis.
10. Confirm saved decision includes new prompt version/hash.

## Forbidden

- Updating deterministic code without updating contract when prompt assumptions change.
- Updating prompt wording without bumping prompt version.
- Relying on cache refresh to migrate DB prompt.
- Letting old database `trading_strategy` remain active.
