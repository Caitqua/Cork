# Repository Guidelines

## Project Structure & Module Organization
- `src/main/app.py` is the entry point and hosts the `App` router.
- Place view frames and widgets in `src/ui/` (e.g., `dashboard.py`).
- Reserve `src/common/` for shared utilities; add `__init__.py` files when packages evolve.
- Store icons and other static assets in `src/icons/` using lowercase, hyphenated names.
- Treat `legacy/` as read-only reference material.
- Keep workflow helpers under `scripts/`, organised by task (dev, build, lint, test).

## Build, Test, and Development Commands
- `make run` launches the app through `scripts/dev app`.
- `python3 -m src.main.app` runs the UI directly for quick smoke checks.
- Add executable helpers in `scripts/build` and `scripts/lint` as packaging or quality gates appear; document usage in script headers.

## Coding Style & Naming Conventions
- Target Python 3.11+, follow PEP 8, and use 4-space indentation—convert older tabbed code when you touch it.
- Use `CamelCase` for classes, `snake_case` for everything else, and descriptive module names (`dashboard.py`, `side_page.py`).
- Keep navigation logic inside `App.show_frame`, exposing new screens via the existing frame pattern.
- Prefer explicit `from src...` imports and avoid module-level side effects in UI code.
- Run `ruff` and `black` locally if available; add project configs once the team standardises on them.

## Testing Guidelines
- No automated suite exists yet; create a top-level `tests/` package that mirrors `src/` and adopt `pytest`.
- Focus on navigation flows, asset loading, and any new helpers; use fixtures to stub Tkinter prompts.
- Wire the runner into `scripts/test` so CI can call `./scripts/test` with no flags.
- Document manual smoke steps (e.g., “launch app, switch tabs”) until automation lands.

## Commit & Pull Request Guidelines
- Commit subjects use the imperative mood and wrap at 72 characters; group related GUI updates.
- Reference issues in the body (`Refs #123`) and list manual verification or scripts run.
- PRs must include a concise summary, before/after screenshots or GIFs for UI work, and the commands/tests executed.
- Request at least one peer review and block merges on failing tests or lint warnings.

## Environment & Dependencies
- Create an isolated env with `python3 -m venv .venv && source .venv/bin/activate`.
- Install runtime deps with `pip install pillow`; record new libraries in `requirements.txt` when they are added.
- Develop on macOS or Linux for parity with tooling; Windows is untested, so confirm core flows manually if you try it.
