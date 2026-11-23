-- DIRETORIA e FINANCEIRO: retorno das campanhas de fornecedores: faturado bruto da campanha x
-- receita INCREMENTAL estimada (diferença-em-diferenças) x leituras ingênuas.
select
    c.cod_campanha,
    d.descricao,
    d.tipo_descricao,
    d.nome_fornecedor,
    c.mes_campanha,
    c.n_skus,
    c.vlr_campanha                            as faturado_campanha,
    c.vlr_incremental_estimado                as receita_incremental,
    c.efeito_did                              as efeito_causal,
    c.efeito_planejamento                     as efeito_planejamento_tipo,
    c.efeito_ingenuo_transversal              as leitura_ingenua_vs_outros_skus,
    c.efeito_antes_depois                     as leitura_antes_depois,
    c.mes_campanha >= date_trunc('month', '{{ var("snapshot_date") }}'::date) - interval '12 months' as ultimos_12m
from {{ source('ml', 'campaign_effects') }} as c
inner join {{ ref('dim_campanha') }} as d on d.cod_campanha = c.cod_campanha
