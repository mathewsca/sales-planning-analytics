select
    supervisor_id::int   as cod_supervisor,
    nome                 as nome_supervisor,
    coordenador_id::int  as cod_coordenador,
    filial_id::int       as cod_filial
from {{ source('erp', 'supervisores') }}
