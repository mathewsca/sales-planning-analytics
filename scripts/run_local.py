"""Roda um ciclo completo do pipeline SEM Airflow (mesmas etapas da DAG), contra o Postgres local.

Útil em máquinas modestas: só o container do Postgres precisa estar de pé.
    python scripts/run_local.py [--scenario base|shock] [--snapshot 2026-02-18] [--force-retrain] [--no-mlflow]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# o MLflow imprime emojis; no Windows a saída redirecionada usa cp1252 e quebraria o processo
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
# via módulo, e não o executável dbt(.exe): os launchers do venv guardam o caminho absoluto da pasta
DBT = [PY, "-W", "ignore::RuntimeWarning", "-m", "dbt.cli.main"]


def sh(args: list[str], cwd: Path = ROOT) -> None:
    t = time.time()
    print(f"\n$ {' '.join(args)}", flush=True)
    subprocess.run(args, cwd=cwd, check=True, env=os.environ)
    print(f"  ({time.time() - t:.0f}s)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="base", choices=["base", "shock"])
    ap.add_argument("--snapshot", default="2026-02-18")
    ap.add_argument("--force-retrain", action="store_true")
    ap.add_argument("--no-mlflow", action="store_true")
    ap.add_argument("--skip-extract", action="store_true", help="reaproveita a landing zone já gerada")
    a = ap.parse_args()
    os.environ["SNAPSHOT_DATE"] = a.snapshot

    if not a.skip_extract:
        sh([PY, "-m", "sales_planning_analytics.generator.generate", "--scenario", a.scenario])
        sh([PY, "-m", "sales_planning_analytics.ingest"])
    sh([*DBT, "build", "--profiles-dir", ".", "--exclude", "tag:reporting", "--quiet"], cwd=ROOT / "dbt")

    from sales_planning_analytics.ml import monitor, train
    from sales_planning_analytics.pipeline import STEPS

    decision = monitor.run()
    if decision["retreinar"] or a.force_retrain:
        print("\n>>> retreino completo:", "; ".join(decision["motivos"]) or "forçado", flush=True)
        train.run(log_to_mlflow=not a.no_mlflow)
    else:
        print("\n>>> atualização leve (refit com a configuração campeã)", flush=True)
        train.refresh()
    for step in ["performance", "quotas", "nowcast", "campaigns"]:
        print(f"\n>>> {step}", flush=True)
        STEPS[step]()
    sh([*DBT, "build", "--profiles-dir", ".", "--select", "tag:reporting", "--quiet"], cwd=ROOT / "dbt")
    print("\nciclo concluído.")


if __name__ == "__main__":
    main()
