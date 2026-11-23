-- Itens faturados (grão: linha do pedido). Devoluções vêm como linhas negativas.
select
    pedido_id::bigint                  as cod_pedido,
    data_venda::date                   as dt_venda,
    cliente_id::bigint                 as cod_cliente,
    representante_id::bigint           as cod_representante,
    interno_id::bigint                 as cod_interno,
    produto_id::bigint                 as cod_produto,
    quantidade::int                    as qtd_itens,
    valor_liquido::numeric(14, 2)      as vlr_liquido,
    case when interno_id is null then 'Externo' else 'Interno' end as canal,
    valor_liquido < 0                  as eh_devolucao
from {{ source('erp', 'vendas_itens') }}
