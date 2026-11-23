"""Calendário comercial por município a partir dos dados públicos (snapshot em data/public/).

Regras (as mesmas do modelo dbt `dim_calendario_municipal`):
- peso do dia da semana (sábado é meio expediente; domingo não vende);
- feriado nacional, estadual ou MUNICIPAL -> 0;
- véspera de feriado (dia útil) -> antecipação de compras;
- ponte (segunda antes de feriado na terça, sexta depois de feriado na quinta) -> emenda.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sales_planning_analytics.settings import settings


def load_municipios() -> pd.DataFrame:
    return pd.read_csv(settings.public_dir / "municipios.csv")


def load_feriados(mun: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (data, cod_ibge) em que há feriado para aquele município."""
    ne = pd.read_csv(settings.public_dir / "feriados_nacionais_estaduais.csv", parse_dates=["data"])
    fm = pd.read_csv(settings.public_dir / "feriados_municipais.csv", parse_dates=["data"])
    by_uf = ne.merge(mun[["cod_ibge", "uf"]], on="uf")[["data", "cod_ibge", "tipo"]]
    fm = fm[["data", "cod_ibge"]].assign(tipo="MUNICIPAL")
    return pd.concat([by_uf, fm]).drop_duplicates(["data", "cod_ibge"])


def holiday_matrix(days: pd.DatetimeIndex, mun: pd.DataFrame) -> np.ndarray:
    fer = load_feriados(mun)
    fer = fer[fer.data.isin(days)]
    hol = np.zeros((len(days), len(mun)), dtype=bool)
    d_idx = pd.Series(np.arange(len(days)), index=days)
    m_idx = pd.Series(np.arange(len(mun)), index=mun.cod_ibge.values)
    ok = fer.cod_ibge.isin(m_idx.index)
    hol[d_idx[fer.data[ok]].values, m_idx[fer.cod_ibge[ok]].values] = True
    return hol


def day_factor_matrix(days: pd.DatetimeIndex, mun: pd.DataFrame, cal: dict) -> np.ndarray:
    """Matriz dias x municípios com o peso comercial de cada dia."""
    dow = np.asarray(cal["dia_semana"])[days.day_of_week]
    f = np.repeat(dow[:, None], len(mun), axis=1)
    hol = holiday_matrix(days, mun)
    nxt = np.vstack([hol[1:], np.zeros((1, hol.shape[1]), bool)])  # amanhã é feriado
    prv = np.vstack([np.zeros((1, hol.shape[1]), bool), hol[:-1]])  # ontem foi feriado
    wd = days.day_of_week.values[:, None]
    ponte = (((wd == 0) & nxt) | ((wd == 4) & prv)) & ~hol
    vespera = nxt & ~hol & (wd < 5) & ~ponte
    f = np.where(vespera, f * cal["vespera_feriado"], f)
    f = np.where(ponte, f * cal["ponte"], f)
    return np.where(hol, 0.0, f)
