select filial_id::int as cod_filial, cod_ibge::int as cod_ibge, nome_filial
from {{ source('erp', 'filiais') }}
