# AlphaTransformer Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-13

## Active Technologies

- Python 3.11+ (backend), TypeScript/React (frontend) + FastAPI 0.104.0, LangChain, LangGraph, SQLAlchemy 2.0, Next.js 14, Tailwind CSS (002-custom-prompts)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+ (backend), TypeScript/React (frontend): Follow standard conventions

## Recent Changes

- 002-custom-prompts: Added Python 3.11+ (backend), TypeScript/React (frontend) + FastAPI 0.104.0, LangChain, LangGraph, SQLAlchemy 2.0, Next.js 14, Tailwind CSS

<!-- MANUAL ADDITIONS START -->
## Project Memory System

This AI_trading workspace maintains institutional knowledge in `../docs/project_notes/` for consistency across sessions.

### Memory Files

- **bugs.md** - Bug log with dates, solutions, and prevention notes
- **decisions.md** - Architectural Decision Records (ADRs) with context and trade-offs
- **key_facts.md** - Project configuration, credentials, ports, important URLs
- **issues.md** - Work log with ticket IDs, descriptions, and URLs

### Memory-Aware Protocols

**Before proposing architectural changes:**
- Check `../docs/project_notes/decisions.md` for existing decisions
- Verify the proposed approach doesn't conflict with past choices
- If it does conflict, acknowledge the existing decision and explain why a change is warranted

**When encountering errors or bugs:**
- Search `../docs/project_notes/bugs.md` for similar issues
- Apply known solutions if found
- Document new bugs and solutions when resolved

**When looking up project configuration:**
- Check `../docs/project_notes/key_facts.md` for ports, URLs, paths, and non-sensitive config
- Prefer documented facts over assumptions

**When completing work on tickets:**
- Log completed work in `../docs/project_notes/issues.md`
- Include ticket ID, date, brief description, and URL

**When user requests memory updates:**
- Update the appropriate memory file (bugs, decisions, key_facts, or issues)
- Follow the established format and style (bullet lists, dates, concise entries)

### Style Guidelines for Memory Files

- Prefer bullet lists over tables for simplicity and ease of editing
- Keep entries concise
- Always include dates for temporal context
- Include URLs for tickets, documentation, monitoring dashboards
- Manual cleanup of old entries is expected

<!-- MANUAL ADDITIONS END -->
