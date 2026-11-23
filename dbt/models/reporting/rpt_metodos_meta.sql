-- GESTÃO e DIRETORIA: comparação dos métodos de meta (simulação no backtest) + provisão de prêmio
-- esperada para o mês corrente e o próximo, por método.
with prov as (
    select metodo, parametro,
           sum(premio_esperado) filter (where ds = date_trunc('month', '{{ var("snapshot_date") }}'::date)) as provisao_mes_corrente,
           sum(meta) filter (where ds = date_trunc('month', '{{ var("snapshot_date") }}'::date))            as meta_total_mes_corrente,
           avg(prob_atingir) filter (where ds = date_trunc('month', '{{ var("snapshot_date") }}'::date))    as prob_media_atingir
    from {{ source('ml', 'quota_proposta') }}
    group by 1, 2
)

select
    s.metodo,
    case s.metodo
        when 'legado' then 'Legado (catraca: +10% sobre o máximo)'
        when 'previsao' then 'Previsão (P50 + ' || round((s.parametro * 100)::numeric) || '%)'
        when 'potencial' then 'Potencial IBGE x habilidade^' || s.parametro
        else 'Probabilidade de atingir = ' || round((s.parametro * 100)::numeric) || '%'
    end                                         as metodo_descricao,
    s.parametro,
    s.escolhido,
    case when s.escolhido then '✔ vigente' else '' end as vigente,
    s.meses,
    s.atingimento_mediano,
    s.pct_bate_meta,
    s.dispersao_iqr,
    s.correlacao_territorio,
    abs(s.correlacao_territorio)                as injustica_territorial,
    s.custo_premio_pct_venda,
    s.meta_sobre_previsao,
    p.meta_total_mes_corrente,
    p.provisao_mes_corrente,
    p.prob_media_atingir
from {{ source('ml', 'quota_summary') }} as s
left join prov as p on p.metodo = s.metodo and p.parametro = s.parametro
