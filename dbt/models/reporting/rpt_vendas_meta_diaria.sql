-- VENDAS: meta diária x realizado no mês corrente, por representante.
-- A meta mensal é distribuída pelos dias úteis DO MUNICÍPIO (feriados estaduais e municipais da
-- carteira), modernizando o "Objetivo Diário" do Power BI, que só conhecia feriados nacionais.
with cal as (
    select cod_representante, data, peso_dia
    from {{ ref('dim_calendario_representante') }}
    where date_trunc('month', data) = date_trunc('month', '{{ var("snapshot_date") }}'::date)
),

meta as (
    select cod_representante, meta
    from {{ source('ml', 'quota_proposta') }}
    where escolhido and ds = date_trunc('month', '{{ var("snapshot_date") }}'::date)
),

venda as (
    select cod_representante, dt_venda as data, sum(vlr_liquido) as realizado
    from {{ ref('fct_vendas_diarias') }}
    where mes = date_trunc('month', '{{ var("snapshot_date") }}'::date)
    group by 1, 2
),

base as (
    select
        c.cod_representante,
        c.data,
        c.peso_dia,
        m.meta * c.peso_dia / sum(c.peso_dia) over (partition by c.cod_representante) as meta_dia,
        case when c.data <= '{{ var("snapshot_date") }}'::date then coalesce(v.realizado, 0) end as realizado_dia
    from cal as c
    left join meta as m on m.cod_representante = c.cod_representante
    left join venda as v on v.cod_representante = c.cod_representante and v.data = c.data
)

select
    b.*,
    sum(b.meta_dia) over w                                           as meta_acumulada,
    case when b.data <= '{{ var("snapshot_date") }}'::date
         then sum(coalesce(b.realizado_dia, 0)) over w end           as realizado_acumulado,
    e.cod_supervisor,
    e.cod_coordenador,
    e.nome_representante
from base as b
inner join {{ ref('dim_equipe') }} as e on e.cod_representante = b.cod_representante
window w as (partition by b.cod_representante order by b.data)
