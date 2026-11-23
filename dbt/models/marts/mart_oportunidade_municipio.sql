-- Penetração de mercado por município: participação na venda (12 meses) / participação no índice IBGE.
-- indice_penetracao < 1 = vende abaixo do potencial (oportunidade); 0 = município não atendido.
with venda as (
    select cod_ibge, sum(vlr_liquido) as vlr_12m
    from {{ ref('fct_vendas_diarias') }}
    where dt_venda > '{{ var("snapshot_date") }}'::date - interval '12 months'
    group by 1
)

select
    m.cod_ibge,
    m.municipio,
    m.uf,
    m.regiao_intermediaria,
    m.regiao_imediata,
    m.latitude,
    m.longitude,
    m.populacao,
    m.vlr_pib_per_capita,
    m.indice_mercado,
    m.filial_proxima,
    m.dist_filial_km,
    m.atendido,
    case when m.atendido then 'Atendido' else 'Não atendido' end as situacao,
    m.qtd_clientes,
    coalesce(v.vlr_12m, 0) as vlr_12m,
    round(
        (coalesce(v.vlr_12m, 0) / sum(coalesce(v.vlr_12m, 0)) over ()) / nullif(m.indice_mercado, 0), 3
    ) as indice_penetracao
from {{ ref('dim_municipio') }} as m
left join venda as v on v.cod_ibge = m.cod_ibge
