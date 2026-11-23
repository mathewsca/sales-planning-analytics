select p.cod_produto, p.linha, p.cod_fornecedor, f.nome_fornecedor, p.vlr_preco_unitario
from {{ ref('stg_erp__produtos') }} as p
inner join {{ ref('stg_erp__fornecedores') }} as f on f.cod_fornecedor = p.cod_fornecedor
