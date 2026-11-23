-- Meta legada (catraca) x realizado por representante e mês
with meta as (
    select cod_representante, mes, sum(vlr_meta) as vlr_meta
    from {{ ref('stg_erp__metas_mensais') }}
    group by 1, 2
),

realizado as (
    select cod_representante, mes, sum(vlr_liquido) as vlr_realizado
    from {{ ref('mart_vendas_mensais') }}
    group by 1, 2
)

select
    m.cod_representante,
    m.mes,
    m.vlr_meta,
    coalesce(r.vlr_realizado, 0)                                   as vlr_realizado,
    round(coalesce(r.vlr_realizado, 0) / nullif(m.vlr_meta, 0), 4) as pct_atingimento,
    coalesce(r.vlr_realizado, 0) >= m.vlr_meta                    as bateu_meta
from meta as m
left join realizado as r on r.cod_representante = m.cod_representante and r.mes = m.mes
