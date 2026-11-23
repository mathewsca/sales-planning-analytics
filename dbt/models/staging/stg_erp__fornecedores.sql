select fornecedor_id::int as cod_fornecedor, fornecedor as nome_fornecedor
from {{ source('erp', 'fornecedores') }}
