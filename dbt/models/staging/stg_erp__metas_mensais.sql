-- Metas legadas por representante x município x mês (regra antiga: catraca sobre o histórico)
select
    representante_id::bigint     as cod_representante,
    cod_ibge::int                as cod_ibge,
    to_date(periodo, 'YYYY-MM')  as mes,
    meta_valor::numeric(14, 2)   as vlr_meta
from {{ source('erp', 'metas_mensais') }}
