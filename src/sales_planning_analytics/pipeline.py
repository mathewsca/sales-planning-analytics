"""Etapas do pipeline (chamadas pelo Airflow ou localmente: python -m sales_planning_analytics.pipeline <etapa>).

Cada etapa lê do warehouse, grava em `ml.*` e devolve um resumo JSON-serializável.
Comparações com o oráculo (verdade do gerador) vão só para reports/*.json: a verdade nunca entra
no warehouse nem nos dashboards.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from sales_planning_analytics.db import copy_df, read_sql, utcnow
from sales_planning_analytics.reports import save_json
from sales_planning_analytics.settings import settings


def snapshot() -> pd.Timestamp:
    return pd.Timestamp(os.getenv("SNAPSHOT_DATE", "2026-02-18"))


def last_closed_month() -> pd.Timestamp:
    return snapshot().to_period("M").to_timestamp() - pd.DateOffset(months=1)


def _truth(name: str) -> pd.DataFrame | None:
    p = settings.truth_dir / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else None


# ------------------------------------------------------------------------------ desempenho
def step_performance() -> dict:
    from sales_planning_analytics.ml import performance

    cutoff = last_closed_month()
    perf = performance.fit(performance.load(), cutoff)
    copy_df(perf.assign(gerado_em=utcnow()), "rep_performance", "ml")
    out = {"cutoff": cutoff, "elasticidade_indice": float(perf.elasticidade_indice.iloc[0])}
    t = _truth("representantes_true")
    if t is not None:
        j = perf.merge(t.rename(columns={"representante_id": "cod_representante"}), on="cod_representante")
        out["spearman_oraculo"] = {
            c: float(spearmanr(j[c], j.habilidade_true).statistic)
            for c in ["venda_media", "razao_ingenua", "habilidade_est"]
        }
    save_json("performance", out)
    return out


# ------------------------------------------------------------------------------ nowcast
def step_nowcast() -> dict:
    from sales_planning_analytics.ml import nowcast
    from sales_planning_analytics.quotas.methods import prob_atingir

    r = nowcast.run(snapshot())
    ev, nc = r["avaliacao"], r["nowcast"]
    # probabilidade de bater a meta vigente: lognormal centrada no nowcast; dispersão a partir do
    # WAPE do modelo na fase do mês (para erro normal, MAE ~ 0,8 sigma -> sigma ~ 1,25 WAPE)
    try:
        meta = read_sql(
            "select cod_representante, meta as meta_vigente from ml.quota_proposta "
            "where escolhido and ds = date_trunc('month', cast(:d as date))",
            {"d": snapshot().date()},
        )
        nc = nc.merge(meta, on="cod_representante", how="left")
    except Exception:  # noqa: BLE001 - primeira execução, sem metas propostas ainda
        nc["meta_vigente"] = np.nan
    frac = (nc.du_decorridos / nc.du_mes).clip(0, 1)
    fase = np.select([frac <= 0.3, frac <= 0.6], [0, 1], 2)
    sig = np.clip(1.25 * ev.wape_modelo.to_numpy()[fase], 0.02, None)
    nc["prob_atingir_meta"] = prob_atingir(nc.meta_vigente, nc.proj_modelo, sig)
    nc["du_restantes"] = (nc.du_mes - nc.du_decorridos).clip(lower=0)
    nc["venda_necessaria_por_du"] = np.where(
        nc.du_restantes > 0,
        (nc.meta_vigente - nc.vlr_mtd).clip(lower=0) / nc.du_restantes.clip(lower=0.5),
        0.0,
    )
    now = utcnow()
    copy_df(ev.assign(gerado_em=now), "nowcast_eval", "ml")
    copy_df(nc.assign(gerado_em=now), "nowcast", "ml")
    out = {"avaliacao": ev.to_dict(orient="records")}
    save_json("nowcast", out)
    return out


# ------------------------------------------------------------------------------ metas
def step_quotas() -> dict:
    from sales_planning_analytics.quotas import methods as Q

    sim = Q.simulate()
    t = _truth("representantes_true")
    truth = t.rename(columns={"representante_id": "cod_representante"}) if t is not None else None
    summary = Q.summarize(sim, truth)
    chosen = Q.choose(summary)
    summary["escolhido"] = (summary.metodo == chosen.metodo) & np.isclose(summary.parametro, chosen.parametro)
    now = utcnow()
    cols = [
        "cod_representante",
        "ds",
        "metodo",
        "parametro",
        "meta",
        "y",
        "p50",
        "atingimento",
        "premio",
        "venda_esperada_territorio",
    ]
    copy_df(sim[cols].assign(gerado_em=now), "quota_scenarios", "ml")
    copy_df(
        summary.drop(columns=["correlacao_habilidade_oraculo"], errors="ignore").assign(gerado_em=now),
        "quota_summary",
        "ml",
    )

    # proposta para o mês corrente e o próximo: previsão de produção (h=1,2) + desempenho até o
    # último mês fechado (gravado pela etapa `performance`, que roda antes)
    fc = read_sql(
        "select unique_id, ds, h, p10, p50, p90 from ml.forecasts where nivel = 'Representante' and h <= 2"
    )
    fc["cod_representante"] = Q.rep_id(fc.unique_id)
    fc["ds"] = pd.to_datetime(fc.ds)
    perf = read_sql(
        "select cod_representante, venda_esperada_territorio, habilidade_est from ml.rep_performance"
    )
    leg = read_sql("select cod_representante, mes as ds, vlr_meta from marts.mart_metas_legado")
    leg["ds"] = pd.to_datetime(leg.ds)
    prop = pd.concat(
        [
            Q.quotas_for_month(month.assign(y=np.nan), perf, leg[leg.ds == ds])
            for ds, month in fc.groupby("ds")
        ],
        ignore_index=True,
    )
    prop["escolhido"] = (prop.metodo == chosen.metodo) & np.isclose(prop.parametro, chosen.parametro)
    # provisão esperada de premiação (Monte Carlo lognormal sobre a previsão do representante)
    rng = np.random.default_rng(0)
    sig = Q.sigma(prop.p10.to_numpy(), prop.p50.to_numpy(), prop.p90.to_numpy())
    draws = prop.p50.to_numpy()[:, None] * np.exp(sig[:, None] * rng.standard_normal((len(prop), 400)))
    prem = Q.premio(draws, prop.meta.to_numpy()[:, None].repeat(400, axis=1))
    prop["premio_esperado"] = prem.mean(axis=1)
    prop["prob_atingir"] = Q.prob_atingir(prop.meta, prop.p50, sig)
    pcols = [
        "cod_representante",
        "ds",
        "metodo",
        "parametro",
        "meta",
        "p10",
        "p50",
        "p90",
        "prob_atingir",
        "premio_esperado",
        "escolhido",
    ]
    copy_df(prop[pcols].assign(gerado_em=now), "quota_proposta", "ml")
    save_json("quotas", {"escolhido": chosen.to_dict(), "resumo": summary.to_dict(orient="records")})
    return {"escolhido": f"{chosen.metodo} ({chosen.parametro})"}


# ------------------------------------------------------------------------------ campanhas
def step_campaigns() -> dict:
    from sales_planning_analytics.campaigns import effects as E

    r = E.run()
    es, pc = r["event_study"], r["per_campaign"]
    now = utcnow()
    copy_df(es.assign(gerado_em=now), "campaign_event_study", "ml")
    pooled = (
        pc.dropna(subset=["efeito_did"])
        .groupby("tipo")
        .apply(lambda x: np.average(x.efeito_did, weights=x.n_skus_primeira_vez), include_groups=False)
    )
    pc["efeito_planejamento"] = pc.tipo.map(pooled).fillna(float(es.loc[es.e == 0, "efeito"].iloc[0]))
    copy_df(pc.assign(gerado_em=now), "campaign_effects", "ml")
    out = {"event_study": es.to_dict(orient="records"), "efeito_por_tipo": pooled.to_dict()}
    t = _truth("campanhas_true")
    if t is not None:
        j = pc.merge(t.rename(columns={"campanha_id": "cod_campanha"}), on="cod_campanha")
        jj = j.dropna(subset=["efeito_did"])
        out["oraculo"] = {
            "efeito_verdadeiro_medio": float(j.att_ratio_true.mean()),
            "did_agregado_e0": float(es.loc[es.e == 0, "efeito"].iloc[0]),
            "dip_verdadeiro_medio": float(t.dip_true.mean()),
            "did_agregado_e1": float(es.loc[es.e == 1, "efeito"].iloc[0]),
            "ingenuo_transversal_medio": float(j.efeito_ingenuo_transversal.mean()),
            "antes_depois_medio": float(j.efeito_antes_depois.mean()),
            "mae_did_por_campanha": float((jj.efeito_did - jj.att_ratio_true).abs().mean()),
            "mae_antes_depois_por_campanha": float((j.efeito_antes_depois - j.att_ratio_true).abs().mean()),
            "mae_planejamento_por_campanha": float((j.efeito_planejamento - j.att_ratio_true).abs().mean()),
        }
    save_json("campaigns", out)
    return {k: v for k, v in out.items() if k != "event_study"}


STEPS = {
    "performance": step_performance,
    "nowcast": step_nowcast,
    "quotas": step_quotas,
    "campaigns": step_campaigns,
}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(STEPS):
        print(name, json.dumps(STEPS[name](), indent=1, default=str, ensure_ascii=False))
