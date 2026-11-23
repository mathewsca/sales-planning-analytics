-- Séries de base da previsão hierárquica: representante x município x canal x mês (grade completa,
-- com zeros), chaves da hierarquia (geografia IBGE e equipe) e exógenas conhecidas no futuro
-- (calendário municipal e campanhas). Só as colunas usadas por ml/forecast.py.
-- Inclui o mês corrente (parcial) e os 2 seguintes, com y nulo, como horizonte da previsão.
with series as (
    select distinct cod_representante, cod_ibge, canal from {{ ref('mart_vendas_mensais') }}
),

meses as (
    select distinct ano_mes as mes
    from {{ ref('dim_data') }}
    where ano_mes between (select min(mes) from {{ ref('mart_vendas_mensais') }})
        and date_trunc('month', '{{ var("snapshot_date") }}'::date + interval '2 months')::date
),

cal as (
    select
        cod_ibge,
        date_trunc('month', data)::date                                  as mes,
        sum(peso_dia_util)                                               as dias_uteis,
        count(*) filter (where eh_feriado and tipo_feriado = 'MUNICIPAL' and dia_semana between 1 and 5)
                                                                          as feriados_municipais,
        count(*) filter (where eh_ponte)                                 as pontes,
        count(*) filter (where eh_vespera)                               as vesperas
    from {{ ref('dim_calendario_municipal') }}
    group by 1, 2
),

camp as (
    select mes_campanha as mes, count(*) as qtd_campanhas
    from {{ ref('dim_campanha') }}
    group by 1
)

select
    s.cod_representante || '|' || s.cod_ibge || '|' || s.canal as unique_id,
    s.cod_representante,
    s.cod_ibge,
    s.canal,
    m.mes                                         as ds,
    -- só meses COMPLETOS têm alvo; o mês corrente (parcial) é horizonte de previsão (h=1)
    case when m.mes < date_trunc('month', '{{ var("snapshot_date") }}'::date)
         then coalesce(v.vlr_liquido, 0) end      as y,
    c.dias_uteis,
    c.feriados_municipais,
    c.pontes,
    c.vesperas,
    coalesce(cp.qtd_campanhas, 0)                 as qtd_campanhas,
    mu.uf,
    mu.cod_regiao_intermediaria,
    mu.cod_regiao_imediata,
    e.cod_supervisor,
    e.cod_coordenador
from series as s
cross join meses as m
inner join {{ ref('dim_municipio') }} as mu on mu.cod_ibge = s.cod_ibge
inner join {{ ref('dim_equipe') }} as e on e.cod_representante = s.cod_representante
left join cal as c on c.cod_ibge = s.cod_ibge and c.mes = m.mes
left join camp as cp on cp.mes = m.mes
left join {{ ref('mart_vendas_mensais') }} as v
    on v.cod_representante = s.cod_representante and v.cod_ibge = s.cod_ibge
    and v.canal = s.canal and v.mes = m.mes
