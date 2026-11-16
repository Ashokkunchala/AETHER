.PHONY: help install dev run robot call test lint typecheck format migrate upgrade clean docker-build docker-up docker-down

help:
	@echo "JARVIS Personal AI - Makefile commands"
	@echo "  make install   - Install dependencies"
	@echo "  make dev       - Install dev dependencies"
	@echo "  make run       - Run enhanced server"
	@echo "  make robot     - Launch the floating robot terminal animation"
	@echo "  make call      - Start a live voice call (no wake word)"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run Ruff (gate)"
	@echo "  make typecheck - Run mypy (informational; known baseline)"
	@echo "  make format    - Format code"
	@echo "  make migrate   - Create an empty manual migration"
	@echo "  make upgrade   - Apply migrations"
	@echo "  make clean     - Clean cache files"
	@echo "  make docker-up - Start the loopback-only local container"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements-dev.txt
	pip install -e ".[dev]"

run:
	uvicorn app.main_enhanced:app --reload --host 127.0.0.1 --port 8000

robot:
	python jarvis_cli.py robot

call:
	python jarvis_cli.py call

test:
	pytest -v

lint:
	ruff check .

# The project uses a hand-written sqlite3 schema, so there is no SQLAlchemy
# metadata to compare against. mypy has a pre-existing baseline of errors and
# is not a merge gate yet; use it to check the files you touch.
typecheck:
	mypy app/ --ignore-missing-imports

format:
	ruff format .

# Alembic autogenerate cannot work with target_metadata = None. Add the SQL to
# the generated file by hand and review it before running `make upgrade`.
migrate:
	alembic revision -m "jarvis schema change"

upgrade:
	alembic upgrade head

# Cross-platform cleanup (works in PowerShell, cmd.exe, and POSIX shells).
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	python -c "import pathlib, shutil; root=pathlib.Path('.'); excluded={'.venv','venv','.git','node_modules','android/.gradle'}; [shutil.rmtree(p, ignore_errors=True) for p in root.rglob('__pycache__') if not any(part in excluded for part in p.parts)]; [p.unlink(missing_ok=True) for p in root.rglob('*.py[co]') if not any(part in excluded for part in p.parts)]; [shutil.rmtree(root/p, ignore_errors=True) for p in ('.pytest_cache','.pytest-tmp','.mypy_cache','.ruff_cache','build','dist')]"
