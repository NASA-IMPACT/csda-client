# Repository Guidelines

## Project Structure & Module Organization
- `src/csda_client/` holds the Python package (client logic in `client.py`, Pydantic models in `models.py`, public exports in `__init__.py`).
- `tests/` contains pytest tests (`test_*.py`) and shared fixtures in `conftest.py`.
- `docs/` and `mkdocs.yml` drive the documentation site and example notebooks.

## Build, Test, and Development Commands
- `uv sync` installs all default dev and docs dependency groups (see `pyproject.toml`).
- `uv run pytest --with-earthdata-login` runs the full test suite, including tests that hit the live CSDA APIs (requires credentials).
- `uv run mkdocs serve` builds and serves docs locally at `http://127.0.0.1:8000/csda-client/`.

## Coding Style & Naming Conventions
- Python 3.12+ (per `pyproject.toml`) with 4-space indentation.
- Linting is enforced with Ruff (imports are sorted and core error checks enabled).
- Type checking uses `mypy` for `src/**/*.py` and `tests/**/*.py`.
- Prefer `snake_case` for functions/modules, `PascalCase` for classes, and clear, domain-specific names (e.g., `tasking`, `orders`, `stac`).

## Testing Guidelines
- Framework: `pytest`.
- Test files should be named `test_*.py` and live under `tests/`.
- Earthdata-authenticated tests are skipped by default; enable them with `.env` or `.netrc` credentials before running the full suite.

## Commit & Pull Request Guidelines
- Commit history mostly follows Conventional Commits: `feat:`, `fix:`, `chore:`, `refactor:` (optional scopes like `fix(ci):` appear). Keep subjects short and include an issue/PR reference when helpful.
- PRs should include: a brief summary, testing notes (`uv run pytest ...`), and doc updates when public API behavior changes (update `docs/` and examples as needed).

## Security & Configuration Tips
- Never commit secrets. Use a local `.env` file with `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`, or configure `.netrc` for Earthdata login.
