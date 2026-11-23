"""Extração de dados públicos: municípios IBGE, população, PIB e feriados.

Fontes (todas abertas):
- IBGE API de Localidades: código de 7 dígitos, UF, regiões imediata e intermediária.
- IBGE SIDRA (API de agregados v3): tabela 6579 (população estimada) e 5938 (PIB municipal).
- kelvins/Municipios-Brasileiros (MIT): latitude e longitude.
- pacote `holidays`: feriados nacionais e estaduais (com feriados móveis).
- joaopbini/feriados-brasil (MIT): feriados municipais por código IBGE.

O resultado é um snapshot pequeno em data/public/ (versionado no git), para o CI e o
gerador serem reprodutíveis sem internet. `python -m sales_planning_analytics.public.extract`
atualiza o snapshot.
"""

from __future__ import annotations

import io
import json
from datetime import date

import holidays
import pandas as pd
import requests

from sales_planning_analytics.settings import settings

UFS = {"GO": 52, "MT": 51, "MS": 50, "DF": 53, "TO": 17}
YEARS = range(2022, 2027)
IBGE = "https://servicodados.ibge.gov.br/api"
LATLON = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
FERIADOS = (
    "https://raw.githubusercontent.com/joaopbini/feriados-brasil/HEAD/dados/feriados/municipal/csv/{y}.csv"
)
TIMEOUT = 60


def _get(url: str) -> requests.Response:
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "sales-planning-analytics-portfolio"})
    r.raise_for_status()
    return r


def municipios() -> pd.DataFrame:
    rows = []
    for uf_id in UFS.values():
        rows += _get(f"{IBGE}/v1/localidades/estados/{uf_id}/municipios?view=nivelado").json()
    df = pd.DataFrame(rows).rename(
        columns={
            "municipio-id": "cod_ibge",
            "municipio-nome": "municipio",
            "UF-sigla": "uf",
            "regiao-imediata-id": "cod_regiao_imediata",
            "regiao-imediata-nome": "regiao_imediata",
            "regiao-intermediaria-id": "cod_regiao_intermediaria",
            "regiao-intermediaria-nome": "regiao_intermediaria",
        }
    )
    return df[
        [
            "cod_ibge",
            "municipio",
            "uf",
            "cod_regiao_imediata",
            "regiao_imediata",
            "cod_regiao_intermediaria",
            "regiao_intermediaria",
        ]
    ]


def _sidra(tabela: int, variavel: int, periodo: str) -> pd.Series:
    locs = ",".join(str(u) for u in UFS.values())
    url = f"{IBGE}/v3/agregados/{tabela}/periodos/{periodo}/variaveis/{variavel}?localidades=N6[N3[{locs}]]"
    res = _get(url).json()[0]["resultados"][0]["series"]
    return pd.Series(
        {int(s["localidade"]["id"]): pd.to_numeric(s["serie"][periodo], errors="coerce") for s in res}
    )


def indicadores(ano_pop: str = "2025", ano_pib: str = "2023") -> pd.DataFrame:
    pop = _sidra(6579, 9324, ano_pop).rename("populacao")
    pib = (_sidra(5938, 37, ano_pib) * 1000).rename("pib")  # tabela em mil reais
    df = pd.concat([pop, pib], axis=1).rename_axis("cod_ibge").reset_index()
    df["pib_per_capita"] = df.pib / df.populacao
    df["ano_populacao"], df["ano_pib"] = int(ano_pop), int(ano_pib)
    return df


def coordenadas() -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(_get(LATLON).content.decode("utf-8")))
    return df.rename(columns={"codigo_ibge": "cod_ibge"})[["cod_ibge", "latitude", "longitude", "capital"]]


def feriados_nacionais_estaduais() -> pd.DataFrame:
    rows = []
    for uf in UFS:
        for d, nome in holidays.Brazil(subdiv=uf, years=YEARS).items():
            rows.append({"data": d, "uf": uf, "nome": nome})
    df = pd.DataFrame(rows)
    nacionais = set(holidays.Brazil(years=YEARS))
    df["tipo"] = df.data.map(lambda d: "NACIONAL" if d in nacionais else "ESTADUAL")
    return df.sort_values(["data", "uf"]).reset_index(drop=True)


def feriados_municipais(cods: set[int]) -> pd.DataFrame:
    frames = []
    for y in YEARS:
        raw = _get(FERIADOS.format(y=y)).content
        try:
            txt = raw.decode("utf-8")
        except UnicodeDecodeError:
            txt = raw.decode("latin-1")
        df = pd.read_csv(
            io.StringIO(txt), header=None, names=["data", "nome", "tipo", "descricao", "uf", "cod_ibge"]
        )
        frames.append(df)
    df = pd.concat(frames)
    df = df[df.cod_ibge.isin(cods)].copy()
    df["data"] = pd.to_datetime(df.data, format="%d/%m/%Y").dt.date
    return df[["data", "cod_ibge", "uf", "nome"]].drop_duplicates(["data", "cod_ibge"]).reset_index(drop=True)


def impute_pib(mun: pd.DataFrame) -> pd.DataFrame:
    """Municípios recém-criados ainda não têm PIB publicado: PIB per capita = mediana da região imediata."""
    mun = mun.copy()
    mun["pib_imputado"] = mun.pib.isna()
    med = mun.groupby("cod_regiao_imediata").pib_per_capita.transform("median")
    mun["pib_per_capita"] = mun.pib_per_capita.fillna(med)
    mun["pib"] = mun.pib.fillna(mun.pib_per_capita * mun.populacao)
    return mun


def main() -> None:
    out = settings.public_dir
    out.mkdir(parents=True, exist_ok=True)
    mun = (
        municipios()
        .merge(indicadores(), on="cod_ibge", how="left")
        .merge(coordenadas(), on="cod_ibge", how="left")
    )
    mun = impute_pib(mun)
    mun.to_csv(out / "municipios.csv", index=False)
    feriados_nacionais_estaduais().to_csv(out / "feriados_nacionais_estaduais.csv", index=False)
    fm = feriados_municipais(set(mun.cod_ibge))
    fm.to_csv(out / "feriados_municipais.csv", index=False)
    meta = {
        "coletado_em": date.today().isoformat(),
        "ufs": list(UFS),
        "municipios": len(mun),
        "municipios_com_feriado_municipal": int(fm.cod_ibge.nunique()),
        "fontes": {
            "localidades": f"{IBGE}/v1/localidades",
            "populacao": "SIDRA tabela 6579 (população residente estimada)",
            "pib": "SIDRA tabela 5938 (PIB dos municípios, preços correntes)",
            "coordenadas": LATLON,
            "feriados_nacionais_estaduais": "pacote python holidays",
            "feriados_municipais": "github.com/joaopbini/feriados-brasil",
        },
    }
    (out / "_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
