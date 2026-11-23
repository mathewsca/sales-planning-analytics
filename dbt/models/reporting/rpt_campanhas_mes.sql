-- VENDAS e GESTÃO: campanhas do mês corrente por representante: meta legada (histórico x (1 + g))
-- x meta proposta (linha de base x efeito CAUSAL estimado para o tipo de campanha) x realizado.
with efeito_tipo as (
    select tipo, max(efeito_planejamento) as efeito_tipo
    from {{ source('ml', 'campaign_effects') }}
    group by 1
),

base as (
    select
        r.*,
        round(
            r.meta_representante / (1 + {{ var("meta_crescimento_campanha") }})
            * (1 + coalesce(t.efeito_tipo, 0)::numeric),
            1
        ) as meta_proposta
    from {{ ref('mart_campanhas_resultado') }} as r
    left join efeito_tipo as t on t.tipo = r.tipo
)

select
    b.cod_campanha,
    d.descricao,
    d.tipo,
    d.tipo_descricao,
    d.nome_fornecedor,
    d.mes_campanha,
    b.cod_representante,
    e.nome_representante,
    e.cod_supervisor,
    e.cod_coordenador,
    b.meta_representante                                     as meta_legado,
    b.meta_proposta,
    b.meta_interno,
    b.realizado,
    b.vlr_faturado,
    b.vlr_faturado_interno,
    b.pct_atingimento                                        as pct_meta_legado,
    round(b.realizado / nullif(b.meta_proposta, 0), 4)       as pct_meta_proposta
from base as b
inner join {{ ref('dim_campanha') }} as d on d.cod_campanha = b.cod_campanha
inner join {{ ref('dim_equipe') }} as e on e.cod_representante = b.cod_representante
where d.mes_campanha = date_trunc('month', '{{ var("snapshot_date") }}'::date)
