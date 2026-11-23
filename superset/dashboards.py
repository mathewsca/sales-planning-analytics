"""Especificação dos dashboards (dashboards como código).

Um dashboard por público (Eckerson, 2010: operacional, tático, estratégico). Todos leem da mesma
camada semântica (marts dbt); as métricas são definidas UMA vez, no dataset, e reutilizadas.
"""

BRL = ",.0f"
PCT = ".1%"


def m(expr: str, label: str, fmt: str = BRL):
    return (expr, label, fmt)


# --------------------------------------------------------------------------- datasets + métricas
DATASETS = {
    "vmc": {
        "schema": "marts",
        "table": "rpt_vendas_mes_corrente",
        "metrics": {
            "meta": m("SUM(meta_vigente)", "Meta do mês (R$)"),
            "realizado": m("SUM(realizado_mtd)", "Realizado no mês (R$)"),
            "pct_meta": m("SUM(realizado_mtd) / NULLIF(SUM(meta_vigente), 0)", "% da meta", PCT),
            "projecao": m("SUM(projecao_fechamento)", "Projeção de fechamento (R$)"),
            "pct_projetado": m(
                "SUM(projecao_fechamento) / NULLIF(SUM(meta_vigente), 0)", "% da meta projetado", PCT
            ),
            "necessario_du": m("SUM(venda_necessaria_por_du)", "Venda necessária por dia útil (R$)"),
            "prob": m("AVG(prob_atingir_meta)", "Probabilidade de bater a meta", ".0%"),
            "positivacao": m(
                "SUM(qtd_positivados)::float / NULLIF(SUM(qtd_carteira), 0)", "Positivação da carteira", PCT
            ),
            "reps_risco": m(
                "SUM(CASE WHEN status_meta = '3 - Em risco' THEN 1 ELSE 0 END)",
                "Representantes em risco",
                ",d",
            ),
            "reps": m("COUNT(*)", "Representantes", ",d"),
        },
        "labels": {
            "nome_representante": "Representante",
            "nome_supervisor": "Supervisor",
            "nome_coordenador": "Coordenador",
            "status_meta": "Status",
        },
    },
    "vmd": {
        "schema": "marts",
        "table": "rpt_vendas_meta_diaria",
        "dttm": ["data"],
        "metrics": {
            "meta_acum": m("SUM(meta_acumulada)", "Meta acumulada (R$)"),
            "real_acum": m("SUM(realizado_acumulado)", "Realizado acumulado (R$)"),
            "meta_dia": m("SUM(meta_dia)", "Meta do dia (R$)"),
            "real_dia": m("SUM(realizado_dia)", "Realizado no dia (R$)"),
        },
    },
    "cli": {
        "schema": "marts",
        "table": "rpt_vendas_clientes_prioridade",
        "metrics": {
            "valor_esperado": m("SUM(valor_esperado)", "Valor esperado (R$)"),
            "clientes": m("COUNT(*)", "Clientes", ",d"),
        },
        "labels": {
            "razao_social": "Cliente",
            "compra_media_mensal_6m": "Compra média/mês (6m)",
            "dias_sem_compra": "Dias sem comprar",
        },
    },
    "camp": {
        "schema": "marts",
        "table": "rpt_campanhas_mes",
        "metrics": {
            "meta_prop": m("SUM(meta_proposta)", "Meta proposta"),
            "meta_leg": m("SUM(meta_legado)", "Meta legada (x1,30)"),
            "realizado": m("SUM(realizado)", "Realizado"),
            "pct": m("SUM(realizado) / NULLIF(SUM(meta_proposta), 0)", "% da meta proposta", PCT),
        },
        "labels": {"descricao": "Campanha", "tipo_descricao": "Tipo"},
    },
    "hist": {
        "schema": "marts",
        "table": "rpt_gestao_historico",
        "dttm": ["mes"],
        "metrics": {
            "realizado": m("SUM(realizado)", "Realizado (R$)"),
            "ating_leg": m(
                "SUM(realizado) FILTER (WHERE meta_legado IS NOT NULL) / NULLIF(SUM(meta_legado), 0)",
                "Atingimento da meta legada",
                PCT,
            ),
            "pct_bate_leg": m(
                "AVG(CASE WHEN realizado >= meta_legado THEN 1.0 ELSE 0 END) FILTER (WHERE meta_legado IS NOT NULL)",
                "% que bateu a meta legada",
                PCT,
            ),
            "positivacao": m(
                "SUM(qtd_positivados)::float / NULLIF(SUM(qtd_carteira), 0)", "Positivação", PCT
            ),
        },
    },
    "met": {
        "schema": "marts",
        "table": "rpt_metodos_meta",
        "metrics": {
            "pct_bate": m("AVG(pct_bate_meta)", "% que bate a meta", PCT),
            "injustica": m("AVG(injustica_territorial)", "Injustiça territorial |ρ|", ".2f"),
            "custo": m("AVG(custo_premio_pct_venda)", "Custo do prêmio (% da venda)", ".2%"),
            "provisao": m("SUM(provisao_mes_corrente)", "Provisão de prêmio no mês (R$)"),
        },
        "labels": {
            "metodo_descricao": "Método",
            "pct_bate_meta": "% bate a meta",
            "atingimento_mediano": "Atingimento mediano",
            "injustica_territorial": "Injustiça territorial",
            "custo_premio_pct_venda": "Custo prêmio % venda",
            "escolhido": "Escolhido",
        },
    },
    "opo": {
        "schema": "marts",
        "table": "mart_oportunidade_municipio",
        "metrics": {
            "vlr": m("SUM(vlr_12m)", "Venda 12 meses (R$)"),
            "indice": m("SUM(indice_mercado)", "Índice de mercado IBGE", ".4f"),
            "nao_atendidos": m(
                "SUM(CASE WHEN NOT atendido THEN 1 ELSE 0 END)", "Municípios não atendidos", ",d"
            ),
            "pop_nao_atendida": m(
                "SUM(CASE WHEN NOT atendido THEN populacao ELSE 0 END)", "População não atendida", ",d"
            ),
            "potencial": m("MAX(indice_mercado) * 1e6", "Potencial (índice x 1e6)", ",.0f"),
        },
        "labels": {"municipio": "Município", "indice_penetracao": "Penetração (1 = na média)"},
    },
    "prev": {
        "schema": "marts",
        "table": "rpt_previsao_empresa",
        "dttm": ["mes"],
        "metrics": {
            "realizado": m("SUM(realizado)", "Realizado"),
            "p10": m("SUM(previsao_p10)", "Previsão P10"),
            "p50": m("SUM(previsao_p50)", "Previsão P50"),
            "p90": m("SUM(previsao_p90)", "Previsão P90"),
            "meta_leg": m("SUM(meta_legado)", "Meta legada (soma)"),
            "meta_nova": m("SUM(meta_metodo_escolhido)", "Meta pelo método escolhido"),
            "ano_anterior": m("SUM(realizado_ano_anterior)", "Mesmo mês do ano anterior"),
        },
    },
    "dir": {
        "schema": "marts",
        "table": "rpt_diretoria_mensal",
        "dttm": ["mes"],
        "metrics": {
            "realizado": m("SUM(realizado)", "Realizado (R$)"),
            "crescimento": m(
                "SUM(realizado) / NULLIF(SUM(realizado_ano_anterior), 0) - 1",
                "Crescimento vs ano anterior",
                PCT,
            ),
        },
        "labels": {"regiao_intermediaria": "Região intermediária (IBGE)"},
    },
    "ret": {
        "schema": "marts",
        "table": "rpt_campanhas_retorno",
        "dttm": ["mes_campanha"],
        "metrics": {
            "faturado": m("SUM(faturado_campanha)", "Faturado nos SKUs da campanha"),
            "incremental": m("SUM(receita_incremental)", "Receita incremental (causal)"),
            "pct_incremental": m(
                "SUM(receita_incremental) / NULLIF(SUM(faturado_campanha), 0)",
                "% do faturado que é incremental",
                PCT,
            ),
        },
        "labels": {
            "nome_fornecedor": "Fornecedor",
            "efeito_causal": "Efeito causal (DiD)",
            "leitura_ingenua_vs_outros_skus": "Leitura ingênua",
        },
    },
    "fin": {
        "schema": "marts",
        "table": "rpt_financeiro_mensal",
        "dttm": ["mes"],
        "metrics": {
            "bruto": m("SUM(faturamento_bruto)", "Faturamento bruto"),
            "devolucoes": m("SUM(devolucoes)", "Devoluções"),
            "liquido": m("SUM(faturamento_liquido)", "Faturamento líquido"),
            "pct_dev": m("SUM(devolucoes) / NULLIF(SUM(faturamento_bruto), 0)", "% de devolução", ".2%"),
        },
        "labels": {"nome_filial": "Filial"},
    },
    "btm": {
        "schema": "ml",
        "table": "backtest_metrics",
        "metrics": {
            "wape_lgbm": m('AVG("wape_LGBM_MinT")', "LightGBM + MinT", ".3f"),
            "wape_ma3": m('AVG("wape_MA3")', "Média 3 meses", ".3f"),
            "wape_catraca": m('AVG("wape_Catraca")', "Catraca (regra antiga)", ".3f"),
            "wape_snaive": m('AVG("wape_SNaive")', "Sazonal ingênuo", ".3f"),
            "wape_ets": m('AVG("wape_ETS")', "ETS", ".3f"),
            "cobertura": m("AVG(cobertura_p10_p90)", "Cobertura P10-P90 (alvo 80%)", ".0%"),
        },
    },
    "es": {
        "schema": "ml",
        "table": "campaign_event_study",
        "metrics": {
            "efeito": m("AVG(efeito)", "Efeito estimado", PCT),
            "ic_low": m("AVG(ic_low)", "IC 2,5%", PCT),
            "ic_high": m("AVG(ic_high)", "IC 97,5%", PCT),
        },
    },
    "nce": {"schema": "ml", "table": "nowcast_eval", "metrics": {}},
    "dec": {"schema": "ml", "table": "model_decisions", "metrics": {}},
}

ROLES = {
    "Vendas": ["vmc", "vmd", "cli", "camp"],
    "Gestao": ["vmc", "hist", "met", "opo", "camp"],
    "Diretoria": ["prev", "dir", "ret", "met"],
    "Financeiro": ["prev", "fin", "met", "ret"],
    "Dados": ["btm", "es", "nce", "dec"],
}


# --------------------------------------------------------------------------- tipos de gráfico
def big(name, ds, metric, sub, fmt=BRL, filters=None):
    return {
        "name": name,
        "dataset": ds,
        "viz": "big_number_total",
        "params": {
            "metric": metric,
            "subheader": sub,
            "y_axis_format": fmt,
            "header_font_size": 0.35,
            "subheader_font_size": 0.13,
            "adhoc_filters": filters or [],
        },
    }


def line(name, ds, x, metrics, grain="P1M", fmt="SMART_NUMBER", groupby=None, filters=None, desc=""):
    return {
        "name": name,
        "dataset": ds,
        "viz": "echarts_timeseries_line",
        "desc": desc,
        "params": {
            "x_axis": x,
            "time_grain_sqla": grain,
            "metrics": metrics,
            "groupby": groupby or [],
            "adhoc_filters": filters or [],
            "row_limit": 10000,
            "show_legend": True,
            "legendOrientation": "top",
            "rich_tooltip": True,
            "y_axis_format": fmt,
            "x_axis_time_format": "smart_date",
            "markerEnabled": False,
            "truncateYAxis": False,
            "zoomable": False,
        },
    }


def bar(
    name,
    ds,
    x,
    metrics,
    fmt="SMART_NUMBER",
    groupby=None,
    horizontal=False,
    stack=False,
    filters=None,
    grain=None,
    desc="",
):
    p = {
        "x_axis": x,
        "metrics": metrics,
        "groupby": groupby or [],
        "adhoc_filters": filters or [],
        "row_limit": 1000,
        "orientation": "horizontal" if horizontal else "vertical",
        "show_legend": True,
        "legendOrientation": "top",
        "rich_tooltip": True,
        "y_axis_format": fmt,
        "stack": "Stack" if stack else None,
        "show_value": False,
    }
    if grain:
        p["time_grain_sqla"] = grain
    return {"name": name, "dataset": ds, "viz": "echarts_timeseries_bar", "params": p, "desc": desc}


def table(
    name,
    ds,
    columns=None,
    metrics=None,
    groupby=None,
    order=None,
    limit=100,
    filters=None,
    cond=None,
    fmt=None,
):
    raw = metrics is None
    p = {
        "query_mode": "raw" if raw else "aggregate",
        "all_columns": columns or [],
        "groupby": groupby or [],
        "metrics": metrics or [],
        "row_limit": limit,
        "server_page_length": 15,
        "adhoc_filters": filters or [],
        "table_timestamp_format": "%d/%m/%Y",
        "show_cell_bars": True,
        "include_search": True,
        "conditional_formatting": cond or [],
        "column_config": {c: {"d3NumberFormat": f} for c, f in (fmt or {}).items()},
    }
    if order:
        if raw:
            p["order_by_cols"] = [f'["{c}", {str(asc).lower()}]' for c, asc in order]
        else:
            p["timeseries_limit_metric"], p["order_desc"] = order[0][0], not order[0][1]
    return {"name": name, "dataset": ds, "viz": "table", "params": p}


def sql_filter(expr):
    return {"expressionType": "SQL", "sqlExpression": expr, "clause": "WHERE"}


def scatter_map(name, ds):
    return {
        "name": name,
        "dataset": ds,
        "viz": "deck_scatter",
        "params": {
            "spatial": {"type": "latlong", "latCol": "latitude", "lonCol": "longitude"},
            "point_radius_fixed": {"type": "metric", "value": "potencial"},
            "point_unit": "pixels",
            "min_radius": 2,
            "max_radius": 22,
            "multiplier": 1,
            "dimension": "situacao",
            "mapbox_style": "tile://https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "viewport": {"latitude": -15.0, "longitude": -51.5, "zoom": 4.4, "bearing": 0, "pitch": 0},
            "row_limit": 5000,
            "adhoc_filters": [],
            "js_columns": ["municipio", "uf"],
        },
    }


def c(name, w, h=50):
    return {"chart": name, "w": w, "h": h}


STATUS_COLORS = [
    {"column": "prob_atingir_meta", "operator": "<", "targetValue": 0.4, "colorScheme": "#d03b3b"},
    {"column": "prob_atingir_meta", "operator": "≥", "targetValue": 0.7, "colorScheme": "#0ca30c"},
]
# cores de status reservadas (as mesmas de superset_config.STATUS): fixas por rótulo em todos os
# dashboards, para um gráfico agrupado por status nunca usar a paleta das séries
STATUS_LABEL_COLORS = {"1 - No ritmo": "#0ca30c", "2 - Atenção": "#fab219", "3 - Em risco": "#d03b3b"}

# --------------------------------------------------------------------------- dashboards
VENDAS = {
    "title": "Vendas · Minha meta do mês",
    "slug": "vendas",
    "roles": ["Vendas"],
    "filters": [{"name": "Representante", "dataset": "vmc", "column": "nome_representante"}],
    "charts": [
        big("Meta do mês", "vmc", "meta", "R$ · método vigente"),
        big("Realizado no mês", "vmc", "realizado", "R$ · líquido até hoje"),
        big("% da meta", "vmc", "pct_meta", "realizado ÷ meta", PCT),
        big("Venda necessária por dia útil", "vmc", "necessario_du", "R$ · com feriados do município"),
        big("Projeção de fechamento", "vmc", "projecao", "R$ · nowcast do modelo"),
        big("Chance de bater a meta", "vmc", "prob", "probabilidade estimada", ".0%"),
        line(
            "Meta acumulada x realizado acumulado",
            "vmd",
            "data",
            ["meta_acum", "real_acum"],
            grain="P1D",
            fmt=",.0f",
            desc="Meta diária distribuída pelos dias úteis do município (sábado = meio dia; feriados municipais = 0)",
        ),
        table(
            "Clientes para visitar hoje (ainda não compraram no mês)",
            "cli",
            columns=[
                "prioridade",
                "razao_social",
                "municipio",
                "porte",
                "compra_media_mensal_6m",
                "dias_sem_compra",
                "valor_esperado",
            ],
            order=[("valor_esperado", False)],
            limit=200,
            fmt={"compra_media_mensal_6m": BRL, "valor_esperado": BRL},
        ),
        table(
            "Campanhas do mês",
            "camp",
            groupby=["descricao", "tipo_descricao"],
            metrics=["meta_prop", "realizado", "pct"],
            order=[("pct", True)],
        ),
    ],
    "rows": [
        [
            c("Meta do mês", 2, 28),
            c("Realizado no mês", 2, 28),
            c("% da meta", 2, 28),
            c("Venda necessária por dia útil", 2, 28),
            c("Projeção de fechamento", 2, 28),
            c("Chance de bater a meta", 2, 28),
        ],
        [c("Meta acumulada x realizado acumulado", 12, 60)],
        [c("Clientes para visitar hoje (ainda não compraram no mês)", 7, 70), c("Campanhas do mês", 5, 70)],
    ],
}

GESTAO = {
    "title": "Gestão · Equipe e metas",
    "slug": "gestao",
    "roles": ["Gestao"],
    "filters": [
        {"name": "Coordenador", "dataset": "vmc", "column": "nome_coordenador"},
        {"name": "Supervisor", "dataset": "vmc", "column": "nome_supervisor"},
    ],
    "charts": [
        big("Representantes em risco", "vmc", "reps_risco", "chance de bater a meta < 40%", ",d"),
        big("% da meta projetado (equipe)", "vmc", "pct_projetado", "projeção de fechamento ÷ meta", PCT),
        big("Positivação da carteira no mês", "vmc", "positivacao", "clientes que compraram ÷ carteira", PCT),
        table(
            "Situação da equipe no mês",
            "vmc",
            columns=[
                "nome_representante",
                "nome_supervisor",
                "meta_vigente",
                "realizado_mtd",
                "projecao_fechamento",
                "prob_atingir_meta",
                "status_meta",
                "pct_positivacao",
                "rank_ajustado",
                "rank_bruto",
            ],
            order=[("prob_atingir_meta", True)],
            limit=300,
            cond=STATUS_COLORS,
            fmt={
                "meta_vigente": BRL,
                "realizado_mtd": BRL,
                "projecao_fechamento": BRL,
                "prob_atingir_meta": ".0%",
                "pct_positivacao": ".0%",
            },
        ),
        bar(
            "Status da meta por supervisor",
            "vmc",
            "nome_supervisor",
            ["reps"],
            fmt=",d",
            groupby=["status_meta"],
            stack=True,
            horizontal=True,
        ),
        line(
            "Atingimento da meta legada (catraca) ao longo do tempo",
            "hist",
            "mes",
            ["ating_leg", "pct_bate_leg"],
            fmt=PCT,
            desc="A regra antiga (+10% sobre o máximo entre o ano anterior e a média de 3 meses) mantém a equipe abaixo de 100%",
        ),
        line("Positivação da carteira ao longo do tempo", "hist", "mes", ["positivacao"], fmt=PCT),
        table(
            "Métodos de meta: justiça x atingibilidade x custo",
            "met",
            columns=[
                "metodo_descricao",
                "pct_bate_meta",
                "atingimento_mediano",
                "injustica_territorial",
                "custo_premio_pct_venda",
                "vigente",
            ],
            order=[("injustica_territorial", True)],
            limit=20,
            fmt={
                "pct_bate_meta": ".0%",
                "atingimento_mediano": ".0%",
                "injustica_territorial": ".2f",
                "custo_premio_pct_venda": ".1%",
            },
        ),
        scatter_map("Mapa de oportunidade: potencial IBGE x atendimento", "opo"),
        table(
            "Municípios com maior potencial não explorado",
            "opo",
            columns=[
                "municipio",
                "uf",
                "populacao",
                "vlr_pib_per_capita",
                "dist_filial_km",
                "situacao",
                "indice_penetracao",
            ],
            filters=[sql_filter("coalesce(indice_penetracao, 0) < 0.5")],
            order=[("populacao", False)],
            limit=50,
            fmt={
                "populacao": ",d",
                "vlr_pib_per_capita": BRL,
                "dist_filial_km": ",.0f",
                "indice_penetracao": ".2f",
            },
        ),
        table(
            "Campanhas do mês por equipe",
            "camp",
            groupby=["descricao", "tipo_descricao"],
            metrics=["meta_leg", "meta_prop", "realizado", "pct"],
        ),
    ],
    "rows": [
        [
            c("Representantes em risco", 4, 26),
            c("% da meta projetado (equipe)", 4, 26),
            c("Positivação da carteira no mês", 4, 26),
        ],
        [c("Situação da equipe no mês", 8, 80), c("Status da meta por supervisor", 4, 80)],
        [
            c("Atingimento da meta legada (catraca) ao longo do tempo", 6, 50),
            c("Positivação da carteira ao longo do tempo", 6, 50),
        ],
        [c("Métodos de meta: justiça x atingibilidade x custo", 12, 45)],
        [
            c("Mapa de oportunidade: potencial IBGE x atendimento", 7, 80),
            c("Municípios com maior potencial não explorado", 5, 80),
        ],
        [c("Campanhas do mês por equipe", 12, 50)],
    ],
}

DIRETORIA = {
    "title": "Diretoria · Resultados e estratégia",
    "slug": "diretoria",
    "roles": ["Diretoria"],
    "filters": [{"name": "UF", "dataset": "dir", "column": "uf"}],
    "charts": [
        big(
            "Faturamento dos últimos 12 meses",
            "dir",
            "realizado",
            "R$ · líquido",
            filters=[sql_filter("ultimos_12m")],
        ),
        big(
            "Crescimento vs mesmo período do ano anterior",
            "dir",
            "crescimento",
            "últimos 12 meses",
            PCT,
            filters=[sql_filter("ultimos_12m")],
        ),
        big(
            "Receita incremental das campanhas (12m)",
            "ret",
            "incremental",
            "R$ · efeito causal, não o faturado bruto",
            filters=[sql_filter("ultimos_12m")],
        ),
        line(
            "Realizado e previsão (P10 · P50 · P90)",
            "prev",
            "mes",
            ["realizado", "p10", "p50", "p90", "meta_nova"],
            fmt=",.0f",
            desc="Previsão hierárquica reconciliada (LightGBM + MinT); faixa P10-P90 calibrada no backtest",
        ),
        bar(
            "Faturamento por região intermediária (IBGE), 12 meses",
            "dir",
            "regiao_intermediaria",
            ["realizado"],
            horizontal=True,
            filters=[sql_filter("ultimos_12m")],
        ),
        bar(
            "Faturamento mensal por canal",
            "dir",
            "mes",
            ["realizado"],
            groupby=["canal"],
            stack=True,
            grain="P1M",
        ),
        table(
            "Campanhas: faturado x receita incremental",
            "ret",
            groupby=["nome_fornecedor"],
            metrics=["faturado", "incremental", "pct_incremental"],
            order=[("incremental", False)],
            limit=24,
        ),
        table(
            "Política de metas: justiça x custo",
            "met",
            columns=[
                "metodo_descricao",
                "pct_bate_meta",
                "injustica_territorial",
                "custo_premio_pct_venda",
                "vigente",
            ],
            order=[("injustica_territorial", True)],
            limit=20,
            fmt={
                "pct_bate_meta": ".0%",
                "atingimento_mediano": ".0%",
                "injustica_territorial": ".2f",
                "custo_premio_pct_venda": ".1%",
            },
        ),
    ],
    "rows": [
        [
            c("Faturamento dos últimos 12 meses", 4, 26),
            c("Crescimento vs mesmo período do ano anterior", 4, 26),
            c("Receita incremental das campanhas (12m)", 4, 26),
        ],
        [c("Realizado e previsão (P10 · P50 · P90)", 12, 60)],
        [
            c("Faturamento por região intermediária (IBGE), 12 meses", 6, 60),
            c("Faturamento mensal por canal", 6, 60),
        ],
        [
            c("Campanhas: faturado x receita incremental", 6, 60),
            c("Política de metas: justiça x custo", 6, 60),
        ],
    ],
}

FINANCEIRO = {
    "title": "Financeiro e Contabilidade · Receita e provisões",
    "slug": "financeiro",
    "roles": ["Financeiro"],
    "filters": [{"name": "Filial", "dataset": "fin", "column": "nome_filial"}],
    "charts": [
        big(
            "Provisão de prêmio no mês (método vigente)",
            "met",
            "provisao",
            "R$ · valor esperado (simulação)",
            filters=[sql_filter("escolhido")],
        ),
        big(
            "% de devolução (12 meses)",
            "fin",
            "pct_dev",
            "devoluções ÷ faturamento bruto",
            ".2%",
            filters=[sql_filter("ultimos_12m")],
        ),
        line(
            "Previsão de receita para o fluxo de caixa (P10 · P50 · P90)",
            "prev",
            "mes",
            ["realizado", "p10", "p50", "p90"],
            fmt=",.0f",
        ),
        bar(
            "Provisão de prêmio por método de meta", "met", "metodo_descricao", ["provisao"], horizontal=True
        ),
        bar("Faturamento bruto x devoluções por mês", "fin", "mes", ["bruto", "devolucoes"], grain="P1M"),
        table(
            "Faturamento por filial e mês (conciliável com o fato de vendas)",
            "fin",
            groupby=["mes", "nome_filial"],
            metrics=["bruto", "devolucoes", "liquido", "pct_dev"],
            order=[("liquido", False)],
            limit=500,
        ),
        table(
            "Campanhas: receita incremental por fornecedor",
            "ret",
            groupby=["nome_fornecedor"],
            metrics=["faturado", "incremental"],
            order=[("incremental", False)],
        ),
    ],
    "rows": [
        [c("Provisão de prêmio no mês (método vigente)", 6, 26), c("% de devolução (12 meses)", 6, 26)],
        [
            c("Previsão de receita para o fluxo de caixa (P10 · P50 · P90)", 8, 60),
            c("Provisão de prêmio por método de meta", 4, 60),
        ],
        [c("Faturamento bruto x devoluções por mês", 12, 50)],
        [
            c("Faturamento por filial e mês (conciliável com o fato de vendas)", 7, 70),
            c("Campanhas: receita incremental por fornecedor", 5, 70),
        ],
    ],
}

MODELOS = {
    "title": "Dados e Modelos · Monitoramento",
    "slug": "modelos",
    "roles": ["Dados"],
    "filters": [],
    "charts": [
        bar(
            "WAPE no nível representante (h = 1), por modelo",
            "btm",
            "nivel",
            ["wape_lgbm", "wape_ets", "wape_ma3", "wape_catraca", "wape_snaive"],
            fmt=".3f",
            filters=[sql_filter("h = 1")],
        ),
        table(
            "Backtest: erro por nível e horizonte",
            "btm",
            columns=[
                "nivel",
                "h",
                "n",
                "wape_LGBM_MinT",
                "wape_ETS",
                "wape_MA3",
                "wape_Catraca",
                "wape_SNaive",
                "cobertura_p10_p90",
                "vies_LGBM_MinT",
            ],
            limit=100,
            fmt={
                **{
                    k: ".3f"
                    for k in ["wape_LGBM_MinT", "wape_ETS", "wape_MA3", "wape_Catraca", "wape_SNaive"]
                },
                "cobertura_p10_p90": ".0%",
                "vies_LGBM_MinT": "+.1%",
            },
        ),
        bar(
            "Campanhas: estudo de evento (DiD)",
            "es",
            "e",
            ["efeito"],
            fmt=PCT,
            desc="e < 0: placebo (deve ser ~0); e = 0: mês da campanha; e = +1: antecipação de compras",
        ),
        table(
            "Estudo de evento: efeito e IC 95% (bootstrap)",
            "es",
            columns=["e", "efeito", "ic_low", "ic_high"],
            limit=10,
            fmt={"efeito": "+.1%", "ic_low": "+.1%", "ic_high": "+.1%"},
        ),
        table(
            "Nowcast x tendência legada (WAPE)",
            "nce",
            columns=[
                "fase_do_mes",
                "n",
                "wape_tendencia_legado",
                "wape_tendencia_municipal",
                "wape_media_3m",
                "wape_modelo",
            ],
            limit=10,
            fmt={
                k: ".3f"
                for k in ["wape_tendencia_legado", "wape_tendencia_municipal", "wape_media_3m", "wape_modelo"]
            },
        ),
        table(
            "Decisões de modelo (auditoria)",
            "dec",
            columns=["gerado_em", "modelo_versao", "tipo", "detalhe"],
            order=[("gerado_em", False)],
            limit=50,
        ),
    ],
    "rows": [
        [
            c("WAPE no nível representante (h = 1), por modelo", 5, 60),
            c("Backtest: erro por nível e horizonte", 7, 60),
        ],
        [
            c("Campanhas: estudo de evento (DiD)", 4, 55),
            c("Estudo de evento: efeito e IC 95% (bootstrap)", 3, 55),
            c("Nowcast x tendência legada (WAPE)", 5, 55),
        ],
        [c("Decisões de modelo (auditoria)", 12, 45)],
    ],
}

DASHBOARDS = [VENDAS, GESTAO, DIRETORIA, FINANCEIRO, MODELOS]


# rótulos amigáveis adicionais
LABELS_EXTRA = {
    "vmc": {
        "meta_vigente": "Meta",
        "realizado_mtd": "Realizado",
        "projecao_fechamento": "Projeção",
        "prob_atingir_meta": "Chance de bater",
        "pct_positivacao": "Positivação",
        "rank_ajustado": "Ranking ajustado",
        "rank_bruto": "Ranking bruto",
    },
    "cli": {
        "municipio": "Município",
        "porte": "Porte",
        "prioridade": "Prioridade",
        "valor_esperado": "Valor esperado (R$)",
    },
    "opo": {
        "uf": "UF",
        "populacao": "População",
        "vlr_pib_per_capita": "PIB per capita (R$)",
        "dist_filial_km": "Distância da filial (km)",
        "situacao": "Situação",
    },
    "met": {"vigente": "Vigente"},
    "fin": {"mes": "Mês"},
    "nce": {
        "fase_do_mes": "Fase do mês",
        "wape_tendencia_legado": "Tendência legada",
        "wape_tendencia_municipal": "Tendência c/ calendário municipal",
        "wape_media_3m": "Média 3 meses",
        "wape_modelo": "Modelo",
    },
    "btm": {
        "nivel": "Nível",
        "wape_LGBM_MinT": "LightGBM+MinT",
        "wape_ETS": "ETS",
        "wape_MA3": "Média 3m",
        "wape_Catraca": "Catraca",
        "wape_SNaive": "Sazonal ingênuo",
        "cobertura_p10_p90": "Cobertura P10-P90",
        "vies_LGBM_MinT": "Viés",
    },
    "es": {"e": "Meses desde a campanha", "ic_low": "IC 2,5%", "ic_high": "IC 97,5%"},
}
for _k, _v in LABELS_EXTRA.items():
    DATASETS[_k].setdefault("labels", {}).update(_v)
