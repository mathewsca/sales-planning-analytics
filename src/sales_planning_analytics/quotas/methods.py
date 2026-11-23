"""Métodos de definição de metas mensais por representante, comparados por simulação.

Para cada mês do backtest, a meta é definida com a informação disponível no fim do mês anterior
(previsão h=1 e desempenho estimado até o corte) e confrontada com o realizado.

Métodos:
  legado      (1+g) * max(mesmo mês do ano anterior, média 3m)  -> efeito catraca (Weitzman, 1980)
  previsao    P50 da previsão reconciliada, escalada para a meta da empresa
  potencial   venda esperada do TERRITÓRIO (IBGE + carteira) x habilidade^theta, escalada para a meta da
              empresa (Zoltners, Sinha & Lorimer, 2006; Mantrala, Sinha & Zoltners, 1994)
  probabilidade  quantil da previsão probabilística com P(atingir) = alvo

Critérios: atingimento (mediana, % que bate), dispersão, JUSTIÇA (correlação de Spearman entre o
atingimento e o potencial do território ~ 0) e custo do plano de premiação.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

from sales_planning_analytics.db import read_sql
from sales_planning_analytics.ml import performance

PLANO = {"comissao_bonus": 0.03, "acelerador": 0.02, "teto_atingimento": 1.5}
GRID = {
    "previsao": [0.0, 0.05, 0.10],  # esticamento da meta da empresa sobre a previsão
    "potencial": [0.0, 0.5, 1.0],  # theta: quanto da habilidade comprovada entra na meta
    "probabilidade": [0.5, 0.6, 0.7],  # probabilidade-alvo de bater a meta
}
STRETCH_EMPRESA = 0.05


def premio(real: np.ndarray, meta: np.ndarray) -> np.ndarray:
    """Plano ilustrativo: 3% da venda ao bater a meta + 2% sobre o excedente (atingimento até 150%)."""
    att = np.where(meta > 0, real / meta, 0)
    bate = att >= 1
    excedente = np.clip(real - meta, 0, (PLANO["teto_atingimento"] - 1) * meta)
    return np.where(bate, PLANO["comissao_bonus"] * real + PLANO["acelerador"] * excedente, 0.0)


def rep_id(uid: pd.Series) -> pd.Series:
    return uid.str.split("/").str[-1].astype("int64")


def load_inputs():
    bt = read_sql(
        'select unique_id, cutoff, ds, y, "LGBM_MinT" as p50, p10, p90 from ml.backtest '
        "where nivel = 'Representante' and h = 1"
    )
    bt["cod_representante"] = rep_id(bt.unique_id)
    bt["ds"], bt["cutoff"] = pd.to_datetime(bt.ds), pd.to_datetime(bt.cutoff)
    leg = read_sql("select cod_representante, mes as ds, vlr_meta from marts.mart_metas_legado")
    leg["ds"] = pd.to_datetime(leg.ds)
    return bt, leg


def sigma(p10, p50, p90):
    """Desvio na escala log a partir de P10/P90 (aproximação lognormal)."""
    lo = np.log(np.clip(p50, 1, None) / np.clip(p10, 1, None))
    hi = np.log(np.clip(p90, 1, None) / np.clip(p50, 1, None))
    return np.clip((lo + hi) / (2 * norm.ppf(0.9)), 0.02, 2.0)


def prob_atingir(meta, centro, sig):
    """P(venda >= meta) com venda lognormal de mediana `centro` e desvio log `sig`."""
    return 1 - norm.cdf(np.log(np.clip(meta, 1, None) / np.clip(centro, 1, None)) / sig)


def quota(d: pd.DataFrame, metodo: str, parametro: float) -> pd.Series:
    """Meta de cada representante por um método (o legado vem pronto do ERP).

    `d` tem uma linha por representante com p10/p50/p90; o método 'potencial' também usa
    venda_esperada_territorio e habilidade_est.
    """
    if metodo == "previsao":
        return d.p50 * (1 + parametro)
    if metodo == "probabilidade":
        return d.p50 * np.exp(norm.ppf(1 - parametro) * sigma(d.p10, d.p50, d.p90))
    if metodo == "potencial":
        base = d.venda_esperada_territorio * d.habilidade_est**parametro
        return base * ((1 + STRETCH_EMPRESA) * d.p50.sum()) / base.sum()
    raise ValueError(f"método desconhecido: {metodo}")


def quotas_for_month(month_bt: pd.DataFrame, perf: pd.DataFrame, legado: pd.DataFrame) -> pd.DataFrame:
    d = month_bt.merge(
        perf[["cod_representante", "venda_esperada_territorio", "habilidade_est"]], on="cod_representante"
    )
    d = d.merge(legado[["cod_representante", "vlr_meta"]], on="cod_representante", how="left")
    rows = [d.assign(metodo="legado", parametro=0.0, meta=d.vlr_meta)]
    rows += [d.assign(metodo=m, parametro=p, meta=quota(d, m, p)) for m, ps in GRID.items() for p in ps]
    out = pd.concat(rows, ignore_index=True).dropna(subset=["meta"])
    out = out[out.meta > 0]
    out["atingimento"] = out.y / out.meta
    out["premio"] = premio(out.y.to_numpy(), out.meta.to_numpy())
    return out


def simulate() -> pd.DataFrame:
    bt, leg = load_inputs()
    perf_df = performance.load()
    frames = []
    for ds, month in bt.groupby("ds"):
        cutoff = month.cutoff.iloc[0]
        perf = performance.fit(perf_df, cutoff)
        frames.append(quotas_for_month(month, perf, leg[leg.ds == ds]))
    return pd.concat(frames, ignore_index=True)


def summarize(sim: pd.DataFrame, truth: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    for (m, p), g in sim.groupby(["metodo", "parametro"]):
        att = g.atingimento.clip(upper=3)
        just = np.mean(
            [spearmanr(x.atingimento, x.venda_esperada_territorio).statistic for _, x in g.groupby("ds")]
        )
        r = {
            "metodo": m,
            "parametro": p,
            "meses": g.ds.nunique(),
            "atingimento_mediano": float(att.median()),
            "pct_bate_meta": float((g.atingimento >= 1).mean()),
            "dispersao_iqr": float(att.quantile(0.75) - att.quantile(0.25)),
            "correlacao_territorio": float(just),
            "custo_premio_pct_venda": float(g.premio.sum() / g.y.sum()),
            "meta_sobre_previsao": float(g.meta.sum() / g.p50.sum()),
        }
        if truth is not None:
            t = g.merge(truth, on="cod_representante")
            r["correlacao_habilidade_oraculo"] = float(
                np.mean([spearmanr(x.atingimento, x.habilidade_true).statistic for _, x in t.groupby("ds")])
            )
        rows.append(r)
    return pd.DataFrame(rows)


def choose(summary: pd.DataFrame) -> pd.Series:
    """Política: entre os métodos com 40-70% de representantes batendo a meta (atingível, mas
    desafiadora), escolher o mais JUSTO (|correlação com o território| mínima); empate -> menor custo."""
    ok = summary[summary.pct_bate_meta.between(0.4, 0.7)].copy()
    if ok.empty:
        ok = summary.copy()
    ok["abs_corr"] = ok.correlacao_territorio.abs().round(2)
    return ok.sort_values(["abs_corr", "custo_premio_pct_venda"]).iloc[0]
