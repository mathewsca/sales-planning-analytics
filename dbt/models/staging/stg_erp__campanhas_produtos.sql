select distinct campanha_id::int as cod_campanha, produto_id::bigint as cod_produto
from {{ source('erp', 'campanhas_produtos') }}
