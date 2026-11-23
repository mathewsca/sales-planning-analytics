"""Nowcast intramensal: projeção do fechamento do mês a partir do acumulado (MTD).

Compara três regras para "quanto vamos fechar este mês?":
  1. Tendência legada (DAX do Power BI): acumulado / dias úteis decorridos x dias úteis do mês,
     com calendário que só conhece feriados NACIONAIS;
  2. Tendência com calendário MUNICIPAL (feriados estaduais e municipais da carteira);
  3. Modelo (LightGBM): combina o acumulado com a previsão de início de mês (média recente),
     dando mais peso ao histórico no começo do mês, quando o acumulado ainda é ruidoso.
Avaliação temporal: treina em meses anteriores, testa nos últimos meses completos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from sales_planning_analytics.db import read_sql
from sales_planning_analytics.ml.metrics import wape

FEATURES = ["frac_du", "dia_mes", "mes_ano", "r_linear", "r_legado", "log_prior"]


def load() -> pd.DataFrame:
    d = read_sql("select * from ml.ml_nowcast_diario")
    d["data"], d["mes"] = pd.to_datetime(d.data), pd.to_datetime(d.mes)
    return d


def build(d: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    current = snapshot.to_period("M").to_timestamp()
    month_tot = (
        d[d.mes < current].groupby(["cod_representante", "mes"]).vlr_dia.sum().rename("vlr_mes_fechado")
    )
    prior = (
        month_tot.groupby(level=0)
        .transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
        .rename("prior")
    )
    # prior do mês corrente = média dos 3 últimos meses fechados
    cur_prior = month_tot.groupby(level=0).apply(lambda s: s.tail(3).mean())
    cur_prior.index = pd.MultiIndex.from_arrays(
        [cur_prior.index, [current] * len(cur_prior)], names=["cod_representante", "mes"]
    )
    prior = pd.concat([prior, cur_prior.rename("prior")])
    x = d.merge(prior.reset_index(), on=["cod_representante", "mes"], how="left")
    x = x[(x.du_decorridos > 0) & x.prior.notna() & (x.prior > 0)].copy()
    x["frac_du"] = x.du_decorridos / x.du_mes
    x["dia_mes"] = x.data.dt.day
    x["mes_ano"] = x.mes.dt.month
    x["proj_linear"] = x.vlr_mtd / x.du_decorridos * x.du_mes
    x["proj_legado"] = x.vlr_mtd / x.du_decorridos_legado.clip(lower=0.5) * x.du_mes_legado
    x["r_linear"] = x.proj_linear / x.prior
    x["r_legado"] = x.proj_legado / x.prior
    x["log_prior"] = np.log(x.prior)
    x["completo"] = x.mes < current
    return x


def model() -> LGBMRegressor:
    return LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=50,
        objective="l1",
        n_jobs=2,
        deterministic=True,
        force_row_wise=True,
        random_state=7,
        verbose=-1,
    )


def evaluate(x: pd.DataFrame, test_months: int = 6) -> tuple[pd.DataFrame, LGBMRegressor]:
    full = x[x.completo]
    months = sorted(full.mes.unique())
    test_start = months[-test_months]
    tr, te = full[full.mes < test_start], full[full.mes >= test_start].copy()
    m = model().fit(tr[FEATURES], tr.vlr_mes / tr.prior)
    te["proj_modelo"] = m.predict(te[FEATURES]) * te.prior
    rows = []
    te["feriado_municipal_no_mes"] = (te.du_mes_legado - te.du_mes) >= 0.5  # calendários divergem
    fases = [
        (0.0, 0.3, "início (até 30% dos dias úteis)"),
        (0.3, 0.6, "meio (30-60%)"),
        (0.6, 0.95, "fim (60-95%)"),
    ]
    for lo, hi, nome in [*fases, (0.0, 0.95, "meses COM feriado estadual/municipal")]:
        e = te[(te.frac_du > lo) & (te.frac_du <= hi)]
        if nome.startswith("meses COM"):
            e = e[e.feriado_municipal_no_mes]
        rows.append(
            {
                "fase_do_mes": nome,
                "n": len(e),
                "wape_tendencia_legado": wape(e.vlr_mes, e.proj_legado),
                "wape_tendencia_municipal": wape(e.vlr_mes, e.proj_linear),
                "wape_media_3m": wape(e.vlr_mes, e.prior),
                "wape_modelo": wape(e.vlr_mes, e.proj_modelo),
            }
        )
    return pd.DataFrame(rows), m


def run(snapshot: pd.Timestamp) -> dict:
    x = build(load(), snapshot)
    table, _ = evaluate(x)
    full = x[x.completo]
    m = model().fit(full[FEATURES], full.vlr_mes / full.prior)
    cur = x[~x.completo]
    cur = cur[cur.data == cur.data.max()].copy()  # último dia disponível do mês corrente
    cur["proj_modelo"] = m.predict(cur[FEATURES]) * cur.prior
    out = cur[
        [
            "cod_representante",
            "data",
            "mes",
            "vlr_mtd",
            "du_decorridos",
            "du_mes",
            "du_mes_legado",
            "prior",
            "proj_legado",
            "proj_linear",
            "proj_modelo",
        ]
    ]
    return {"avaliacao": table, "nowcast": out}
