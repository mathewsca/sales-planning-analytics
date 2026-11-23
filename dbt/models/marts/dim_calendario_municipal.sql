-- Calendário comercial por município (mesmas regras do gerador e de public/calendar.py).
--   peso_dia_util: seg-sex = 1, sábado = 0,5, domingo = 0, feriado nacional/estadual/MUNICIPAL = 0
--   peso_legado:   regra antiga do Power BI (só feriados nacionais; sábado = 0,5)
--   eh_vespera / eh_ponte: efeitos de calendário usados como variáveis do modelo
{{ config(indexes=[{'columns': ['cod_ibge', 'data']}]) }}
with dias as (
    select data, dia_semana from {{ ref('dim_data') }} where data between '2023-01-01' and '2026-12-31'
),

mun as (
    select cod_ibge from {{ ref('dim_municipio') }} where atendido
),

fer as (
    select data, cod_ibge, max(tipo_feriado) as tipo_feriado
    from {{ ref('stg_public__feriados') }}
    group by data, cod_ibge
),

base as (
    select
        d.data,
        d.dia_semana,
        m.cod_ibge,
        f.tipo_feriado,
        f.tipo_feriado is not null  as eh_feriado,
        f1.cod_ibge is not null     as amanha_feriado,
        f0.cod_ibge is not null     as ontem_feriado
    from dias as d
    cross join mun as m
    left join fer as f on f.cod_ibge = m.cod_ibge and f.data = d.data
    left join fer as f1 on f1.cod_ibge = m.cod_ibge and f1.data = d.data + 1
    left join fer as f0 on f0.cod_ibge = m.cod_ibge and f0.data = d.data - 1
),

flags as (
    select
        *,
        (not eh_feriado) and ((dia_semana = 1 and amanha_feriado) or (dia_semana = 5 and ontem_feriado)) as eh_ponte
    from base
)

select
    data,
    cod_ibge,
    dia_semana,
    eh_feriado,
    tipo_feriado,
    eh_ponte,
    (not eh_feriado) and (not eh_ponte) and amanha_feriado and dia_semana between 1 and 5 as eh_vespera,
    (case
        when eh_feriado then 0
        when dia_semana = 7 then 0
        when dia_semana = 6 then 0.5
        else 1
    end)::numeric(3, 1) as peso_dia_util,
    (case
        when tipo_feriado = 'NACIONAL' then 0
        when dia_semana = 7 then 0
        when dia_semana = 6 then 0.5
        else 1
    end)::numeric(3, 1) as peso_legado
from flags
