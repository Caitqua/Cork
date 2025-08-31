# Repository Guidelines

## Project Structure & Module Organization
- Current files: `dev_doc.txt` (feature outline). Place implementation under `src/` grouped by feature: `dashboard/`, `cases/`, `evidence/`, `documents/`, `notebook/`, `board/`.
- Mirror tests under `tests/` using the same folder names (e.g., `tests/cases/`). Shared utilities live in `src/common/`. Static assets go in `assets/`. Additional docs in `docs/`.

## Build, Test, and Development Commands
- Use wrapper scripts in `scripts/` to keep toolchains swappable:
  - `scripts/dev` — start local dev server or watcher.
  - `scripts/build` — create a production build.
  - `scripts/test` — run unit tests; pass `-u` to update snapshots.
  - `scripts/lint` — run formatters and linters.
- Examples:
  - Node: `npm run dev`, `npm run build`, `npm test`, `npm run lint`.
  - Python: `pytest -q`, `black .`, `ruff check .`.

## Coding Style & Naming Conventions
- Indentation: 2 spaces for web/TS; 4 spaces for Python.
- Files: `kebab-case` for files; `PascalCase` for components/classes.
- Names: `camelCase` for variables/functions; `snake_case` for Python modules.
- Tools: Prettier (JS/TS/JSON/MD) and Black (Python); lint with ESLint or Ruff. Run `scripts/lint` before opening a PR.

## Testing Guidelines
- Frameworks: Vitest/Jest (JS/TS) or Pytest (Python).
- Structure: one test file per module/component (e.g., `cases.service.test.ts`, `tests/cases/test_models.py`).
- Coverage: target ≥80% lines; include tests for new and changed logic. Run `scripts/test --coverage` when available.

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits (e.g., `feat(cases): add archive flow`).
- PRs: include a clear description, linked issues, and references to affected sections in `dev_doc.txt`. Add screenshots/GIFs for UI changes and brief test notes.
- Checks: PRs must pass build, lint, and tests.

## Security & Configuration
- Do not commit secrets. Provide `.env.example` and use `.env` locally.
- Use anonymized/test data; redact PII in examples and screenshots.
- Document feature flags and config in `docs/config.md` when introduced.

