select
    campanha_id::int              as cod_campanha,
    representante_id::bigint      as cod_representante,
    meta_rep::numeric(14, 2)      as meta_representante,
    meta_interno::numeric(14, 2)  as meta_interno
from {{ source('erp', 'metas_campanha') }}
