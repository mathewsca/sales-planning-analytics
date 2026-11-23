"""Evidência versionada em reports/: métricas e comparações com o oráculo (nunca vão ao warehouse)."""

from __future__ import annotations

import json

import pandas as pd

from sales_planning_analytics.settings import ROOT

REPORTS_DIR = ROOT / "reports"


def save_json(name: str, payload: dict) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / f"{name}.json").write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False), encoding="utf-8"
    )


def save_csv(name: str, df: pd.DataFrame) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    df.to_csv(REPORTS_DIR / f"{name}.csv", index=False)
