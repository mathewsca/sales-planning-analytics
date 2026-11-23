-- Base do nowcast intramensal: por representante e dia, a venda acumulada no mês e os dias úteis
-- decorridos/restantes, pelo calendário da carteira do representante (dim_calendario_representante).
with cal_rep as (
    select cod_representante, data, peso_dia, peso_legado
    from {{ ref('dim_calendario_representante') }}
    -- calendário até o FIM do mês corrente: os dias úteis restantes já são conhecidos hoje
    where data <= (date_trunc('month', '{{ var("snapshot_date") }}'::date) + interval '1 month - 1 day')::date
),

venda as (
    select cod_representante, dt_venda as data, sum(vlr_liquido) as vlr_dia
    from {{ ref('fct_vendas_diarias') }}
    group by 1, 2
),

dia as (
    select
        c.cod_representante,
        c.data,
        date_trunc('month', c.data)::date as mes,
        c.peso_dia,
        c.peso_legado,
        coalesce(v.vlr_dia, 0) as vlr_dia
    from cal_rep as c
    left join venda as v on v.cod_representante = c.cod_representante and v.data = c.data
    where c.data >= (select min(dt_venda) from {{ ref('fct_vendas_diarias') }})
),

final as (
    select
        cod_representante,
        data,
        mes,
        vlr_dia,
        sum(vlr_dia) over w_mtd                                   as vlr_mtd,
        sum(peso_dia) over w_mtd                                  as du_decorridos,
        sum(peso_dia) over w_mes                                  as du_mes,
        sum(peso_legado) over w_mtd                               as du_decorridos_legado,
        sum(peso_legado) over w_mes                               as du_mes_legado,
        sum(vlr_dia) over w_mes                                   as vlr_mes
    from dia
    window
        w_mtd as (partition by cod_representante, mes order by data rows between unbounded preceding and current row),
        w_mes as (partition by cod_representante, mes)
)

select * from final
where data <= '{{ var("snapshot_date") }}'::date
