-- GESTÃO (tático): histórico mensal por representante: meta legada x realizado, positivação,
-- e meta que cada método teria definido (simulação dos meses do backtest).
with sim as (
    select cod_representante, ds as mes,
           max(meta) filter (where metodo = 'previsao' and parametro = 0.05)      as meta_previsao,
           max(meta) filter (where metodo = 'potencial' and parametro = 0.5)      as meta_potencial,
           max(meta) filter (where metodo = 'probabilidade' and parametro = 0.6)  as meta_probabilidade
    from {{ source('ml', 'quota_scenarios') }}
    group by 1, 2
)

select
    c.mes,
    e.cod_representante,
    e.nome_representante,
    e.cod_supervisor,
    e.nome_supervisor,
    e.cod_coordenador,
    e.nome_coordenador,
    c.qtd_carteira,
    c.qtd_positivados,
    c.pct_positivacao,
    c.vlr_liquido                       as realizado,
    l.vlr_meta                          as meta_legado,
    l.pct_atingimento                   as pct_atingimento_legado,
    s.meta_previsao,
    s.meta_potencial,
    s.meta_probabilidade
from {{ ref('mart_carteira_mensal') }} as c
inner join {{ ref('dim_equipe') }} as e on e.cod_representante = c.cod_representante
left join {{ ref('mart_metas_legado') }} as l on l.cod_representante = c.cod_representante and l.mes = c.mes
left join sim as s on s.cod_representante = c.cod_representante and s.mes = c.mes
where c.mes < date_trunc('month', '{{ var("snapshot_date") }}'::date)
