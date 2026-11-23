.DEFAULT_GOAL := help
COMPOSE := docker compose
# Windows (Git Bash + make) usa Scripts/; Linux/macOS usam bin/
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
else
PY := .venv/bin/python
endif
# interpretador do `make setup` (ex.: make setup PYTHON="py -3.12")
PYTHON ?= python3.12

help: ## Lista os comandos
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- subida POR PARTES (máquinas com pouca memória) -------------------------------------------
db: ## 1) Só o Postgres (~250 MB)
	$(COMPOSE) up -d postgres

ml: ## 2) + MLflow (registry de modelos)
	$(COMPOSE) --profile ml up -d

orchestration: ## 3) + Airflow (DAG completa); desligue o BI antes em máquinas com < 8 GB
	$(COMPOSE) --profile orchestration up -d --build

bi: ## 4) + Superset (dashboards por público, RBAC e RLS); importa os dashboards no 1º start
	$(COMPOSE) --profile bi up -d --build

api: ## + FastAPI (/forecast, /quota, /quota/simulate)
	$(COMPOSE) --profile api up -d --build

stop-orchestration: ## Desliga o Airflow (libera ~2 GB) mantendo o resto
	$(COMPOSE) stop airflow

down: ## Derruba a stack (mantém volumes)
	$(COMPOSE) --profile ml --profile orchestration --profile api --profile bi down

reset: ## Derruba tudo e apaga volumes (banco, artefatos)
	$(COMPOSE) --profile ml --profile orchestration --profile api --profile bi down -v

# --- pipeline ---------------------------------------------------------------------------------
pipeline: ## Ciclo completo via Airflow
	$(COMPOSE) exec -T airflow airflow dags trigger sales_planning_analytics_pipeline

local: ## Ciclo completo SEM Airflow (só o Postgres precisa estar de pé)
	$(PY) scripts/run_local.py

shock-demo: ## Demonstração de drift: ciclo em nov/2025, depois fev/2026 com retração no MT
	$(PY) scripts/run_local.py --snapshot 2025-11-18
	$(PY) scripts/run_local.py --snapshot 2026-02-18 --scenario shock

challenger: ## Treina o desafiante com alvo diferenciado (DIFF_CONFIG); o gate decide se promove
	$(PY) -c "from sales_planning_analytics.ml import forecast as F, train; train.run(cfg=F.DIFF_CONFIG)"

public-data: ## Atualiza o snapshot de dados públicos (IBGE + feriados)
	$(PY) -m sales_planning_analytics.public.extract

dbt-docs: ## Documentação e linhagem do dbt
	cd dbt && ../$(PY) -m dbt.cli.main docs generate --profiles-dir .

# --- qualidade --------------------------------------------------------------------------------
setup: ## Ambiente local (Python 3.12)
	$(PYTHON) -m venv .venv && $(PY) -m pip install -e ".[api,dbt,dev]" && $(PY) -m pre_commit install

test: ## Testes unitários
	$(PY) -m pytest

lint: ## Lint e formatação
	$(PY) -m ruff check . && $(PY) -m ruff format --check .

screenshots: ## Prints dos dashboards (Superset de pé em :8088)
	$(PY) scripts/screenshots.py
