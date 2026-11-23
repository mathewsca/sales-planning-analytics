"""API de previsões e metas.

GET  /health                         -> status e versão do modelo vigente
GET  /forecast/{nivel}               -> previsões P10/P50/P90 (ex.: Total, UF, Coordenador, Representante)
GET  /quota/{cod_representante}      -> metas propostas (todos os métodos) para o mês corrente e o próximo
POST /quota/simulate                 -> recalcula as metas do mês com um método/parâmetro escolhido
POST /reload                         -> limpa o cache (chamado pelo Airflow ao fim do pipeline)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sales_planning_analytics.db import read_sql
from sales_planning_analytics.quotas import methods as Q

app = FastAPI(title="Vendas, metas e campanhas", version="1.0.0")
NIVEIS = {
    "Total",
    "UF",
    "Região intermediária",
    "Região imediata",
    "Coordenador",
    "Supervisor",
    "Representante",
    "Canal",
}


@lru_cache(maxsize=1)
def forecasts() -> pd.DataFrame:
    return read_sql("select unique_id, nivel, ds, h, p10, p50, p90, modelo_versao, cutoff from ml.forecasts")


@lru_cache(maxsize=1)
def proposals() -> pd.DataFrame:
    return read_sql("select * from ml.quota_proposta")


@app.get("/health")
def health() -> dict:
    try:
        f = forecasts()
        return {
            "status": "ok",
            "modelo_versao": str(f.modelo_versao.iloc[0]),
            "cutoff": str(f.cutoff.iloc[0]),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "degradado", "erro": str(exc)[:200]}


@app.get("/forecast/{nivel}")
def forecast(nivel: str, id: str | None = None) -> list[dict]:
    if nivel not in NIVEIS:
        raise HTTPException(404, f"nível inválido; use um de {sorted(NIVEIS)}")
    f = forecasts()
    f = f[f.nivel == nivel]
    if id:
        f = f[f.unique_id.str.split("/").str[-1] == id]
    if f.empty:
        raise HTTPException(404, "sem previsão para esse filtro")
    return f.assign(ds=f.ds.astype(str), cutoff=f.cutoff.astype(str)).to_dict(orient="records")


@app.get("/quota/{cod_representante}")
def quota(cod_representante: int) -> list[dict]:
    p = proposals()
    p = p[p.cod_representante == cod_representante]
    if p.empty:
        raise HTTPException(404, "representante sem meta proposta")
    return p.assign(ds=p.ds.astype(str)).drop(columns=["gerado_em"]).round(4).to_dict(orient="records")


class Simulation(BaseModel):
    metodo: Literal["previsao", "potencial", "probabilidade"]
    parametro: float = Field(
        ..., ge=0, le=1.5, description="previsao: esticamento; potencial: theta; probabilidade: P(atingir)"
    )
    mes: Literal["corrente", "proximo"] = "corrente"


@app.post("/quota/simulate")
def simulate(s: Simulation) -> dict:
    """Recalcula a meta de cada representante a partir da previsão vigente e do desempenho estimado."""
    if s.metodo == "probabilidade" and not 0 < s.parametro < 1:
        raise HTTPException(422, "para 'probabilidade', o parâmetro deve estar entre 0 e 1")
    f = forecasts()
    f = f[(f.nivel == "Representante") & (f.h == (1 if s.mes == "corrente" else 2))].copy()
    f["cod_representante"] = Q.rep_id(f.unique_id)
    if s.metodo == "potencial":
        perf = read_sql(
            "select cod_representante, venda_esperada_territorio, habilidade_est from ml.rep_performance"
        )
        f = f.merge(perf, on="cod_representante")
    f["meta"] = Q.quota(f, s.metodo, s.parametro)
    f["prob_atingir"] = Q.prob_atingir(f.meta, f.p50, Q.sigma(f.p10, f.p50, f.p90))
    return {
        "metodo": s.metodo,
        "parametro": s.parametro,
        "mes": str(f.ds.iloc[0]),
        "meta_total": round(float(f.meta.sum()), 2),
        "previsao_total_p50": round(float(f.p50.sum()), 2),
        "prob_media_atingir": round(float(f.prob_atingir.mean()), 4),
        "metas": f[["cod_representante", "meta", "p50", "prob_atingir"]].round(2).to_dict(orient="records"),
    }


@app.post("/reload")
def reload() -> dict:
    forecasts.cache_clear()
    proposals.cache_clear()
    return {"recarregado": True}
