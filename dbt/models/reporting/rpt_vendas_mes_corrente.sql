-- VENDAS (operacional, diário) e GESTÃO: situação de cada representante no mês corrente.
-- Uma linha por representante. RLS do Superset filtra por cod_representante / cod_supervisor.
with nc as (
    select * from {{ source('ml', 'nowcast') }}
),

legado as (
    select cod_representante, vlr_meta as meta_legado
    from {{ ref('mart_metas_legado') }}
    where mes = date_trunc('month', '{{ var("snapshot_date") }}'::date)
),

carteira as (
    select cod_representante, qtd_carteira, qtd_positivados, pct_positivacao
    from {{ ref('mart_carteira_mensal') }}
    where mes = date_trunc('month', '{{ var("snapshot_date") }}'::date)
)

select
    e.cod_representante,
    e.nome_representante,
    e.cod_supervisor,
    e.nome_supervisor,
    e.cod_coordenador,
    e.nome_coordenador,
    e.nome_filial,
    nc.data                                           as data_referencia,
    nc.meta_vigente,
    l.meta_legado,
    nc.vlr_mtd                                        as realizado_mtd,
    round((nc.vlr_mtd / nullif(nc.meta_vigente, 0))::numeric, 4)        as pct_meta_mtd,
    round((nc.du_decorridos / nullif(nc.du_mes, 0))::numeric, 4)        as pct_dias_uteis_decorridos,
    nc.du_restantes,
    nc.venda_necessaria_por_du,
    nc.proj_modelo                                    as projecao_fechamento,
    nc.proj_legado                                    as tendencia_legado,
    round((nc.proj_modelo / nullif(nc.meta_vigente, 0))::numeric, 4)    as pct_meta_projetado,
    round(nc.prob_atingir_meta::numeric, 4)          as prob_atingir_meta,
    case
        when nc.prob_atingir_meta >= 0.7 then '1 - No ritmo'
        when nc.prob_atingir_meta >= 0.4 then '2 - Atenção'
        else '3 - Em risco'
    end                                               as status_meta,
    c.qtd_carteira,
    c.qtd_positivados,
    c.pct_positivacao,
    p.habilidade_est,
    p.rank_ajustado,
    p.rank_bruto
from {{ ref('dim_equipe') }} as e
left join nc on nc.cod_representante = e.cod_representante
left join legado as l on l.cod_representante = e.cod_representante
left join carteira as c on c.cod_representante = e.cod_representante
left join {{ source('ml', 'rep_performance') }} as p on p.cod_representante = e.cod_representante
