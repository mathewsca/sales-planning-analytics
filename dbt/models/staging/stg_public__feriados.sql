-- Uma linha por (data, município) com feriado: nacional, estadual ou municipal
select data::date as data, cod_ibge::int as cod_ibge, tipo as tipo_feriado
from {{ source('public', 'feriados') }}
