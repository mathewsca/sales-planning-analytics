-- Vendas mensais por representante x município x canal
select
    mes,
    cod_representante,
    cod_ibge,
    canal,
    sum(vlr_liquido)   as vlr_liquido,
    sum(vlr_bruto)     as vlr_bruto,
    sum(vlr_devolucao) as vlr_devolucao,
    sum(qtd_pedidos)   as qtd_pedidos
from {{ ref('fct_vendas_diarias') }}
group by 1, 2, 3, 4
