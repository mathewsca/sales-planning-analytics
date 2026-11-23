select
    produto_id::bigint             as cod_produto,
    linha,
    fornecedor_id::int             as cod_fornecedor,
    preco_unitario::numeric(12, 2) as vlr_preco_unitario
from {{ source('erp', 'produtos') }}
