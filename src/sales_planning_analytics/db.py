"""Acesso ao warehouse PostgreSQL."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from sales_planning_analytics.settings import settings


def utcnow() -> datetime:
    """Carimbo de tempo das cargas (UTC, sem fuso: o Postgres grava como timestamp)."""
    return datetime.now(UTC).replace(tzinfo=None)


@lru_cache(maxsize=1)
def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or settings.database_url, pool_pre_ping=True)


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


def table_exists(name: str) -> bool:
    """`name` no formato schema.tabela (valor interno do código, nunca entrada de usuário)."""
    return bool(read_sql("select to_regclass(:n) is not null as ok", {"n": name}).ok.iloc[0])


def ensure_schema(schema: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(text(f"create schema if not exists {schema}"))


def copy_df(df: pd.DataFrame, table: str, schema: str, mode: str = "replace") -> int:
    """Carga rápida via COPY (ordens de grandeza mais rápido que INSERT em lote).

    mode="replace": TRUNCATE + COPY (preserva a tabela; views do dbt que dependem dela continuam válidas).
    mode="append":  apenas COPY.
    """
    ensure_schema(schema)
    engine = get_engine()
    insp = inspect(engine)
    if insp.has_table(table, schema=schema):
        existing = [c["name"] for c in insp.get_columns(table, schema=schema)]
        if mode == "replace" and set(existing) != set(df.columns):
            # o esquema mudou (ex.: nova coluna de saída do modelo): recria a tabela
            with engine.begin() as conn:
                conn.execute(text(f"drop table {schema}.{table} cascade"))
            df.head(0).to_sql(table, engine, schema=schema, index=False)
        elif mode == "replace":
            with engine.begin() as conn:
                conn.execute(text(f"truncate table {schema}.{table}"))
    else:
        df.head(0).to_sql(table, engine, schema=schema, index=False)
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cols = ", ".join(f'"{c}"' for c in df.columns)
    raw = engine.raw_connection()
    try:
        with (
            raw.cursor() as cur,
            cur.copy(f"COPY {schema}.{table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp,
        ):
            while chunk := buf.read(1 << 20):
                cp.write(chunk)
        raw.commit()
    finally:
        raw.close()
    return len(df)


def append_row(table: str, schema: str = "ml", **fields) -> None:
    """Acrescenta um registro a uma tabela de log (decisões de modelo, monitoramento)."""
    copy_df(pd.DataFrame([fields]), table, schema, mode="append")
