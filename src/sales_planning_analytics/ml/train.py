"""Backtest (origem móvel), seleção com teste pareado, MLflow e previsão de produção.

Protocolo (decidido ANTES de ver o resultado):
  1. Origens mensais móveis nos últimos N meses; horizonte h = 1..3.
  2. Métrica principal: WAPE no nível REPRESENTANTE, h = 1 (é o nível e o prazo em que as metas são definidas).
  3. O LightGBM reconciliado só é aceito se superar o melhor baseline com IC 95% do bootstrap pareado < 0.
  4. Intervalos P10-P90: conformal pooled calibrado APENAS com origens anteriores (sem olhar o futuro).
  5. Gate champion/challenger: o desafiante não pode piorar o WAPE do campeão em mais de 10%.
  6. Primeiro ciclo (nenhuma previsão em produção): um modelo recusado é publicado como PROVISÓRIO,
     sem virar campeão, para metas, nowcast e dashboards não ficarem sem previsão. A partir do
     segundo ciclo, um recusado nunca é publicado.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from sales_planning_analytics.db import append_row, copy_df, read_sql, table_exists, utcnow
from sales_planning_analytics.ml import forecast as F
from sales_planning_analytics.ml.metrics import (
    bias,
    coverage,
    mase,
    mase_scale,
    paired_bootstrap_wape,
    pinball,
    wape,
)
from sales_planning_analytics.reports import save_csv, save_json
from sales_planning_analytics.settings import settings

MODELS = ["LGBM_MinT", "LGBM", "LGBM_BU", "MA3", "Catraca", "SNaive", "ETS"]
BASELINES = ["MA3", "Catraca", "SNaive", "ETS"]
KEY_LEVELS = [
    "Total",
    "UF",
    "Coordenador",
    "Supervisor",
    "Representante",
    "Canal",
    "Base (rep x município x canal)",
]


def backtest(Y, Xf, S, tags, origins: list[pd.Timestamp], cfg: dict, h: int = 3) -> pd.DataFrame:
    last = Y.ds.max()
    frames = []
    for i, cutoff in enumerate(origins):
        t = time.time()
        hh = min(h, (last.year - cutoff.year) * 12 + last.month - cutoff.month)
        out, _, _ = F.forecast_cycle(Y, Xf, S, tags, cutoff, hh, cfg)
        frames.append(out)
        print(
            f"[backtest] origem {cutoff:%Y-%m} ({i + 1}/{len(origins)}) h={hh} em {time.time() - t:.0f}s",
            flush=True,
        )
    bt = pd.concat(frames, ignore_index=True).merge(Y[["unique_id", "ds", "y"]], on=["unique_id", "ds"])
    # intervalos sequenciais: cada origem é calibrada só com as origens anteriores
    parts = []
    for k, cutoff in enumerate(origins):
        cur = bt[bt.cutoff == cutoff]
        prev = bt[(bt.cutoff < cutoff) & (bt.ds <= cutoff)]  # erros já observados na data do corte
        if k >= 2 and len(prev):
            cur = F.apply_intervals(cur, F.calibrate(prev))
        else:
            cur = cur.assign(p50=cur.LGBM_MinT, p10=np.nan, p90=np.nan)
        parts.append(cur)
    return pd.concat(parts, ignore_index=True)


def evaluate(bt: pd.DataFrame, Y: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    scale = mase_scale(Y[Y.ds <= bt.cutoff.min()])  # escala só com dados anteriores ao 1º corte
    for lv in KEY_LEVELS:
        for hh in sorted(bt.h.unique()):
            e = bt[(bt.nivel == lv) & (bt.h == hh)]
            if e.empty:
                continue
            r = {"nivel": lv, "h": int(hh), "n": len(e)}
            for m in MODELS:
                r[f"wape_{m}"] = wape(e.y, e[m])
                r[f"mase_{m}"] = mase(e, m, scale)
            r["vies_LGBM_MinT"] = bias(e.y, e.LGBM_MinT)
            ci = e.dropna(subset=["p10", "p90"])
            r["cobertura_p10_p90"] = coverage(ci.y, ci.p10, ci.p90) if len(ci) else np.nan
            r["pinball_p10"] = pinball(ci.y, ci.p10, 0.1) if len(ci) else np.nan
            r["pinball_p90"] = pinball(ci.y, ci.p90, 0.9) if len(ci) else np.nan
            rows.append(r)
    table = pd.DataFrame(rows)

    rep1 = bt[(bt.nivel == "Representante") & (bt.h == 1)]
    best_base = min(BASELINES, key=lambda m: wape(rep1.y, rep1[m]))
    tests = {m: paired_bootstrap_wape(rep1, "LGBM_MinT", m) for m in BASELINES}
    summary = {
        "wape_rep_h1": {m: wape(rep1.y, rep1[m]) for m in MODELS},
        "melhor_baseline": best_base,
        "teste_pareado_vs_baselines": tests,
        "aceito_vs_baseline": tests[best_base]["ci_high"] < 0,
        "cobertura_p10_p90_rep": float(table.query("nivel == 'Representante'").cobertura_p10_p90.mean()),
        "origens": [str(c.date()) for c in sorted(bt.cutoff.unique())],
    }
    return table, summary


def _mlflow():
    import mlflow

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.experiment_name)
    return mlflow


def champion_wape() -> float | None:
    try:
        mlflow = _mlflow()
        client = mlflow.MlflowClient()
        mv = client.get_model_version_by_alias(settings.model_name, "champion")
        return float(client.get_run(mv.run_id).data.metrics["wape_rep_h1"])
    except Exception:  # noqa: BLE001 - sem campeão (primeira execução) ou MLflow indisponível
        return None


def publish_forecast(fc: pd.DataFrame, cutoff, version: str, wape_esperado: float, now) -> None:
    """Grava a previsão vigente (ml.forecasts) e acumula o histórico usado pelo monitoramento."""
    out = fc[["unique_id", "nivel", "ds", "h", "p10", "p50", "p90"]].assign(
        cutoff=cutoff, modelo_versao=version, gerado_em=now
    )
    copy_df(out, "forecasts", "ml")
    keep = out[out.nivel.isin(["Total", "UF", "Coordenador", "Representante"])].assign(
        wape_esperado=wape_esperado
    )
    copy_df(keep, "forecasts_history", "ml", mode="append")


def refresh(cfg: dict | None = None) -> dict:
    """Atualização leve (sem retreino completo): refit com a configuração campeã e nova previsão,
    com os intervalos da última calibração."""
    cfg = cfg or F.DEFAULT_CONFIG
    calib = read_sql("select nivel, h, q10, q90, wape_esperado, modelo_versao from ml.forecast_calibration")
    Y, Xf, S, tags = F.hierarchy(F.load_panel())
    last = Y.ds.max()
    fc, _, _ = F.forecast_cycle(Y, Xf, S, tags, last, 3, cfg, stats=False)
    fc = F.apply_intervals(fc, calib[["nivel", "h", "q10", "q90"]])
    now = utcnow()
    version = str(calib.modelo_versao.iloc[0])
    publish_forecast(fc, last, version, float(calib.wape_esperado.iloc[0]), now)
    append_row(
        "model_decisions",
        gerado_em=now,
        modelo_versao=version,
        tipo="atualizacao",
        detalhe=json.dumps({"cutoff": str(last.date())}),
    )
    return {"versao": version, "cutoff": str(last.date())}


def run(n_origins: int = 8, log_to_mlflow: bool = True, cfg: dict | None = None) -> dict:
    cfg = cfg or F.DEFAULT_CONFIG
    t0 = time.time()
    panel = F.load_panel()
    Y, Xf, S, tags = F.hierarchy(panel)
    last = Y.ds.max()
    origins = [last - pd.DateOffset(months=k) for k in range(n_origins, 0, -1)]
    bt = backtest(Y, Xf, S, tags, origins, cfg)
    table, summary = evaluate(bt, Y)

    # previsão de produção: treina com tudo até o snapshot e prevê os próximos 3 meses
    fc, model, importance = F.forecast_cycle(Y, Xf, S, tags, last, 3, cfg, stats=False)
    calib = F.calibrate(bt)
    fc = F.apply_intervals(fc, calib)
    now = utcnow()

    decision = {
        "aceito_vs_baseline": summary["aceito_vs_baseline"],
        "wape": summary["wape_rep_h1"]["LGBM_MinT"],
    }
    champ = champion_wape() if log_to_mlflow else None
    decision["wape_campeao"] = champ
    decision["promovido"] = bool(
        summary["aceito_vs_baseline"] and (champ is None or decision["wape"] <= champ * 1.10)
    )
    # sem nenhuma previsão em produção não há campeão para manter: publica como provisório
    decision["provisorio"] = not decision["promovido"] and not table_exists("ml.forecasts")
    version = "local"
    if log_to_mlflow:
        version = log_run(cfg, summary, table, importance, model, bt, decision)
    out = {"summary": summary, "decision": decision, "versao": version, "segundos": round(time.time() - t0)}
    append_row(
        "model_decisions", gerado_em=now, modelo_versao=version, tipo="treino", detalhe=json.dumps(decision)
    )

    if decision["provisorio"]:
        print(">>> recusado pelo gate, mas não há previsão em produção: publicado como provisório")
    elif not decision["promovido"]:
        # desafiante recusado: só registra a decisão. Previsões, calibração e backtest de produção
        # continuam sendo os do campeão (metas, nowcast e dashboards não mudam).
        save_json("challenger_metrics", out)
        save_csv("challenger_backtest_table", table)
        print(">>> desafiante recusado pelo gate; produção mantém o campeão")
        print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
        return out

    copy_df(
        calib.assign(wape_esperado=decision["wape"], modelo_versao=version, gerado_em=now),
        "forecast_calibration",
        "ml",
    )
    publish_forecast(fc, last, version, decision["wape"], now)
    bt_out = bt[["unique_id", "nivel", "cutoff", "ds", "h", "y", *MODELS, "p10", "p90"]]
    copy_df(bt_out.assign(modelo_versao=version), "backtest", "ml")
    copy_df(table.assign(modelo_versao=version, gerado_em=now), "backtest_metrics", "ml")
    save_json("forecast_metrics", out)
    save_csv("forecast_backtest_table", table)
    print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    return out


def log_run(cfg, summary, table, importance, model, bt, decision) -> str:
    mlflow = _mlflow()
    from mlflow.models import infer_signature

    with mlflow.start_run(run_name="lgbm-mint") as r:
        mlflow.log_params(cfg)
        mlflow.log_metric("wape_rep_h1", summary["wape_rep_h1"]["LGBM_MinT"])
        for m, v in summary["wape_rep_h1"].items():
            mlflow.log_metric(f"wape_rep_h1_{m}", v)
        mlflow.log_metric("cobertura_p10_p90_rep", summary["cobertura_p10_p90_rep"])
        mlflow.log_dict(summary, "summary.json")
        mlflow.log_text(table.to_csv(index=False), "backtest_table.csv")
        mlflow.log_text(importance.to_csv(), "feature_importance.csv")
        X = pd.DataFrame(np.zeros((1, len(importance))), columns=list(importance.sort_index().index))
        mlflow.lightgbm.log_model(
            model.booster_,
            name="model",
            signature=infer_signature(X),
            registered_model_name=settings.model_name,
        )
        client = mlflow.MlflowClient()
        ver = max(int(v.version) for v in client.search_model_versions(f"run_id='{r.info.run_id}'"))
        client.set_model_version_tag(settings.model_name, str(ver), "promovido", str(decision["promovido"]))
        client.set_registered_model_alias(settings.model_name, "challenger", str(ver))
        if decision["promovido"]:
            client.set_registered_model_alias(settings.model_name, "champion", str(ver))
        return f"v{ver}"


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--origins", type=int, default=8)
    ap.add_argument("--no-mlflow", action="store_true")
    a = ap.parse_args()
    run(a.origins, log_to_mlflow=not a.no_mlflow)
