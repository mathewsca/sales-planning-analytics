from __future__ import annotations

import pandas as pd
import pytest
import yaml

from sales_planning_analytics.settings import settings


@pytest.fixture(scope="session")
def cfg() -> dict:
    return yaml.safe_load(settings.generator_config.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def small_world(cfg):
    """Mundo sintético pequeno (5% da escala), gerado uma vez por sessão de testes."""
    from sales_planning_analytics.generator.generate import Generator

    g = Generator(cfg, "base", scale=0.05)
    tables = g.run()
    return g, tables


@pytest.fixture
def toy_panel() -> pd.DataFrame:
    """Painel mínimo com o formato de ml.ml_serie_mensal (2 reps, 2 municípios, 2 canais)."""
    rows = []
    for rep, sup, coord, ibge, imed, rint, uf in [
        (1, 10, 100, 5200050, 520001, 5201, "GO"),
        (2, 10, 100, 5300108, 530001, 5301, "DF"),
    ]:
        for canal in ["Externo", "Interno"]:
            for i, ds in enumerate(pd.date_range("2024-01-01", periods=18, freq="MS")):
                rows.append(
                    {
                        "cod_representante": rep,
                        "cod_supervisor": sup,
                        "cod_coordenador": coord,
                        "cod_ibge": ibge,
                        "cod_regiao_imediata": imed,
                        "cod_regiao_intermediaria": rint,
                        "uf": uf,
                        "canal": canal,
                        "ds": ds,
                        "y": None
                        if i >= 16
                        else float(100 * rep + 10 * i + (5 if canal == "Interno" else 0)),
                        "dias_uteis": 22.0,
                        "feriados_municipais": 0,
                        "pontes": 0,
                        "vesperas": 1,
                        "qtd_campanhas": 4,
                    }
                )
    return pd.DataFrame(rows)
