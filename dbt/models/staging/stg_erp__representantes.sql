select
    representante_id::bigint as cod_representante,
    nome                     as nome_representante,
    supervisor_id::int       as cod_supervisor,
    coordenador_id::int      as cod_coordenador,
    filial_id::int           as cod_filial,
    data_admissao::date      as dt_admissao
from {{ source('erp', 'representantes') }}
