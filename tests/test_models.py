import numpy as np
import pandas as pd
import pytest

from sales_planning_analytics.campaigns.effects import _effect
from sales_planning_analytics.ml import forecast as F
from sales_planning_analytics.ml.metrics import bias, coverage, paired_bootstrap_wape, pinball, wape
from sales_planning_analytics.quotas.methods import premio, prob_atingir, quotas_for_month, sigma


def test_wape_e_vies():
    y = np.array([100, 200, 0])
    assert wape(y, y) == 0
    assert wape(y, np.array([110, 190, 0])) == pytest.approx(20 / 300)
    assert bias(y, y * 1.1) == pytest.approx(0.1)


def test_pinball_e_cobertura():
    y = np.array([1.0, 2.0, 3.0])
    assert pinball(y, y, 0.9) == 0
    assert coverage(y, y - 1, y + 1) == 1.0


def test_bootstrap_pareado_detecta_modelo_melhor():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"unique_id": np.repeat(np.arange(60), 5), "y": rng.uniform(50, 150, 300)})
    df["bom"] = df.y + rng.normal(0, 5, 300)
    df["ruim"] = df.y + rng.normal(0, 30, 300)
    r = paired_bootstrap_wape(df, "bom", "ruim", n_boot=300)
    assert r["diff"] < 0 and r["ci_high"] < 0


def test_hierarquia_soma_coerente(toy_panel):
    Y, Xf, S, tags = F.hierarchy(toy_panel)
    bottom = tags["/".join(F.SPEC[-1])]
    assert len(bottom) == 4
    yb = Y[Y.unique_id.isin(bottom)].pivot(index="unique_id", columns="ds", values="y").loc[bottom]
    Smat = S.set_index("unique_id")[bottom]
    total = Y[Y.unique_id == "Total"].set_index("ds").y
    assert np.allclose(Smat.loc["Total"].to_numpy() @ yb.to_numpy(), total.loc[yb.columns].to_numpy())
    assert Xf.ds.nunique() == 2  # meses futuros com exógenas, sem alvo


def test_alvo_diferenciado_continua_a_tendencia(toy_panel):
    """Árvores no NÍVEL não extrapolam: preveriam no máximo o maior valor já visto. Com o alvo
    diferenciado, a previsão de uma série crescente precisa continuar a tendência."""
    Y, Xf, S, tags = F.hierarchy(toy_panel)
    cutoff = Y.ds.max()
    out, _, _ = F.forecast_cycle(Y, Xf, S, tags, cutoff, 1, F.DIFF_CONFIG, stats=False)
    total = Y[Y.unique_id == "Total"].set_index("ds").y
    passo = total.diff().iloc[-1]  # +40 por mês no painel de teste
    previsto = out[out.unique_id == "Total"].LGBM_MinT.iloc[0]
    # o modelo antigo (nível + Tweedie) previa ~+5: só 12% do passo
    assert previsto >= total.iloc[-1] + 0.75 * passo


def test_premio_so_paga_quem_bate_e_respeita_teto():
    real, meta = np.array([90.0, 100.0, 200.0]), np.array([100.0, 100.0, 100.0])
    p = premio(real, meta)
    assert p[0] == 0
    assert p[1] == pytest.approx(3.0)
    assert p[2] == pytest.approx(0.03 * 200 + 0.02 * 50)  # excedente limitado a 150%


def test_metas_por_potencial_somam_a_meta_da_empresa():
    month = pd.DataFrame(
        {
            "cod_representante": [1, 2, 3],
            "y": [np.nan] * 3,
            "p50": [100.0, 200.0, 300.0],
            "p10": [80.0, 160.0, 240.0],
            "p90": [120.0, 240.0, 360.0],
        }
    )
    perf = pd.DataFrame(
        {
            "cod_representante": [1, 2, 3],
            "venda_esperada_territorio": [1.0, 2.0, 3.0],
            "habilidade_est": [1.0, 1.0, 1.0],
        }
    )
    leg = pd.DataFrame({"cod_representante": [1, 2, 3], "vlr_meta": [120.0, 220.0, 330.0]})
    q = quotas_for_month(month, perf, leg)
    pot = q[(q.metodo == "potencial") & (q.parametro == 0.0)]
    assert pot.meta.sum() == pytest.approx(1.05 * 600)
    prob = q[(q.metodo == "probabilidade") & (q.parametro == 0.5)]
    assert np.allclose(prob.meta, month.p50)  # P(atingir)=50% -> meta = mediana


def test_sigma_lognormal_positivo():
    s = sigma(np.array([80.0]), np.array([100.0]), np.array([125.0]))
    assert 0.1 < s[0] < 0.3


def test_prob_atingir_meta_na_mediana_e_50_pct():
    p = prob_atingir(np.array([100.0, 50.0, 200.0]), np.array([100.0, 100.0, 100.0]), 0.2)
    assert p[0] == pytest.approx(0.5)
    assert p[1] > 0.99 and p[2] < 0.01


def test_did_multiplicativo_recupera_efeito_conhecido():
    rng = np.random.default_rng(1)
    months = pd.date_range("2024-01-01", periods=6, freq="MS")
    base = rng.uniform(20, 80, 200)
    Y = pd.DataFrame(np.outer(base, np.ones(6)) * np.array([1, 1.1, 0.9, 1.0, 1.05, 1.0]), columns=months)
    treated, control = np.arange(100), np.arange(100, 200)
    Y.loc[treated, months[3]] *= 1.30  # efeito verdadeiro de +30% no mês 3
    eff = _effect(Y, treated, control, list(months[:3]), months[3])
    assert eff == pytest.approx(0.30, abs=1e-6)
