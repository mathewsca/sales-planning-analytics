-- Fato de vendas (grão: item do pedido), com chaves de equipe e geografia
{{ config(indexes=[{'columns': ['mes']}, {'columns': ['cod_produto', 'mes']}]) }}
select
    v.cod_pedido,
    v.dt_venda,
    date_trunc('month', v.dt_venda)::date   as mes,
    v.cod_cliente,
    v.cod_representante,
    v.cod_interno,
    v.canal,
    v.cod_produto,
    c.cod_ibge,
    v.qtd_itens,
    v.vlr_liquido,
    v.eh_devolucao
from {{ ref('stg_erp__vendas_itens') }} as v
inner join {{ ref('stg_erp__clientes') }} as c on c.cod_cliente = v.cod_cliente
