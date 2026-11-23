-- FINANCEIRO e CONTABILIDADE: faturamento bruto, devoluções e líquido por filial e UF, por mês
-- (conciliável com o fato de vendas: a soma do líquido bate com fct_vendas).
select
    v.mes,
    e.nome_filial,
    m.uf,
    v.canal,
    sum(v.vlr_bruto)       as faturamento_bruto,
    sum(v.vlr_devolucao)   as devolucoes,
    sum(v.vlr_liquido)     as faturamento_liquido,
    sum(v.qtd_pedidos)     as pedidos,
    v.mes >= date_trunc('month', '{{ var("snapshot_date") }}'::date) - interval '12 months'
        and v.mes < date_trunc('month', '{{ var("snapshot_date") }}'::date) as ultimos_12m
from {{ ref('mart_vendas_mensais') }} as v
inner join {{ ref('dim_equipe') }} as e on e.cod_representante = v.cod_representante
inner join {{ ref('dim_municipio') }} as m on m.cod_ibge = v.cod_ibge
group by 1, 2, 3, 4, v.mes
