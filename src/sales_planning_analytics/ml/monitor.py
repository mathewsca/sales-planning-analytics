"""Monitoramento: as previsões do ciclo anterior acertaram os meses que acabaram de se realizar?

Sinais (Gama et al., 2014: monitorar o erro é o detector mais direto de concept drift):
  1. WAPE no nível representante vs o WAPE esperado (o do backtest daquele modelo): razão > 1,3;
  2. viés por UF (|soma prevista - soma real| / soma real) > 15%: ruptura regional;
  3. cobertura do intervalo P10-P90 < 60% (alvo 80%);
  4. sem modelo campeão registrado (primeira execução).
Qualquer sinal -> retreino completo (backtest + teste pareado + gate). Senão -> atualização leve
(refit com a configuração campeã e nova previsão), que é barata e mantém as metas em dia.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from sales_planning_analytics.db import append_row, read_sql, table_exists, utcnow
from sales_planning_analytics.ml.metrics import bias, coverage, wape

LIMITES = {"razao_wape": 1.3, "vies_uf": 0.15, "cobertura_min": 0.60}


def run() -> dict:
    now = utcnow()
    out = {"gerado_em": str(now), "retreinar": False, "motivos": []}
    if not table_exists("ml.forecasts_history"):
        out.update(retreinar=True, motivos=["sem modelo em produção (primeira execução)"])
        return _save(out, now)
    hist = read_sql("select * from ml.forecasts_history")
    hist["ds"], hist["cutoff"] = pd.to_datetime(hist.ds), pd.to_datetime(hist.cutoff)
    from sales_planning_analytics.ml import forecast as F

    Y, _, _, _ = F.hierarchy(F.load_panel())  # realizados em todos os níveis da hierarquia
    actual = Y[["unique_id", "ds", "y"]]
    last_obs = actual.ds.max()
    prev = hist[hist.cutoff < last_obs]
    if prev.empty:
        out["motivos"] = ["nenhum mês novo realizado desde a última previsão"]
        return _save(out, now)
    prev = prev[prev.cutoff == prev.cutoff.max()].merge(actual, on=["unique_id", "ds"])
    if prev.empty:
        out["motivos"] = ["nenhum mês novo realizado desde a última previsão"]
        return _save(out, now)
    rep = prev[prev.nivel == "Representante"]
    exp_wape = float(prev.wape_esperado.dropna().iloc[0]) if prev.wape_esperado.notna().any() else np.nan
    obs_wape = wape(rep.y, rep.p50)
    uf = prev[prev.nivel == "UF"].assign(uf=lambda d: d.unique_id.str.split("/").str[-1])
    vies_uf = uf.groupby("uf").apply(lambda d: bias(d.y, d.p50), include_groups=False)
    cov = coverage(rep.y, rep.p10, rep.p90)
    out.update(
        cutoff_avaliado=str(prev.cutoff.max().date()),
        meses_avaliados=sorted({str(d.date()) for d in prev.ds}),
        wape_rep_observado=obs_wape,
        wape_rep_esperado=exp_wape,
        razao_wape=obs_wape / exp_wape if exp_wape else np.nan,
        vies_por_uf=vies_uf.round(4).to_dict(),
        cobertura_p10_p90=cov,
    )
    if exp_wape and obs_wape / exp_wape > LIMITES["razao_wape"]:
        out["motivos"].append(f"WAPE {obs_wape:.3f} > {LIMITES['razao_wape']}x o esperado ({exp_wape:.3f})")
    for u, v in vies_uf.items():
        if abs(v) > LIMITES["vies_uf"]:
            out["motivos"].append(f"viés de {v:+.1%} na UF {u}")
    if cov < LIMITES["cobertura_min"]:
        out["motivos"].append(f"cobertura P10-P90 de {cov:.0%} (< {LIMITES['cobertura_min']:.0%})")
    out["retreinar"] = bool(out["motivos"])
    return _save(out, now)


def _save(out: dict, now) -> dict:
    append_row(
        "monitoring",
        gerado_em=now,
        retreinar=out["retreinar"],
        motivos="; ".join(out["motivos"]),
        detalhe=json.dumps(out, default=str),
    )
    print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    return out
