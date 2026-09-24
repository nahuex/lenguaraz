# SPDX-License-Identifier: Apache-2.0
# Lenguaraz — developer and operator entry points.
# Targets marked "feature NNN" are stubs until that feature lands (see .specify/memory/product.md §6).

SHELL := /bin/sh
.DEFAULT_GOAL := help
UV ?= uv
NPM ?= npm
COMPOSE ?= docker compose

.PHONY: help verify dev up demo web smoke-stt smoke-translate simulate samples mvp-check \
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

up: ## Start the whole stack with Docker Compose (feature 001)
	@echo "up: not implemented yet (feature 001)"; exit 1

demo: ## Serve the bundled sample stages from stages.yaml (dry run: ENGINE=fake make demo)
	$(UV) run lenguaraz serve

web: ## Build the audience view into web/dist
	cd web && $(NPM) ci --no-audit --no-fund && $(NPM) run build

smoke-stt: ## Real Gemini call: transcribe a sample clip (feature 001; uses quota)
	@echo "smoke-stt: not implemented yet (feature 001)"; exit 1

smoke-translate: ## Real Gemini call: translate a sample segment (feature 002; uses quota)
	@echo "smoke-translate: not implemented yet (feature 002)"; exit 1

simulate: ## Replay N stages concurrently and write the scale report (feature 005)
	@echo "simulate: not implemented yet (feature 005)"; exit 1

samples: ## Generate EN/ES test audio with Gemini TTS into samples/ (feature 001; uses quota)
	@echo "samples: not implemented yet (feature 001)"; exit 1

mvp-check: ## Scripted check of every MVP gate (feature 001/002)
	@echo "mvp-check: not implemented yet (feature 001/002)"; exit 1

license-check: ## Fail on any dependency license outside the allowlist (feature 007)
	@echo "license-check: not implemented yet (feature 007)"; exit 1

spdx-check: ## Every source file starts with the SPDX header (Constitution Art. XVII.A.4)
	@sh scripts/spdx_check.sh

docs-check: ## Validate doc links and config-key coverage (feature 008)
	@echo "docs-check: not implemented yet (feature 008)"; exit 1

fresh-clone-test: ## Clone the public repo into a temp dir and follow quickstart.md in dry-run mode (feature 008)
	@echo "fresh-clone-test: not implemented yet (feature 008)"; exit 1

hooks: ## Install the git pre-commit hook (gitleaks + SPDX check)
	@git config core.hooksPath .githooks && chmod +x .githooks/* scripts/*.sh && echo "hooks: core.hooksPath=.githooks"
