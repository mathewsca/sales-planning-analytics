select interno_id::bigint as cod_interno, nome as nome_interno, filial_id::int as cod_filial
from {{ source('erp', 'vendedores_internos') }}
