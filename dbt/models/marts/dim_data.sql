with dias as (
    select generate_series('2022-01-01'::date, '2027-12-31'::date, interval '1 day')::date as data
)

select
    data,
    to_char(data, 'YYYYMMDD')::int                    as pk_data,
    extract(year from data)::int                      as ano,
    extract(quarter from data)::int                   as trimestre,
    extract(month from data)::int                     as mes,
    (array['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'])
        [extract(month from data)::int]               as nome_mes,
    date_trunc('month', data)::date                   as ano_mes,
    extract(isodow from data)::int                    as dia_semana
from dias
