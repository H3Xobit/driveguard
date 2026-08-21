PYTHON ?= python3
COMPOSE ?= docker compose
export PYTHONPATH := src

.PHONY: help setup up down simulate test lint demo eval

help:
	@echo "setup up down demo test eval simulate"

setup:
	$(PYTHON) -m pip install -e ".[dev]"

up:
	$(COMPOSE) up -d --build
	@echo "Waiting for API health on :38000 ..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
	  curl -sf http://localhost:38000/health && exit 0; \
	  sleep 4; \
	done; exit 1

down:
	$(COMPOSE) down -v

simulate:
	$(PYTHON) -m driveguard.simulator.session --duration 40 --inject cas_hmw

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src tests

eval:
	$(PYTHON) -m driveguard.eval_harness --smoke 10

demo: up
	@echo "Injecting cas_hmw..."
	curl -sf -X POST "http://localhost:38000/simulate/inject?type=cas_hmw" | $(PYTHON) -m json.tool
	@echo "UI: http://localhost:33000  API: http://localhost:38000/docs"
