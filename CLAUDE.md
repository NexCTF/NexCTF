# Development stack
All dev commands are wrapped by `Taskfile.yml` (run `task` from the repo root). Env vars come from `.env.dev`.

- Start infra (postgres, valkey, s3): `task dev:infra:up`
- Start backend (runs migrations + fixtures, then serves): `task dev:backend`
- Start frontend dev server: `task dev:frontend`
- Stop infra: `task dev:infra:down`
- Stop infra + clean volumes: `task dev:infra:down -- -v`
- Run all checks (backend + frontend): `task dev:check`
- Apply all auto-fixes (backend + frontend): `task dev:fix`
- Tail infra logs: `task dev:logs`

Infra must be up (`task dev:infra:up`) before running the backend or its tests.

One-time setup: `task dev:hooks:install` installs git pre-commit hooks (via prek, running `dev:backend:check` / `dev:frontend:check` from `.pre-commit-config.yaml`). Run hooks on demand with `task dev:hooks:run`.

# Backend
The backend code is in `backend/` folder.

## Package management
This project uses uv. Do not use pip, pip-tools, poetry, or conda.

- Add runtime dependency: `uv add <package>` (writes to `[project.dependencies]`)
- Add dev dependency: `uv add --dev <package>` (writes to `[dependency-groups]` per PEP 735)
- Remove dependency: `uv remove <package>`
- Sync environment from lockfile: `uv sync`
- Regenerate lockfile from constraints: `uv lock`
- Upgrade locked versions: `uv lock --upgrade`
- Commit `uv.lock` to version control (current uv guidance is to commit it for applications, CLIs, and libraries)

## Testing
- Tool: pytest
- Before running you need to start the dev infra with `task dev:infra:up`
- Run all backend tests: `task dev:backend:test`
- Run specific backend tests: `task dev:backend:test -- [TEST_FILE_PATH]`

## Linting, formatting and type checking
- Tools: ruff (lint + format) and ty (type checking)
- Check everything, no changes (what CI runs): `task dev:backend:check`
- Auto-fix lint issues + format: `task dev:backend:fix`
- Granular commands (run from `backend/`):
  - `uv run ruff check .` / `uv run ruff check --fix .`
  - `uv run ruff format .` / `uv run ruff format --check .`
  - `uv run ty check`
- Ruff has no explicit config in `pyproject.toml` (runs on defaults). ty config lives under `[tool.ty.src]`.

## Code style
- Follow the Google python style guide
- Type hints required for all code
- Public APIs must have docstrings
- All docstrings must remain short
- Functions must be focused and small


# Frontend
The frontend code is in `frontend/` folder.

## Package management
This project uses bun. Do not use npm or yarn.

- Add dependency: `bun add <package>`
- Add dev dependency: `bun add -d <package>`
- Remove dependency: `bun remove <package>`
- Sync environment from lockfile: `bun install --frozen-lockfile`
- Commit `bun.lock` to version control

## Linting, formatting and type checking
- Tools: biome (lint + format) and tsc (type checking)
- Check everything, no changes (what CI runs): `task dev:frontend:check`
- Auto-fix lint + format: `task dev:frontend:fix`
- Granular commands (run from `frontend/`):
  - `bunx biome lint .` / `bunx biome check --write .`
  - `bunx biome format --write .`
  - `bunx tsc -b`
- Biome config lives in `biome.json`. tsc config lives in `tsconfig.json` / `tsconfig.app.json`.

## Code style
- Type hints (TypeScript types) required for all code
- Functions must be focused and small
