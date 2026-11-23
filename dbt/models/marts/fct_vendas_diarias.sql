-- Agregado diário por representante x município x canal (base da previsão e do nowcast)
select
    dt_venda,
    mes,
    cod_representante,
    cod_ibge,
    canal,
    sum(vlr_liquido)                                              as vlr_liquido,
    coalesce(sum(vlr_liquido) filter (where not eh_devolucao), 0) as vlr_bruto,
    coalesce(-sum(vlr_liquido) filter (where eh_devolucao), 0)    as vlr_devolucao,
    count(distinct cod_pedido)                                    as qtd_pedidos,
    count(distinct cod_cliente)                                   as qtd_clientes
from {{ ref('fct_vendas') }}
group by 1, 2, 3, 4, 5
