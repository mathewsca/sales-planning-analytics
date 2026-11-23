# Glossário único de KPIs (camada semântica)

Todos os dashboards leem destas definições. Elas são feitas uma vez nos marts dbt e como métricas
dos datasets do Superset (`superset/dashboards.py`). O teste `assert_kpis_consistentes` garante que o
faturamento mensal é igual nos painéis da Diretoria, do Financeiro e da Gestão.

| KPI | Definição | Fonte |
|---|---|---|
| Faturamento líquido | soma de `vlr_liquido`, já com as devoluções (linhas negativas) descontadas | `fct_vendas` |
| Faturamento bruto | soma das linhas positivas | `fct_vendas_diarias.vlr_bruto` |
| % de devolução | devoluções ÷ faturamento bruto | `rpt_financeiro_mensal` |
| Meta vigente | meta do mês pelo **método escolhido** na política de metas | `ml.quota_proposta` (escolhido) |
| Meta legada | (1 + 10%) × máx(mesmo mês do ano anterior, média dos últimos 3 meses) | `mart_metas_legado` |
| % da meta | realizado no mês ÷ meta vigente | `rpt_vendas_mes_corrente` |
| Dias úteis | seg–sex = 1, sábado = 0,5, domingo e feriados (nacional, estadual, **municipal**) = 0 | `dim_calendario_municipal` |
| Venda necessária por dia útil | (meta − realizado) ÷ dias úteis restantes do mês | `rpt_vendas_mes_corrente` |
| Projeção de fechamento | nowcast do modelo: acumulado do mês combinado com o histórico | `ml.nowcast.proj_modelo` |
| Chance de bater a meta | P(fechamento ≥ meta), com incerteza calibrada no backtest do nowcast | `ml.nowcast.prob_atingir_meta` |
| Positivação | clientes da carteira que compraram no mês ÷ clientes da carteira | `mart_carteira_mensal` |
| Ranking ajustado | posição pela habilidade estimada (efeito aleatório com shrinkage), descontado o potencial do território | `ml.rep_performance` |
| Índice de mercado (IBGE) | ½ participação na população + ½ participação no PIB, entre os municípios da região | `dim_municipio` |
| Penetração | participação na venda (12 meses) ÷ participação no índice de mercado; abaixo de 1 indica oportunidade | `mart_oportunidade_municipio` |
| Receita incremental de campanha | faturado da campanha × efeito ÷ (1 + efeito), com o efeito causal estimado por DiD | `ml.campaign_effects` |
| Provisão de prêmio | valor esperado do prêmio (3% da venda ao bater a meta + 2% sobre o excedente, até 150%), simulado com a previsão probabilística | `ml.quota_proposta.premio_esperado` |
| WAPE | Σ\|erro\| ÷ Σ\|real\| | `ml.backtest_metrics` |
