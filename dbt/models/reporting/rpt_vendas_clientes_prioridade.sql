-- VENDAS: lista acionável de clientes ainda NÃO positivados no mês corrente, priorizada pelo
-- valor esperado (compra média mensal dos últimos 6 meses fechados x frequência de compra).
with hist as (
    select
        cod_cliente,
        sum(vlr_liquido) / 6.0                     as compra_media_mensal_6m,
        count(distinct mes) / 6.0                  as frequencia_compra_6m,
        max(dt_venda)                              as ultima_compra
    from {{ ref('fct_vendas') }}
    where mes >= date_trunc('month', '{{ var("snapshot_date") }}'::date) - interval '6 months'
      and mes < date_trunc('month', '{{ var("snapshot_date") }}'::date)
      and not eh_devolucao
    group by 1
),

compraram_mes as (
    select distinct cod_cliente
    from {{ ref('fct_vendas') }}
    where mes = date_trunc('month', '{{ var("snapshot_date") }}'::date) and vlr_liquido > 0
)

select
    c.cod_cliente,
    c.razao_social,
    c.porte,
    c.municipio,
    c.uf,
    c.cod_representante,
    e.cod_supervisor,
    e.cod_coordenador,
    e.nome_representante,
    round(coalesce(h.compra_media_mensal_6m, 0)::numeric, 2)         as compra_media_mensal_6m,
    round(coalesce(h.frequencia_compra_6m, 0)::numeric, 2)           as frequencia_compra_6m,
    h.ultima_compra,
    '{{ var("snapshot_date") }}'::date - h.ultima_compra             as dias_sem_compra,
    round((coalesce(h.compra_media_mensal_6m, 0) * coalesce(h.frequencia_compra_6m, 0))::numeric, 2)
                                                                     as valor_esperado,
    row_number() over (
        partition by c.cod_representante
        order by coalesce(h.compra_media_mensal_6m, 0) * coalesce(h.frequencia_compra_6m, 0) desc
    )                                                                as prioridade
from {{ ref('dim_cliente') }} as c
inner join {{ ref('dim_equipe') }} as e on e.cod_representante = c.cod_representante
left join hist as h on h.cod_cliente = c.cod_cliente
where c.cod_cliente not in (select cod_cliente from compraram_mes)
