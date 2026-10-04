# One command vocabulary for humans, CI, and coding agents. CI calls the same
# underlying commands (see .github/workflows/ci.yml), so "green locally"
# means "green in CI". Run `make help` for the list.

PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help
.PHONY: help setup dev node node-stop reset-chain test test-integration test-sources test-all lint build check docker

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## One-time: Python venv + backend deps + frontend deps
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements-dev.txt
	npm install --prefix frontend

dev: ## Start node (if needed), backend :8000 and frontend :5173 together
	./scripts/dev.sh

node: ## Start the regtest node and mine the frozen chain (first run only)
	./scripts/start_node.sh
	cd backend && ../$(PY) setup_chain.py

node-stop: ## Stop the regtest node
	./scripts/stop_node.sh

reset-chain: ## DESTRUCTIVE: delete the local chain + fixtures (node must be stopped)
	rm -rf .bitcoin-regtest backend/fixtures.json

test: ## Unit tests: no node, no network, ~1s. Run this constantly.
	cd backend && ../$(PY) -m pytest

test-integration: ## Needs a running node (`make node`): scenarios + exact accept/reject boundaries
	cd backend && ../$(PY) -m pytest -m integration

test-sources: ## Needs internet: every cited Core source line still contains its rejection string
	cd backend && ../$(PY) -m pytest -m network

test-all: test test-integration test-sources ## Every test tier

lint: ## Frontend lint
	npm run lint --prefix frontend

build: ## Production frontend build
	npm run build --prefix frontend

check: lint build test ## Fast pre-commit gate (what CI's fast jobs run)

docker: ## Build the single-container image
	docker build -t btc-playground .
