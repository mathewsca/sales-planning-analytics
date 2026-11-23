"""Desempenho da equipe: separar habilidade de território e de sorte.

O ranking por faturamento bruto confunde três coisas: o tamanho/potencial do território, a sorte do
mês e a habilidade do representante. Modelo de efeitos mistos (Gelman & Hill, 2007):

    log(venda_rm) = b0 + b1 log(índice de mercado IBGE da carteira) + b2 log(nº clientes)
                    + b3 composição da carteira (porte) + mês + u_r + e_rm,   u_r ~ N(0, s_u²)

O efeito aleatório u_r (BLUP) é a habilidade estimada: um estimador de shrinkage (Efron & Morris,
1975) que puxa para a média quem tem pouca evidência, evitando premiar sorte.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from sales_planning_analytics.db import read_sql

QUERY = """
with comp as (
    select cod_representante,
           avg((porte = 'Grande')::int) as share_grande,
           avg((porte = 'Medio')::int)  as share_medio
    from marts.dim_cliente group by 1
)
select c.mes, c.cod_representante, c.qtd_carteira, c.indice_mercado_carteira, c.pct_positivacao,
       c.vlr_liquido, k.share_grande, k.share_medio
from marts.mart_carteira_mensal c
join comp k using (cod_representante)
"""


def load() -> pd.DataFrame:
    df = read_sql(QUERY)
    df["mes"] = pd.to_datetime(df.mes)
    return df


def fit(df: pd.DataFrame, cutoff: pd.Timestamp, window: int = 12) -> pd.DataFrame:
    """Ajusta o modelo nos `window` meses até `cutoff` (inclusive) e devolve uma linha por representante."""
    d = df[(df.mes <= cutoff) & (df.mes > cutoff - pd.DateOffset(months=window))].copy()
    d["log_venda"] = np.log1p(d.vlr_liquido.clip(lower=0))
    d["log_indice"] = np.log(d.indice_mercado_carteira.clip(lower=1e-9))
    d["log_carteira"] = np.log(d.qtd_carteira)
    d["mes_c"] = d.mes.dt.strftime("%Y-%m")
    formula = "log_venda ~ log_indice + log_carteira + share_grande + share_medio + C(mes_c)"
    m = smf.mixedlm(formula, d, groups=d.cod_representante).fit(reml=True)
    re = pd.Series({k: float(v.iloc[0]) for k, v in m.random_effects.items()}, name="u")
    # erro-padrão condicional do BLUP: var(u|y) = s_u² * (1 - shrinkage)
    s2u, s2e = float(m.cov_re.iloc[0, 0]), float(m.scale)
    n = d.groupby("cod_representante").size()
    shrink = s2u / (s2u + s2e / n)
    se = np.sqrt(s2u * (1 - shrink))
    fixed = d.assign(u=0.0)
    d["log_esperado"] = m.predict(fixed)  # só efeitos fixos: o que o território "entrega" sozinho
    g = d.groupby("cod_representante").agg(
        venda_media=("vlr_liquido", "mean"),
        venda_esperada_territorio=("log_esperado", lambda s: float(np.expm1(s).mean())),
        pct_positivacao=("pct_positivacao", "mean"),
        indice_mercado_carteira=("indice_mercado_carteira", "first"),
        qtd_carteira=("qtd_carteira", "first"),
    )
    g["habilidade_log"] = re.reindex(g.index)
    g["habilidade_est"] = np.exp(g.habilidade_log)
    g["habilidade_ic_low"] = np.exp(g.habilidade_log - 1.96 * se.reindex(g.index))
    g["habilidade_ic_high"] = np.exp(g.habilidade_log + 1.96 * se.reindex(g.index))
    g["fator_shrinkage"] = shrink.reindex(g.index)
    g["rank_bruto"] = g.venda_media.rank(ascending=False, method="first").astype(int)
    g["rank_ajustado"] = g.habilidade_est.rank(ascending=False, method="first").astype(int)
    g["razao_ingenua"] = g.venda_media / g.indice_mercado_carteira  # "venda por potencial" sem modelo
    g["elasticidade_indice"] = float(m.params["log_indice"])
    g["cutoff"] = cutoff
    return g.reset_index()
