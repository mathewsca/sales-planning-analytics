-- DIRETORIA: realizado mensal por UF / região intermediária / canal, com o ano anterior
-- (a previsão P10/P50/P90 da empresa está em rpt_previsao_empresa).
with realizado_m as (
    select v.mes, m.uf, m.regiao_intermediaria, v.canal,
           sum(v.vlr_liquido) as realizado, sum(v.vlr_bruto) as bruto, sum(v.vlr_devolucao) as devolucao
    from {{ ref('mart_vendas_mensais') }} as v
    inner join {{ ref('dim_municipio') }} as m on m.cod_ibge = v.cod_ibge
    where v.mes < date_trunc('month', '{{ var("snapshot_date") }}'::date)
    group by 1, 2, 3, 4
)

select
    r.*,
    lag(r.realizado, 12) over (partition by r.uf, r.regiao_intermediaria, r.canal order by r.mes) as realizado_ano_anterior,
    r.mes >= date_trunc('month', '{{ var("snapshot_date") }}'::date) - interval '12 months' as ultimos_12m
from realizado_m as r
