"""Efeito causal das campanhas de fornecedores: diferença-em-diferenças escalonado.

Problema: as campanhas são colocadas, de propósito, em SKUs de giro lento. Comparar "SKUs em campanha"
com "SKUs fora de campanha" no mesmo mês mede o viés de seleção, não o efeito (pode até dar negativo).

Estimador (no espírito de Callaway & Sant'Anna, 2021): para cada coorte g = mês da PRIMEIRA campanha
do SKU, compara a variação das vendas do SKU entre o pré-período (média de g-3..g-1) e g+e com a mesma
variação dos SKUs AINDA NÃO TRATADOS em g+e (controles válidos, sem contaminação de tratamentos
anteriores). Em contagens, usamos a razão de razões sobre somas (DiD multiplicativo, equivalente a
um DiD de Poisson), robusta a SKUs com zero venda:

    efeito(g, e) = [T(g+e) / T(pré)] / [C(g+e) / C(pré)] - 1

e = 0 mede o incremento no mês da campanha; e = +1 mede a antecipação (queda no mês seguinte, van
Heerde, Leeflang & Wittink, 2004); e < 0 testa tendências paralelas (deve ser ~ 0).
IC 95% por bootstrap por SKU (cluster).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sales_planning_analytics.db import read_sql

EVENTS = [-3, -2, 0, 1, 2]
PRE = [-3, -2, -1]


def load_panel() -> pd.DataFrame:
    p = read_sql(
        "select cod_produto, mes, qtd, vlr, em_campanha, cod_campanha, primeira_campanha from ml.ml_painel_campanha"
    )
    p["mes"] = pd.to_datetime(p.mes)
    p["primeira_campanha"] = pd.to_datetime(p.primeira_campanha)
    return p


def _wide(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list]:
    Y = panel.pivot(index="cod_produto", columns="mes", values="qtd").sort_index(axis=1)
    first = panel.drop_duplicates("cod_produto").set_index("cod_produto").primeira_campanha.reindex(Y.index)
    return Y, first, list(Y.columns)


def _effect(Y: pd.DataFrame, treated: np.ndarray, control: np.ndarray, pre_cols: list, post_col) -> float:
    t_pre, t_post = Y.loc[treated, pre_cols].to_numpy().mean(axis=1).sum(), Y.loc[treated, post_col].sum()
    c_pre, c_post = Y.loc[control, pre_cols].to_numpy().mean(axis=1).sum(), Y.loc[control, post_col].sum()
    if min(t_pre, c_pre, c_post) <= 0:
        return np.nan
    return float((t_post / t_pre) / (c_post / c_pre) - 1)


def cohort_effects(
    Y: pd.DataFrame, first: pd.Series, months: list, sku_subset: np.ndarray | None = None
) -> pd.DataFrame:
    idx = pd.Series(range(len(months)), index=months)
    rows = []
    for g, members in first.dropna().groupby(first.dropna()):
        gi = idx.get(g)
        if gi is None or gi < 3:
            continue
        treated = members.index.to_numpy()
        if sku_subset is not None:
            treated = np.intersect1d(treated, sku_subset)
        if len(treated) == 0:
            continue
        pre_cols = [months[gi + k] for k in PRE]
        for e in EVENTS:
            if not 0 <= gi + e < len(months):
                continue
            post = months[gi + e]
            ctrl = first.index[(first.isna() | (first > max(post, g))).to_numpy()]
            if sku_subset is not None:
                ctrl = np.intersect1d(ctrl, sku_subset)
            eff = _effect(Y, treated, ctrl, pre_cols, post) if e not in PRE else np.nan
            if e in (-3, -2):  # placebo: variação pré-tratamento contra a média do pré-período
                eff = _effect(Y, treated, ctrl, [months[gi - 1]], post)
            rows.append(
                {"coorte": g, "e": e, "efeito": eff, "n_tratados": len(treated), "n_controles": len(ctrl)}
            )
    return pd.DataFrame(rows)


def event_study(Y, first, months, n_boot: int = 200, seed: int = 0) -> pd.DataFrame:
    def agg(ce: pd.DataFrame) -> pd.Series:
        ce = ce.dropna(subset=["efeito"])
        return ce.groupby("e").apply(
            lambda x: np.average(x.efeito, weights=x.n_tratados), include_groups=False
        )

    point = agg(cohort_effects(Y, first, months))
    rng = np.random.default_rng(seed)
    skus = Y.index.to_numpy()
    boots = []
    for _ in range(n_boot):
        sample = rng.choice(skus, size=len(skus), replace=True)
        Yb = Y.loc[sample].reset_index(drop=True)
        fb = first.loc[sample].reset_index(drop=True)
        boots.append(agg(cohort_effects(Yb, fb, months)))
    B = pd.concat(boots, axis=1)
    return pd.DataFrame(
        {
            "e": point.index,
            "efeito": point.values,
            "ic_low": B.quantile(0.025, axis=1).reindex(point.index).values,
            "ic_high": B.quantile(0.975, axis=1).reindex(point.index).values,
        }
    )


def per_campaign(panel: pd.DataFrame, Y, first, months) -> pd.DataFrame:
    """Efeito no mês da campanha (e=0) por campanha, nos SKUs em sua primeira campanha + estimadores ingênuos."""
    camp = read_sql(
        "select cod_campanha, mes_campanha, tipo, cod_fornecedor, descricao from marts.dim_campanha"
    )
    camp["mes_campanha"] = pd.to_datetime(camp.mes_campanha)
    links = read_sql("select cod_campanha, cod_produto from staging.stg_erp__campanhas_produtos")
    idx = {m: i for i, m in enumerate(months)}
    rows = []
    for c in camp.itertuples():
        gi = idx.get(c.mes_campanha)
        skus = links.cod_produto[links.cod_campanha == c.cod_campanha].to_numpy()
        skus = np.intersect1d(skus, Y.index)
        if gi is None or gi < 3 or len(skus) == 0:
            continue
        g = c.mes_campanha
        first_time = skus[(first.loc[skus] == g).to_numpy()]
        others = Y.index.difference(skus)
        naive_cross = Y.loc[skus, g].mean() / max(Y.loc[others, g].mean(), 1e-9) - 1
        before_after = Y.loc[skus, g].sum() / max(Y.loc[skus, months[gi - 1]].sum(), 1e-9) - 1
        did = np.nan
        if len(first_time):
            ctrl = first.index[(first.isna() | (first > g)).to_numpy()]
            did = _effect(Y, first_time, ctrl, [months[gi + k] for k in PRE], g)
        vlr = panel[(panel.mes == g) & panel.cod_produto.isin(skus)].vlr.sum()
        rows.append(
            {
                "cod_campanha": c.cod_campanha,
                "mes_campanha": g,
                "tipo": c.tipo,
                "cod_fornecedor": c.cod_fornecedor,
                "n_skus": len(skus),
                "n_skus_primeira_vez": len(first_time),
                "efeito_did": did,
                "efeito_ingenuo_transversal": naive_cross,
                "efeito_antes_depois": before_after,
                "vlr_campanha": vlr,
                "vlr_incremental_estimado": vlr * did / (1 + did) if pd.notna(did) and did > -1 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def run() -> dict:
    panel = load_panel()
    Y, first, months = _wide(panel)
    es = event_study(Y, first, months)
    pc = per_campaign(panel, Y, first, months)
    return {"event_study": es, "per_campaign": pc}
