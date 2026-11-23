"""Ingestão: landing (Parquet do ERP) + snapshot público (IBGE/feriados) -> schema raw do PostgreSQL.

Contratos de dados (pandera) nas tabelas críticas: falha cedo, antes de contaminar o warehouse.
Idempotente (full refresh via TRUNCATE + COPY).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from sales_planning_analytics.db import copy_df, utcnow
from sales_planning_analytics.public.calendar import load_feriados, load_municipios
from sales_planning_analytics.settings import settings

ERP_TABLES = [
    "filiais",
    "coordenadores",
    "supervisores",
    "representantes",
    "vendedores_internos",
    "clientes",
    "fornecedores",
    "produtos",
    "campanhas",
    "campanhas_produtos",
    "metas_mensais",
    "metas_campanha",
    "vendas_itens",
]

VENDAS_SCHEMA = pa.DataFrameSchema(
    {
        "pedido_id": pa.Column(int),
        "data_venda": pa.Column("datetime64[ns]"),
        "cliente_id": pa.Column(int),
        "representante_id": pa.Column(int),
        "interno_id": pa.Column("Int64", nullable=True),
        "produto_id": pa.Column(int),
        "quantidade": pa.Column(int, pa.Check.ne(0)),
        "valor_liquido": pa.Column(float),
    },
    checks=[
        pa.Check(
            lambda d: (np_sign(d.quantidade) == np_sign(d.valor_liquido)).all(), error="sinal qtd != valor"
        ),
    ],
    coerce=True,
)

MUNICIPIOS_SCHEMA = pa.DataFrameSchema(
    {
        "cod_ibge": pa.Column(int, [pa.Check.in_range(1_100_000, 5_399_999)], unique=True),
        "uf": pa.Column(str, pa.Check.str_length(2, 2)),
        "populacao": pa.Column(float, pa.Check.gt(0)),
        "pib_per_capita": pa.Column(float, pa.Check.gt(0)),
        "latitude": pa.Column(float, pa.Check.in_range(-34, 6)),
        "longitude": pa.Column(float, pa.Check.in_range(-74, -34)),
    },
    coerce=True,
)


def np_sign(s: pd.Series) -> pd.Series:
    return (s > 0).astype(int) - (s < 0).astype(int)


def run(landing: Path | None = None) -> dict[str, int]:
    landing = Path(landing or settings.landing_dir)
    loaded_at = utcnow()
    counts = {}
    for name in ERP_TABLES:
        df = pd.read_parquet(landing / f"{name}.parquet")
        if name == "vendas_itens":
            df = VENDAS_SCHEMA.validate(df, lazy=True)
        df["_loaded_at"] = loaded_at
        counts[name] = copy_df(df, name, schema="raw")
        print(f"[ingest] raw.{name:<22} {counts[name]:>10,} linhas")
    mun = MUNICIPIOS_SCHEMA.validate(load_municipios(), lazy=True)
    for name, df in {"ibge_municipios": mun, "feriados": load_feriados(mun)}.items():
        counts[name] = copy_df(df.assign(_loaded_at=loaded_at), name, schema="raw")
        print(f"[ingest] raw.{name:<22} {counts[name]:>10,} linhas")
    return counts


if __name__ == "__main__":
    run()
