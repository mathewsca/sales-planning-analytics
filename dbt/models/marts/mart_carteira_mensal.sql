-- Carteira e positivação por representante x mês (o antigo "controle do time externo")
-- indice_mercado_carteira = soma, nos municípios do representante, do índice IBGE do município
-- multiplicado pela fração dos clientes do município que estão na carteira dele.
with rep_mun as (
    select
        cod_representante,
        cod_ibge,
        count(*) as n,
        count(*)::numeric / sum(count(*)) over (partition by cod_ibge) as fracao_municipio
    from {{ ref('dim_cliente') }}
    group by 1, 2
),

carteira as (
    select
        r.cod_representante,
        sum(r.n)                                        as qtd_carteira,
        sum(m.indice_mercado * r.fracao_municipio)      as indice_mercado_carteira
    from rep_mun as r
    inner join {{ ref('dim_municipio') }} as m on m.cod_ibge = r.cod_ibge
    group by 1
),

meses as (
    select distinct mes from {{ ref('fct_vendas') }}
),

pos as (
    select
        mes,
        cod_representante,
        count(distinct cod_cliente) filter (where vlr_liquido > 0) as qtd_positivados,
        sum(vlr_liquido) as vlr_liquido
    from {{ ref('fct_vendas') }}
    group by 1, 2
)

select
    m.mes,
    c.cod_representante,
    c.qtd_carteira,
    c.indice_mercado_carteira,
    coalesce(p.qtd_positivados, 0)                                       as qtd_positivados,
    round(coalesce(p.qtd_positivados, 0)::numeric / c.qtd_carteira, 4)  as pct_positivacao,
    coalesce(p.vlr_liquido, 0)                                           as vlr_liquido
from carteira as c
cross join meses as m
left join pos as p on p.cod_representante = c.cod_representante and p.mes = m.mes
