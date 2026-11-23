"""Previsão hierárquica de vendas mensais com reconciliação MinT e intervalos conformais.

Hierarquia agrupada (grouped):
  geografia: Total -> UF -> região intermediária -> região imediata
  equipe:    Total -> coordenador -> supervisor -> representante
  canal:     Total -> Externo / Interno
  base:      representante x município (IBGE) x canal
Modelos:
  - baselines: média dos últimos 3 meses, regra da catraca (max(ano anterior, média 3m)),
    ingênuo sazonal e ETS (statsforecast);
  - LightGBM global (mlforecast) com defasagens, calendário MUNICIPAL (dias úteis, feriados,
    pontes, vésperas) e campanhas; alvo escalado por série (permite um modelo único p/ todos os níveis),
    no NÍVEL com perda Tweedie. O alvo diferenciado (DIFF_CONFIG) foi testado e recusado pelo gate;
  - reconciliação MinT-shrink (Wickramasuriya et al., 2019): previsões coerentes entre níveis.
Intervalos: conformal "pooled" por nível e horizonte (erros relativos das origens anteriores do
backtest), aplicado sobre a previsão reconciliada: P10/P50/P90.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from hierarchicalforecast.core import HierarchicalReconciliation
from hierarchicalforecast.methods import BottomUp, MinTrace
from lightgbm import LGBMRegressor
from mlforecast import MLForecast
from mlforecast.lag_transforms import RollingMean
from mlforecast.target_transforms import Differences
from statsforecast import StatsForecast
from statsforecast.models import AutoETS, SeasonalNaive

from sales_planning_analytics.db import read_sql

warnings.filterwarnings("ignore", category=FutureWarning)

EXOG = ["dias_uteis", "feriados_municipais", "pontes", "vesperas", "qtd_campanhas"]
SPEC = [
    ["total"],
    ["total", "uf"],
    ["total", "uf", "reg_int"],
    ["total", "uf", "reg_int", "reg_imed"],
    ["total", "coord"],
    ["total", "coord", "sup"],
    ["total", "coord", "sup", "rep"],
    ["total", "canal"],
    ["total", "coord", "sup", "rep", "uf", "reg_int", "reg_imed", "ibge", "canal"],
]
LEVEL_NAMES = {
    "total": "Total",
    "total/uf": "UF",
    "total/uf/reg_int": "Região intermediária",
    "total/uf/reg_int/reg_imed": "Região imediata",
    "total/coord": "Coordenador",
    "total/coord/sup": "Supervisor",
    "total/coord/sup/rep": "Representante",
    "total/canal": "Canal",
    "total/coord/sup/rep/uf/reg_int/reg_imed/ibge/canal": "Base (rep x município x canal)",
}

DEFAULT_CONFIG = {
    "lags": [1, 2, 3, 6, 12],
    "n_estimators": 350,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "target_diff": 0,
    "objective": "tweedie",
    "tweedie_variance_power": 1.2,
}

# Desafiante testado (e RECUSADO pelo gate) para corrigir o viés do campeão: árvores no NÍVEL não
# extrapolam tendência e subestimam uma série que cresce ~6% a.a. (viés de -7% no backtest).
# Com o alvo diferenciado o modelo prevê a VARIAÇÃO mensal (pode ser negativa: perda L2). Corrige o
# viés nos níveis agregados, mas piora o nível representante, onde as metas são definidas.
# Detalhes em docs/model_card.md.
DIFF_CONFIG = {**DEFAULT_CONFIG, "target_diff": 1, "objective": "regression"}


# ---------------------------------------------------------------------------- dados e hierarquia
def load_panel() -> pd.DataFrame:
    df = read_sql("select * from ml.ml_serie_mensal")
    df["ds"] = pd.to_datetime(df.ds)
    return df


def hierarchy(panel: pd.DataFrame):
    """Retorna (Y_hist, X_future, S_df, tags) já agregados em todos os níveis."""
    p = panel.assign(
        total="Total",
        uf=panel.uf,
        reg_int=panel.cod_regiao_intermediaria.astype(str),
        reg_imed=panel.cod_regiao_imediata.astype(str),
        coord=panel.cod_coordenador.astype(str),
        sup=panel.cod_supervisor.astype(str),
        rep=panel.cod_representante.astype(str),
        ibge=panel.cod_ibge.astype(str),
    )
    cols = sorted({c for s in SPEC for c in s})
    p = p[[*cols, "ds", "y", *EXOG]].copy()
    p["y"] = p.y.clip(lower=0)  # devoluções líquidas pontuais não fazem sentido como demanda
    frames, tags = [], {}
    p["_fut"] = p.y.isna()
    for spec in SPEC:
        key = "/".join(spec)
        uid = p[spec[0]].astype(str)
        for c in spec[1:]:
            uid = uid + "/" + p[c].astype(str)
        g = p.assign(unique_id=uid).groupby(["unique_id", "ds"], as_index=False)
        agg = g.agg(y=("y", "sum"), _fut=("_fut", "max"), **{c: (c, "mean") for c in EXOG})
        agg.loc[agg._fut, "y"] = np.nan
        agg = agg.drop(columns="_fut")
        frames.append(agg)
        tags[key] = np.sort(agg.unique_id.unique())
        p[f"_uid_{key}"] = uid
    allp = pd.concat(frames, ignore_index=True)
    Y = allp[allp.y.notna()].reset_index(drop=True)
    Xf = allp[allp.y.isna()].drop(columns="y").reset_index(drop=True)
    # matriz de soma S (linhas: todas as séries; colunas: séries da base)
    bkey = "/".join(SPEC[-1])
    rows_idx = pd.Index(np.concatenate(list(tags.values())))
    cols_idx = pd.Index(tags[bkey])
    links = p.drop_duplicates(f"_uid_{bkey}")
    mat = np.zeros((len(rows_idx), len(cols_idx)))
    for spec in SPEC:
        key = "/".join(spec)
        mat[rows_idx.get_indexer(links[f"_uid_{key}"]), cols_idx.get_indexer(links[f"_uid_{bkey}"])] = 1.0
    S = pd.DataFrame(mat, columns=cols_idx).assign(unique_id=rows_idx.values)
    S = S[["unique_id", *cols_idx]]
    return Y, Xf, S, tags


def level_of(tags: dict) -> pd.Series:
    return pd.Series({uid: LEVEL_NAMES[k] for k, ids in tags.items() for uid in ids}, name="nivel")


# ---------------------------------------------------------------------------- modelos
def simple_baselines(train: pd.DataFrame, h: int) -> pd.DataFrame:
    """Média dos últimos 3 meses e a regra da catraca (como as metas antigas eram feitas)."""
    last = train.ds.max()
    fut = pd.date_range(last + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    piv = train.pivot(index="unique_id", columns="ds", values="y")
    ma3 = piv[piv.columns[-3:]].mean(axis=1)
    rows = []
    for d in fut:
        ly = piv[d - pd.DateOffset(years=1)] if (d - pd.DateOffset(years=1)) in piv.columns else ma3
        rows.append(
            pd.DataFrame(
                {"unique_id": piv.index, "ds": d, "MA3": ma3.values, "Catraca": np.maximum(ma3, ly).values}
            )
        )
    return pd.concat(rows, ignore_index=True)


def stat_baselines(train: pd.DataFrame, h: int, n_jobs: int = 1):
    sf = StatsForecast(
        models=[SeasonalNaive(season_length=12), AutoETS(season_length=12)], freq="MS", n_jobs=n_jobs
    )
    fc = sf.forecast(h=h, df=train[["unique_id", "ds", "y"]], fitted=True)
    fitted = sf.forecast_fitted_values()
    return fc.rename(columns={"SeasonalNaive": "SNaive", "AutoETS": "ETS"}), fitted.rename(
        columns={"SeasonalNaive": "SNaive", "AutoETS": "ETS"}
    )


def lgbm_forecast(train: pd.DataFrame, X_future: pd.DataFrame, h: int, nivel: pd.Series, cfg: dict):
    """LightGBM global no alvo escalado por série (y / média absoluta da série)."""
    scale = train.groupby("unique_id").y.apply(lambda s: s.abs().mean()).clip(lower=1.0).rename("scale")
    codes = {n: i for i, n in enumerate(sorted(LEVEL_NAMES.values()))}
    stat = pd.DataFrame(
        {"scale": scale, "log_scale": np.log(scale), "nivel_cod": nivel.reindex(scale.index).map(codes)}
    )
    tr = train.merge(stat, left_on="unique_id", right_index=True)
    tr["y"] = tr.y / tr.scale
    model = LGBMRegressor(
        n_estimators=cfg["n_estimators"],
        learning_rate=cfg["learning_rate"],
        num_leaves=cfg["num_leaves"],
        min_child_samples=cfg["min_child_samples"],
        subsample=cfg["subsample"],
        subsample_freq=1,
        colsample_bytree=cfg["colsample_bytree"],
        objective=cfg["objective"],
        **(
            {"tweedie_variance_power": cfg["tweedie_variance_power"]} if cfg["objective"] == "tweedie" else {}
        ),
        n_jobs=2,
        deterministic=True,
        force_row_wise=True,
        random_state=7,
        verbose=-1,
    )
    mlf = MLForecast(
        models={"LGBM": model},
        freq="MS",
        lags=cfg["lags"],
        lag_transforms={1: [RollingMean(window_size=3), RollingMean(window_size=12)]},
        date_features=["month"],
        target_transforms=[Differences([cfg["target_diff"]])] if cfg.get("target_diff") else None,
    )
    cols = ["unique_id", "ds", "y", *EXOG, "log_scale", "nivel_cod"]
    mlf.fit(tr[cols], static_features=["log_scale", "nivel_cod"], fitted=True)
    Xf = X_future[X_future.ds <= train.ds.max() + pd.offsets.MonthBegin(h)][["unique_id", "ds", *EXOG]]
    fc = mlf.predict(h=h, X_df=Xf)
    fitted = mlf.forecast_fitted_values()
    for d in (fc, fitted):
        s = d.unique_id.map(scale)
        for c in [c for c in d.columns if c.startswith("LGBM") or c == "y"]:
            d[c] = (d[c] * s).clip(lower=0)
    fitted_model = mlf.models_["LGBM"]
    importance = pd.Series(fitted_model.feature_importances_, index=mlf.ts.features_order_).sort_values(
        ascending=False
    )
    return fc, fitted, fitted_model, importance


def reconcile(base: pd.DataFrame, fitted: pd.DataFrame, S: pd.DataFrame, tags: dict, model: str = "LGBM"):
    """MinT-shrink e Bottom-up sobre a previsão base; desloca o intervalo pela correção do MinT."""
    hrec = HierarchicalReconciliation([BottomUp(), MinTrace(method="mint_shrink", nonnegative=False)])
    rec = hrec.reconcile(
        Y_hat_df=base[["unique_id", "ds", model]],
        Y_df=fitted[["unique_id", "ds", "y", model]],
        S_df=S,
        tags=tags,
    )
    out = base.merge(rec, on=["unique_id", "ds", model], how="left")
    mint = f"{model}/MinTrace_method-mint_shrink"
    out = out.rename(columns={mint: f"{model}_MinT", f"{model}/BottomUp": f"{model}_BU"})
    out[f"{model}_MinT"] = out[f"{model}_MinT"].clip(lower=0)
    return out


def forecast_cycle(
    Y: pd.DataFrame, Xf: pd.DataFrame, S, tags, cutoff: pd.Timestamp, h: int, cfg: dict, stats: bool = True
):
    """Um ciclo completo: treina até `cutoff` (inclusive) e prevê h meses."""
    train = Y[Y.ds <= cutoff].copy()
    fut_exog = pd.concat(
        [Y[Y.ds > cutoff][["unique_id", "ds", *EXOG]], Xf[["unique_id", "ds", *EXOG]]]
    ).drop_duplicates(["unique_id", "ds"])
    nivel = level_of(tags)
    fc, fitted, model, imp = lgbm_forecast(train, fut_exog, h, nivel, cfg)
    out = reconcile(fc, fitted.merge(train[["unique_id", "ds"]], on=["unique_id", "ds"]), S, tags)
    out = out.merge(simple_baselines(train, h), on=["unique_id", "ds"], how="left")
    if stats:
        # baselines estatísticos só nos níveis agregados (do representante para cima): no nível base
        # (1.500+ séries esparsas) o ETS custa ~85% do tempo e não é usado em nenhuma decisão
        agg_ids = nivel.index[nivel != LEVEL_NAMES["/".join(SPEC[-1])]]
        sfc, _ = stat_baselines(train[train.unique_id.isin(agg_ids)], h)
        out = out.merge(sfc, on=["unique_id", "ds"], how="left")
    out["cutoff"] = cutoff
    out["h"] = ((out.ds.dt.year - cutoff.year) * 12 + out.ds.dt.month - cutoff.month).astype(int)
    out["nivel"] = out.unique_id.map(nivel)
    return out, model, imp


# ---------------------------------------------------------------------------- intervalos conformais
def calibrate(bt: pd.DataFrame, model: str = "LGBM_MinT", floor: float = 1.0) -> pd.DataFrame:
    """Quantis do erro relativo (y - yhat) / yhat por nível e horizonte (split conformal pooled)."""
    r = (bt.y - bt[model]) / bt[model].clip(lower=floor)
    q = bt.assign(r=r).groupby(["nivel", "h"]).r.quantile([0.1, 0.9]).unstack()
    return q.rename(columns={0.1: "q10", 0.9: "q90"}).reset_index()


def apply_intervals(fc: pd.DataFrame, calib: pd.DataFrame, model: str = "LGBM_MinT") -> pd.DataFrame:
    out = fc.merge(calib, on=["nivel", "h"], how="left")
    out["p50"] = out[model]
    out["p10"] = (out[model] * (1 + out.q10)).clip(lower=0)
    out["p90"] = (out[model] * (1 + out.q90)).clip(lower=0)
    return out.drop(columns=["q10", "q90"])
