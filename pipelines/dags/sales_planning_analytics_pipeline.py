"""Pipeline de vendas, metas e campanhas (ciclo mensal, com acompanhamento diário do mês corrente).

    extract_public ─┐
    extract_erp ────┴─> ingest_raw -> dbt_build -> monitor_and_decide ─┬─> train_full ───┐
                                                                       └─> refresh_light ─┴─> performance -> quotas
        -> nowcast -> campaigns -> dbt_reporting -> reload_api

- extract_public: IBGE (municípios, população, PIB) e feriados (nacionais, estaduais e municipais).
  Em produção roda 1x/ano; aqui reaproveita o snapshot versionado se a internet falhar.
- monitor_and_decide: compara a previsão do ciclo anterior com os meses que se realizaram; retreino
  completo (backtest + teste pareado + gate champion/challenger) só quando há sinal de degradação.
"""

from __future__ import annotations

import os

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import Param, dag, task

PY = os.getenv("PROJECT_PYTHON", "/opt/project-venv/bin/python")
VENV_BIN = os.path.dirname(PY)
DBT = (
    f"cd /opt/project/dbt && {VENV_BIN}/dbt build --profiles-dir . "
    "--target-path /tmp/dbt/target --log-path /tmp/dbt/logs"
)


@dag(
    dag_id="sales_planning_analytics_pipeline",
    schedule="0 6 * * 1-6",  # diário (seg-sáb): o mês corrente é acompanhado todo dia útil
    start_date=pendulum.datetime(2026, 1, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    tags=["vendas", "metas", "mlops"],
    params={
        "scenario": Param(
            "base",
            enum=["base", "shock"],
            description="'shock' simula retração regional (MT) a partir de dez/2025",
        ),
        "snapshot_date": Param("2026-02-18", type="string", description="'hoje' do warehouse (AAAA-MM-DD)"),
        "force_retrain": Param(False, type="boolean"),
    },
    doc_md=__doc__,
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(seconds=30),
        "retry_exponential_backoff": 2.0,
    },
)
def sales_planning_analytics_pipeline():
    env = {"SNAPSHOT_DATE": "{{ params.snapshot_date }}"}

    extract_public = BashOperator(
        task_id="extract_public",
        bash_command=f"{PY} -m sales_planning_analytics.public.extract || echo 'sem internet: usando o snapshot versionado'",
    )
    extract_erp = BashOperator(
        task_id="extract_erp",
        bash_command=f"{PY} -m sales_planning_analytics.generator.generate --scenario {{{{ params.scenario }}}}",
        doc_md="Simula a extração do ERP (gera os Parquet da landing zone).",
    )

    @task.external_python(python=PY, expect_airflow=False)
    def ingest_raw() -> dict:
        from sales_planning_analytics.ingest import run

        return run()

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT} --exclude tag:reporting",
        env=env,
        append_env=True,
        doc_md="staging -> marts -> ml (features), com todos os testes (anti-vazamento, feriados, chaves).",
    )

    @task.branch_external_python(python=PY, expect_airflow=False)
    def monitor_and_decide(force: str, snapshot: str) -> str:
        import os

        os.environ["SNAPSHOT_DATE"] = snapshot
        from sales_planning_analytics.ml.monitor import run

        r = run()
        return "train_full" if r["retreinar"] or force == "True" else "refresh_light"

    @task.external_python(python=PY, expect_airflow=False)
    def train_full() -> dict:
        from sales_planning_analytics.ml.train import run

        r = run()
        return {"versao": r["versao"], "decisao": r["decision"]}

    @task.external_python(python=PY, expect_airflow=False)
    def refresh_light() -> dict:
        from sales_planning_analytics.ml.train import refresh

        return refresh()

    def step(name: str, trigger_rule: str = "all_success"):
        @task.external_python(task_id=name, python=PY, expect_airflow=False, trigger_rule=trigger_rule)
        def _run(step_name: str, snapshot: str) -> str:
            import json
            import os

            os.environ["SNAPSHOT_DATE"] = snapshot
            from sales_planning_analytics.pipeline import STEPS

            return json.dumps(STEPS[step_name](), default=str)[:2000]

        return _run(name, "{{ params.snapshot_date }}")

    dbt_reporting = BashOperator(
        task_id="dbt_reporting",
        bash_command=f"{DBT} --select tag:reporting",
        env=env,
        append_env=True,
        doc_md="Camada semântica dos dashboards (por público) + teste de consistência de KPIs entre painéis.",
    )
    reload_api = BashOperator(
        task_id="reload_api",
        bash_command="curl -fsS -X POST http://api:8000/reload || echo 'API indisponível (ok se o profile api estiver desligado)'",
    )

    decision = monitor_and_decide(force="{{ params.force_retrain }}", snapshot="{{ params.snapshot_date }}")
    [extract_public, extract_erp] >> ingest_raw() >> dbt_build >> decision
    perf = step("performance", trigger_rule="none_failed_min_one_success")
    decision >> train_full() >> perf
    decision >> refresh_light() >> perf
    perf >> step("quotas") >> step("nowcast") >> step("campaigns") >> dbt_reporting >> reload_api


sales_planning_analytics_pipeline()
