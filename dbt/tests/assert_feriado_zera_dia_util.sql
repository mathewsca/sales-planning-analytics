-- Regra de negócio: feriado (nacional, estadual ou municipal) nunca conta como dia útil.
select * from {{ ref('dim_calendario_municipal') }}
where eh_feriado and peso_dia_util > 0
