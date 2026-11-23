select
    cliente_id::bigint        as cod_cliente,
    razao_social,
    cod_ibge::int             as cod_ibge,
    porte,
    segmento,
    representante_id::bigint  as cod_representante,
    interno_id::bigint        as cod_interno,
    data_cadastro::date       as dt_cadastro
from {{ source('erp', 'clientes') }}
