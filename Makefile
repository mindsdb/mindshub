FRONTEND := frontend
API      := backend/core_api
AGENT    := backend/core_agent

_NPM_STAMP := $(FRONTEND)/node_modules/.package-lock.json
_API_STAMP  := $(API)/.venv
_AGENT_STAMP := $(AGENT)/.venv

.PHONY: setup dev dev-web build dist-mac dist-win

$(_NPM_STAMP): $(FRONTEND)/package-lock.json
	npm --prefix $(FRONTEND) ci

$(_API_STAMP): $(API)/uv.lock
	uv sync --directory $(API)

$(_AGENT_STAMP): $(AGENT)/uv.lock
	uv sync --directory $(AGENT)

setup: $(_NPM_STAMP) $(_API_STAMP) $(_AGENT_STAMP)

dev: $(_NPM_STAMP) $(_API_STAMP) $(_AGENT_STAMP)
	@trap 'kill 0' SIGINT SIGTERM EXIT; \
	uv run --directory $(API) uvicorn cowork.server:app --reload \
		--reload-dir $(API)/cowork \
		--reload-dir $(AGENT)/anton & \
	npm --prefix $(FRONTEND) run dev

dev-web: $(_NPM_STAMP) $(_API_STAMP) $(_AGENT_STAMP)
	@trap 'kill 0' SIGINT SIGTERM EXIT; \
	uv run --directory $(API) uvicorn cowork.server:app --reload \
		--reload-dir $(API)/cowork \
		--reload-dir $(AGENT)/anton & \
	cd $(FRONTEND) && BUILD_TARGET=web npm run dev:renderer -- --open

build: $(_NPM_STAMP)
	npm --prefix $(FRONTEND) run build

dist-mac: $(_NPM_STAMP)
	npm --prefix $(FRONTEND) run dist:mac

dist-win: $(_NPM_STAMP)
	npm --prefix $(FRONTEND) run dist:win
