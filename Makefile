# Root tasks (DEV-01 §3.3). `make test-all` runs every component's suite the way CI does.
# Needs: uv (Python 3.12 is fetched by uv), Node 20 and 22 (portal, sample system),
# PostgreSQL 16 binaries in /usr/lib/postgresql/16/bin or PG_BIN (insights, sample system).
# No target reaches a client system; tests make no network calls.

UV ?= uv
PY := --python 3.12
NPM ?= npm

.PHONY: help test-all lint-all check-all docs-check \
	test-schemas test-tsl test-plugin test-insights test-portal test-portal-e2e test-sample test-deploy-ops \
	lint-schemas lint-tsl lint-plugin lint-insights lint-portal lint-sample lint-deploy-ops

help:
	@echo "make test-all     every component test suite"
	@echo "make lint-all     every linter and type checker"
	@echo "make docs-check   relative links, anchors, registry ids, doc control rows, backlog.csv in sync"
	@echo "make check-all    lint-all + test-all + docs-check + portal e2e"

test-all: test-schemas test-tsl test-plugin test-insights test-portal test-sample test-deploy-ops

lint-all: lint-schemas lint-tsl lint-plugin lint-insights lint-portal lint-sample lint-deploy-ops

check-all: lint-all test-all docs-check test-portal-e2e

docs-check:
	python3 scripts/check_links.py
	python3 scripts/check_registry.py
	python3 scripts/check_docs.py
	python3 scripts/build_backlog.py --check

# --- schemas -----------------------------------------------------------------------------------
test-schemas:
	cd schemas && $(UV) run --locked $(PY) pytest
lint-schemas:
	cd schemas && $(UV) run --locked $(PY) ruff check tests

# --- tsl ---------------------------------------------------------------------------------------
test-tsl:
	cd tsl && $(UV) run --locked $(PY) pytest -q
lint-tsl:
	cd tsl && $(UV) run --locked $(PY) ruff check . && $(UV) run --locked $(PY) ruff format --check . && $(UV) run --locked $(PY) mypy

# --- plugin and pods ---------------------------------------------------------------------------
test-plugin:
	cd plugins/truminds/tests && $(UV) run --locked $(PY) pytest -q
lint-plugin:
	cd plugins/truminds/tests && $(UV) run --locked $(PY) ruff check .

# --- insights service --------------------------------------------------------------------------
test-insights:
	cd services/insights && $(UV) run --locked $(PY) pytest -q
lint-insights:
	cd services/insights && $(UV) run --locked $(PY) ruff check . && $(UV) run --locked $(PY) ruff format --check . && $(UV) run --locked $(PY) mypy

# --- portal ------------------------------------------------------------------------------------
portal/node_modules:
	cd portal && $(NPM) ci
test-portal: portal/node_modules
	cd portal && $(NPM) test
test-portal-e2e: portal/node_modules
	cd portal && $(NPM) run e2e
lint-portal: portal/node_modules
	cd portal && $(NPM) run lint && $(NPM) run typecheck && $(NPM) run check:tokens && $(NPM) run check:api

# --- sample system -----------------------------------------------------------------------------
examples/sample-system/node_modules:
	cd examples/sample-system && $(NPM) ci
test-sample: examples/sample-system/node_modules
	cd examples/sample-system && $(NPM) test && $(NPM) run canary
lint-sample: examples/sample-system/node_modules
	cd examples/sample-system && $(NPM) run lint && $(NPM) run typecheck

# --- deploy and monitoring (use the insights venv) ---------------------------------------------
services/insights/.venv:
	cd services/insights && $(UV) sync --locked $(PY)
test-deploy-ops: services/insights/.venv
	services/insights/.venv/bin/python -m pytest -q deploy/tests ops/monitoring/tests
lint-deploy-ops: services/insights/.venv
	services/insights/.venv/bin/ruff check --config deploy/ruff.toml deploy
	services/insights/.venv/bin/ruff check --config ops/ruff.toml ops
