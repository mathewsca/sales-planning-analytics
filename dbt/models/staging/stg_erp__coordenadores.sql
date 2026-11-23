select coordenador_id::int as cod_coordenador, nome as nome_coordenador
from {{ source('erp', 'coordenadores') }}
