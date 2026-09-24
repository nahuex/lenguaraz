# SPDX-License-Identifier: Apache-2.0
# Lenguaraz — developer and operator entry points.
# Targets marked "feature NNN" are stubs until that feature lands (see .specify/memory/product.md §6).

SHELL := /bin/sh
.DEFAULT_GOAL := help
UV ?= uv
NPM ?= npm
COMPOSE ?= docker compose

.PHONY: help verify dev up down logs demo web smoke-stt smoke-translate simulate samples mvp-check \
        license-check spdx-check docs-check fresh-clone-test hooks

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

verify: ## ruff + mypy + pytest + frontend build + SPDX headers (must be green before every commit)
	@if [ -f pyproject.toml ]; then \
		$(UV) run ruff check . && $(UV) run ruff format --check . && $(UV) run mypy && $(UV) run pytest -q; \
	else echo "verify: no pyproject.toml yet (feature 001) - skipping Python checks"; fi
	@if [ -f web/package.json ]; then cd web && $(NPM) run build; \
	else echo "verify: no web/ yet (feature 001) - skipping frontend build"; fi
	@$(MAKE) --no-print-directory spdx-check

dev: ## Run the API with auto-reload on http://127.0.0.1:8000 (ENGINE=fake for a dry run)
	$(UV) run lenguaraz serve --host 127.0.0.1 --reload

up: ## Build and start the whole stack with Docker Compose on http://localhost:8000
	$(COMPOSE) up --build -d && echo "Lenguaraz is starting: http://localhost:8000 (logs: make logs)"

down: ## Stop the Docker Compose stack
	$(COMPOSE) down

logs: ## Follow the container logs
	$(COMPOSE) logs -f

demo: ## Serve the bundled sample stages from stages.yaml (dry run: ENGINE=fake make demo)
	$(UV) run lenguaraz serve

web: ## Build the audience view into web/dist
	cd web && $(NPM) ci --no-audit --no-fund && $(NPM) run build

smoke-stt: ## Real Gemini call: transcribe samples/en_kubernetes.wav, print WER/latency/tokens (uses quota)
	$(UV) run lenguaraz smoke-stt $(SMOKE_ARGS)

smoke-translate: ## Real Gemini call: translate sample segments EN->ES and ES->EN, report TTFT/latency/tokens/glossary adherence (uses quota)
	$(UV) run lenguaraz smoke-translate $(SMOKE_ARGS)

simulate: ## Run N stages in one process (SIM_ARGS="--stages 10 --seconds 60 --real 2") and write docs/scale-report.md
	$(UV) run lenguaraz simulate $(SIM_ARGS)

samples: ## Generate EN/ES test audio + sentence boundaries with Gemini TTS into samples/ (uses quota)
	$(UV) run lenguaraz samples $(SAMPLES_ARGS)

mvp-check: ## Scripted check of every MVP gate (fake engine by default; MVP_ARGS="--engine gemini" for real)
	$(UV) run lenguaraz mvp-check $(MVP_ARGS)

license-check: ## Fail on any dependency license outside the allowlist (feature 007)
	@echo "license-check: not implemented yet (feature 007)"; exit 1

spdx-check: ## Every source file starts with the SPDX header (Constitution Art. XVII.A.4)
	@sh scripts/spdx_check.sh

docs-check: ## Every config key is documented and every relative doc link resolves
	$(UV) run python scripts/docs_check.py

fresh-clone-test: ## Clone the public repo into a temp dir and follow quickstart.md in dry-run mode (feature 008)
	@echo "fresh-clone-test: not implemented yet (feature 008)"; exit 1

hooks: ## Install the git pre-commit hook (gitleaks + SPDX check)
	@git config core.hooksPath .githooks && chmod +x .githooks/* scripts/*.sh && echo "hooks: core.hooksPath=.githooks"
