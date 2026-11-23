-- DIRETORIA e FINANCEIRO: realizado mensal da empresa + previsão P10/P50/P90 (nível Total)
-- + meta total (legado x método escolhido). Base do gráfico "vamos bater o ano?" e da projeção de caixa.
with realizado_m as (
    select mes, sum(vlr_liquido) as realizado
    from {{ ref('mart_vendas_mensais') }}
    where mes < date_trunc('month', '{{ var("snapshot_date") }}'::date)
    group by 1
),

prev as (
    select ds::date as mes, p10, p50, p90
    from {{ source('ml', 'forecasts') }}
    where nivel = 'Total'
),

meta_leg as (
    select mes, sum(vlr_meta) as meta_legado from {{ ref('mart_metas_legado') }} group by 1
),

meta_nova as (
    select ds::date as mes, sum(meta) as meta_metodo_escolhido
    from {{ source('ml', 'quota_proposta') }} where escolhido group by 1
),

meses as (
    select mes from realizado_m union select mes from prev
)

select
    m.mes,
    r.realizado,
    p.p10 as previsao_p10,
    p.p50 as previsao_p50,
    p.p90 as previsao_p90,
    l.meta_legado,
    n.meta_metodo_escolhido,
    lag(r.realizado, 12) over (order by m.mes) as realizado_ano_anterior
from meses as m
left join realizado_m as r on r.mes = m.mes
left join prev as p on p.mes = m.mes
left join meta_leg as l on l.mes = m.mes
left join meta_nova as n on n.mes = m.mes
