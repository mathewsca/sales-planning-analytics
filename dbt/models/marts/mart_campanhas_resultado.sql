-- Resultado das campanhas por representante: meta x realizado no tipo da campanha
-- (F = faturamento em R$, Q = quantidade, V = positivação = clientes distintos)
with itens as (
    select c.cod_campanha, c.tipo, v.cod_representante, v.cod_cliente, v.canal, v.qtd_itens, v.vlr_liquido
    from {{ ref('dim_campanha') }} as c
    inner join {{ ref('stg_erp__campanhas_produtos') }} as cp on cp.cod_campanha = c.cod_campanha
    inner join {{ ref('fct_vendas') }} as v
        on v.cod_produto = cp.cod_produto and v.mes = c.mes_campanha
),

realizado as (
    select
        cod_campanha,
        cod_representante,
        sum(vlr_liquido)                                           as vlr_faturado,
        sum(qtd_itens)                                             as qtd_itens,
        count(distinct cod_cliente) filter (where vlr_liquido > 0) as qtd_clientes,
        coalesce(sum(vlr_liquido) filter (where canal = 'Interno'), 0) as vlr_faturado_interno
    from itens
    group by 1, 2
),

base as (
    select
        m.cod_campanha,
        m.cod_representante,
        d.tipo,
        d.mes_campanha,
        m.meta_representante,
        m.meta_interno,
        coalesce(r.vlr_faturado, 0)         as vlr_faturado,
        coalesce(r.vlr_faturado_interno, 0) as vlr_faturado_interno,
        case d.tipo
            when 'F' then coalesce(r.vlr_faturado, 0)
            when 'Q' then coalesce(r.qtd_itens, 0)
            else coalesce(r.qtd_clientes, 0)
        end                                 as realizado
    from {{ ref('stg_erp__metas_campanha') }} as m
    inner join {{ ref('dim_campanha') }} as d on d.cod_campanha = m.cod_campanha
    left join realizado as r on r.cod_campanha = m.cod_campanha and r.cod_representante = m.cod_representante
)

select
    *,
    round(realizado / nullif(meta_representante, 0), 4) as pct_atingimento
from base
