-- Calendário comercial de cada representante: média dos calendários dos municípios da carteira,
-- ponderada pelo nº de clientes (um feriado municipal pesa onde há clientes).
-- Base do nowcast (ml_nowcast_diario) e da meta diária (rpt_vendas_meta_diaria).
{{ config(indexes=[{'columns': ['cod_representante', 'data']}]) }}
with pesos as (
    select cod_representante, cod_ibge, count(*)::numeric as w
    from {{ ref('dim_cliente') }}
    group by 1, 2
)

select
    p.cod_representante,
    c.data,
    sum(p.w * c.peso_dia_util) / sum(p.w) as peso_dia,
    sum(p.w * c.peso_legado) / sum(p.w)   as peso_legado
from pesos as p
inner join {{ ref('dim_calendario_municipal') }} as c on c.cod_ibge = p.cod_ibge
group by 1, 2
