-- Municípios IBGE + filial mais próxima + índice de mercado a priori.
-- indice_mercado = média da participação na população e no PIB da região: um índice simples e
-- transparente (no espírito dos "buying power indexes"); o modelo estima as elasticidades nos dados.
with m as (
    select * from {{ ref('stg_public__municipios') }}
),

f as (
    select fi.cod_filial, fi.nome_filial, mu.latitude, mu.longitude
    from {{ ref('stg_erp__filiais') }} as fi
    inner join m as mu on mu.cod_ibge = fi.cod_ibge
),

dist as (
    select
        m.cod_ibge,
        f.cod_filial,
        f.nome_filial,
        6371 * 2 * asin(sqrt(
            power(sin(radians(f.latitude - m.latitude) / 2), 2)
            + cos(radians(m.latitude)) * cos(radians(f.latitude))
            * power(sin(radians(f.longitude - m.longitude) / 2), 2)
        )) as dist_km
    from m cross join f
),

proxima as (
    select *, row_number() over (partition by cod_ibge order by dist_km) as rk from dist
),

clientes as (
    select cod_ibge, count(*) as qtd_clientes
    from {{ ref('stg_erp__clientes') }}
    group by cod_ibge
)

select
    m.*,
    p.cod_filial                                   as cod_filial_proxima,
    p.nome_filial                                  as filial_proxima,
    round(p.dist_km::numeric, 1)                   as dist_filial_km,
    coalesce(c.qtd_clientes, 0)                    as qtd_clientes,
    coalesce(c.qtd_clientes, 0) > 0                as atendido,
    round((0.5 * m.populacao / sum(m.populacao) over ()
         + 0.5 * m.vlr_pib / sum(m.vlr_pib) over ())::numeric, 8) as indice_mercado
from m
inner join proxima as p on p.cod_ibge = m.cod_ibge and p.rk = 1
left join clientes as c on c.cod_ibge = m.cod_ibge
