"""Métricas de previsão (pontuais e probabilísticas) com incerteza quantificada."""

from __future__ import annotations

import numpy as np
import pandas as pd


def wape(y, yhat) -> float:
    """Weighted absolute percentage error: sum|e| / sum|y| (robusto a zeros, legível pelo negócio)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    return float(np.abs(y - yhat).sum() / max(np.abs(y).sum(), 1e-9))


def bias(y, yhat) -> float:
    """Viés relativo: (soma previsto - soma real) / soma real. > 0 = superestima."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    return float((yhat.sum() - y.sum()) / max(np.abs(y).sum(), 1e-9))


def mase_scale(history: pd.DataFrame, season: int = 12) -> pd.Series:
    """Escala do MASE (Hyndman & Koehler, 2006): MAE in-sample do ingênuo sazonal por série.

    Usa a diferença sazonal quando há mais de `season` observações; senão, o ingênuo simples.
    """

    def _scale(s: pd.Series) -> float:
        v = s.to_numpy(float)
        d = np.abs(v[season:] - v[:-season]) if len(v) > season else np.abs(np.diff(v))
        return float(d.mean()) if len(d) and d.mean() > 0 else np.nan

    return history.sort_values("ds").groupby("unique_id").y.apply(_scale)


def mase(df: pd.DataFrame, model: str, scale: pd.Series) -> float:
    """MASE médio entre séries (séries com escala nula ou indefinida são ignoradas)."""
    mae = (df.y - df[model]).abs().groupby(df.unique_id).mean()
    r = (mae / scale.reindex(mae.index)).replace([np.inf, -np.inf], np.nan).dropna()
    return float(r.mean())


def pinball(y, q, tau: float) -> float:
    y, q = np.asarray(y, float), np.asarray(q, float)
    e = y - q
    return float(np.mean(np.maximum(tau * e, (tau - 1) * e)))


def coverage(y, lo, hi) -> float:
    y = np.asarray(y, float)
    return float(((y >= np.asarray(lo)) & (y <= np.asarray(hi))).mean())


def paired_bootstrap_wape(
    df: pd.DataFrame,
    model_a: str,
    model_b: str,
    cluster: str = "unique_id",
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, float]:
    """WAPE(A) - WAPE(B) com IC 95% por bootstrap PAREADO e por cluster (série).

    Reamostrar séries inteiras preserva a correlação temporal dos erros de uma mesma série;
    parear (mesma reamostragem para A e B) remove a variância comum às duas avaliações.
    Diferença negativa = A erra menos que B.
    """
    rng = np.random.default_rng(seed)
    g = df.groupby(cluster)
    abs_a = g.apply(lambda x: (x.y - x[model_a]).abs().sum(), include_groups=False).to_numpy()
    abs_b = g.apply(lambda x: (x.y - x[model_b]).abs().sum(), include_groups=False).to_numpy()
    tot = g.apply(lambda x: x.y.abs().sum(), include_groups=False).to_numpy()
    n = len(tot)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        t = tot[idx].sum()
        diffs[i] = (abs_a[idx].sum() - abs_b[idx].sum()) / t
    point = (abs_a.sum() - abs_b.sum()) / tot.sum()
    return {
        "diff": float(point),
        "ci_low": float(np.percentile(diffs, 2.5)),
        "ci_high": float(np.percentile(diffs, 97.5)),
        "p_a_melhor": float((diffs < 0).mean()),
    }
