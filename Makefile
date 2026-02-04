# 🐀 Ratatouille - Data Platform in a Box
# Usage: make <command>

.PHONY: help up down logs build clean status test lint format typecheck check dev-shell query run

# Default container runtime (podman or docker)
CONTAINER_RUNTIME ?= podman
COMPOSE_CMD = $(CONTAINER_RUNTIME) compose

# Colors
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

help:
	@echo "🐀 Ratatouille - Anyone Can Data!"
	@echo ""
	@echo "Usage: make <command>"
	@echo ""
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "$(CYAN)  DEVELOPMENT$(RESET)"
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "  test        Run tests"
	@echo "  lint        Run linter (ruff)"
	@echo "  format      Format code (ruff)"
	@echo "  typecheck   Run type checker (mypy)"
	@echo "  check       Run all checks (lint + typecheck + test)"
	@echo "  dev-shell   Open shell in dev container"
	@echo ""
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "$(CYAN)  PLATFORM$(RESET)"
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "  up          Start the platform"
	@echo "  down        Stop the platform"
	@echo "  build       Rebuild images"
	@echo "  logs        Follow logs"
	@echo "  status      Show container status"
	@echo "  clean       Stop and remove volumes"
	@echo ""
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "$(CYAN)  DATA$(RESET)"
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "  run         Run all pipelines"
	@echo "  query       DuckDB shell"
	@echo ""
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "$(CYAN)  WEB UI$(RESET)"
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "  Dagster:    http://localhost:3030"
	@echo "  Jupyter:    http://localhost:8889 (token: ratatouille)"
	@echo "  MinIO:      http://localhost:9001 (ratatouille/ratatouille123)"
	@echo "  Nessie:     http://localhost:19120"
	@echo ""
	@echo "$(YELLOW)Tip: Set CONTAINER_RUNTIME=docker to use Docker instead of Podman$(RESET)"
	@echo ""

# ============================================
# DEVELOPMENT
# ============================================

test:
	@echo "🧪 Running tests..."
	@$(COMPOSE_CMD) run --rm --build ratatouille pytest tests/ -v

test-unit:
	@echo "🧪 Running unit tests..."
	@$(COMPOSE_CMD) run --rm --build ratatouille pytest tests/unit/ -v

test-integration:
	@echo "🧪 Running integration tests..."
	@$(COMPOSE_CMD) run --rm --build ratatouille pytest tests/integration/ -v -m integration

test-cov:
	@echo "🧪 Running tests with coverage..."
	@$(COMPOSE_CMD) run --rm --build ratatouille pytest tests/ -v --cov=src/ratatouille --cov-report=term-missing

lint:
	@echo "🔍 Linting..."
	@$(COMPOSE_CMD) run --rm --build ratatouille ruff check src/ tests/

lint-fix:
	@echo "🔧 Fixing lint issues..."
	@$(COMPOSE_CMD) run --rm --build ratatouille ruff check src/ tests/ --fix

format:
	@echo "✨ Formatting..."
	@$(COMPOSE_CMD) run --rm --build ratatouille ruff format src/ tests/

format-check:
	@echo "🔍 Checking format..."
	@$(COMPOSE_CMD) run --rm --build ratatouille ruff format src/ tests/ --check

typecheck:
	@echo "🔬 Type checking..."
	@$(COMPOSE_CMD) run --rm --build ratatouille mypy src/ratatouille

check: lint-fix format typecheck test
	@echo ""
	@echo "$(GREEN)✅ All checks passed!$(RESET)"

dev-shell:
	@echo "🐚 Opening dev shell..."
	@$(COMPOSE_CMD) run --rm --build ratatouille bash

# ============================================
# PLATFORM
# ============================================

up:
	@echo "🐀 Starting Ratatouille..."
	@$(COMPOSE_CMD) up -d --build
	@echo ""
	@echo "$(GREEN)✅ Platform ready!$(RESET)"
	@echo "   Dagster:    http://localhost:3030"
	@echo "   Jupyter:    http://localhost:8889 (token: ratatouille)"
	@echo "   MinIO:      http://localhost:9001"
	@echo "   Nessie:     http://localhost:19120"

down:
	@echo "🛑 Stopping..."
	@$(COMPOSE_CMD) down

build:
	@echo "🔨 Building..."
	@$(COMPOSE_CMD) build --no-cache

logs:
	@$(COMPOSE_CMD) logs -f

status:
	@$(COMPOSE_CMD) ps

# ============================================
# DATA
# ============================================

run:
	@echo "⚡ Running all pipelines..."
	@$(COMPOSE_CMD) exec dagster dagster asset materialize --select "*"

query:
	@echo "🦆 DuckDB shell..."
	@$(COMPOSE_CMD) run --rm ratatouille python -c "import duckdb; import readline; duckdb.connect(':memory:').sql('SELECT 1 AS hello').show()"
	@echo "Use: $(COMPOSE_CMD) exec jupyter python -c \"from ratatouille import sdk; sdk.query('SELECT 1')\""

# ============================================
# WORKSPACE IMAGE
# ============================================

build-workspace:
	@echo "🐀 Building workspace image..."
	@$(CONTAINER_RUNTIME) build -f Dockerfile.workspace -t ratatouille-workspace:latest .
	@echo "$(GREEN)✅ Image built: ratatouille-workspace:latest$(RESET)"
	@echo ""
	@echo "To use in devcontainer, the image is now available locally."

# ============================================
# CLEANUP
# ============================================

clean:
	@echo "🧹 Cleaning up..."
	@$(COMPOSE_CMD) down -v --remove-orphans
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✅ Clean$(RESET)"

clean-all: clean
	@echo "🧹 Deep clean (removing data)..."
	@rm -rf data/
	@echo "$(GREEN)✅ All clean$(RESET)"
