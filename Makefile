# 🐀 Ratatouille - Data Platform in a Box
# Usage: make <command>

.PHONY: help up down logs build clean run status query dev dev-merge dev-drop dev-status dev-branches

help:
	@echo "🐀 Ratatouille - Anyone Can Data!"
	@echo ""
	@echo "Usage: make <command>"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  PLATFORM"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  up        Start the platform"
	@echo "  down      Stop the platform"
	@echo "  build     Rebuild images"
	@echo "  logs      Follow logs"
	@echo "  status    Show status"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  DATA"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  run       Run all pipelines"
	@echo "  query     ClickHouse shell"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  DEV MODE (Iceberg Branches)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  dev BRANCH=x        Start dev session"
	@echo "  dev-merge BRANCH=x  Merge branch to main"
	@echo "  dev-drop BRANCH=x   Drop branch"
	@echo "  dev-status          Show current dev mode"
	@echo "  dev-branches        List all branches"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  BROWSER"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  Dagster:     http://localhost:3030"
	@echo "  Jupyter:     http://localhost:8889 (token: ratatouille)"
	@echo "  MinIO:       http://localhost:9001 (ratatouille/ratatouille123)"
	@echo "  ClickHouse:  http://localhost:8123 (ratatouille/ratatouille123)"
	@echo ""

# ============================================
# PLATFORM
# ============================================

up:
	@echo "🐀 Starting Ratatouille..."
	@docker compose up -d --build
	@echo ""
	@echo "✅ Platform ready!"
	@echo "   Dagster:     http://localhost:3030"
	@echo "   Jupyter:     http://localhost:8889 (token: ratatouille)"
	@echo "   MinIO:       http://localhost:9001"
	@echo "   ClickHouse:  http://localhost:8123"

down:
	@echo "🛑 Stopping..."
	@docker compose down

build:
	@echo "🔨 Building..."
	@docker compose build --no-cache

logs:
	@docker compose logs -f

status:
	@docker compose ps

# ============================================
# DATA
# ============================================

run:
	@echo "⚡ Running all pipelines..."
	@docker compose exec dagster dagster asset materialize --select "*"

query:
	@echo "🏠 ClickHouse shell..."
	@docker compose exec clickhouse clickhouse-client --user ratatouille --password ratatouille123

# ============================================
# DEV MODE
# ============================================

dev:
ifndef BRANCH
	@echo "❌ Usage: make dev BRANCH=feature/your-branch"
	@exit 1
endif
	@echo "🔬 Starting dev session: $(BRANCH)"
	@docker compose exec jupyter python -c "from ratatouille import rat; rat.dev_start('$(BRANCH)')"
	@echo ""
	@echo "✅ Dev mode active! Open Jupyter at http://localhost:8889"

dev-merge:
ifndef BRANCH
	@echo "❌ Usage: make dev-merge BRANCH=feature/your-branch"
	@exit 1
endif
	@echo "🔀 Merging branch: $(BRANCH)"
	@docker compose exec jupyter python -c "from ratatouille import rat; rat.dev_merge('$(BRANCH)')"

dev-drop:
ifndef BRANCH
	@echo "❌ Usage: make dev-drop BRANCH=feature/your-branch"
	@exit 1
endif
	@echo "🗑️ Dropping branch: $(BRANCH)"
	@docker compose exec jupyter python -c "from ratatouille import rat; rat.dev_drop('$(BRANCH)')"

dev-status:
	@echo "📊 Dev mode status:"
	@docker compose exec jupyter python -c "from ratatouille import rat; import json; print(json.dumps(rat.dev_status(), indent=2))"

dev-branches:
	@echo "🌿 Branches:"
	@docker compose exec jupyter python -c "from ratatouille import rat; import json; print(json.dumps(rat.dev_branches(), indent=2))"

# ============================================
# CLEANUP
# ============================================

clean:
	@echo "🧹 Cleaning up..."
	@docker compose down -v
	@echo "✅ Clean"
