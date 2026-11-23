-- Camada semântica única: o mesmo KPI tem de bater entre os dashboards de públicos diferentes.
-- Faturamento líquido mensal: Diretoria (rpt_previsao_empresa) = Financeiro (rpt_financeiro_mensal)
-- = Gestão (rpt_gestao_historico). Tolerância de R$ 1 por arredondamento.
{{ config(tags=['reporting']) }}
with d as (select mes, realizado from {{ ref('rpt_previsao_empresa') }} where realizado is not null),
f as (
    select mes, sum(faturamento_liquido) as fin
    from {{ ref('rpt_financeiro_mensal') }}
    where mes < date_trunc('month', '{{ var("snapshot_date") }}'::date)
    group by 1
),
g as (select mes, sum(realizado) as ges from {{ ref('rpt_gestao_historico') }} group by 1)
select d.mes, d.realizado, f.fin, g.ges
from d
left join f on f.mes = d.mes
left join g on g.mes = d.mes
where abs(d.realizado - coalesce(f.fin, 0)) > 1 or abs(d.realizado - coalesce(g.ges, 0)) > 1
