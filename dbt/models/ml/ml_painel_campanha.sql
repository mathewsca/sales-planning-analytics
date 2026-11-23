-- Painel SKU x mês para o efeito causal das campanhas (diferença-em-diferenças escalonado).
-- primeira_campanha = mês da 1ª campanha do SKU (coorte de tratamento); SKUs nunca tratados = null.
with meses as (  -- só meses completos (o mês corrente parcial distorceria o efeito)
    select distinct mes from {{ ref('fct_vendas') }}
    where mes < date_trunc('month', '{{ var("snapshot_date") }}'::date)
),

skus as (
    select cod_produto from {{ ref('dim_produto') }}
),

qtd as (
    select cod_produto, mes, sum(qtd_itens) as qtd, sum(vlr_liquido) as vlr
    from {{ ref('fct_vendas') }}
    where not eh_devolucao
    group by 1, 2
),

trat as (
    select cp.cod_produto, c.mes_campanha, c.cod_campanha, c.tipo
    from {{ ref('stg_erp__campanhas_produtos') }} as cp
    inner join {{ ref('stg_erp__campanhas') }} as c on c.cod_campanha = cp.cod_campanha
),

primeira as (
    select cod_produto, min(mes_campanha) as primeira_campanha
    from trat
    group by 1
)

select
    s.cod_produto,
    m.mes,
    coalesce(q.qtd, 0)                         as qtd,
    coalesce(q.vlr, 0)                         as vlr,
    t.cod_campanha is not null                 as em_campanha,
    t.cod_campanha,
    p.primeira_campanha
from skus as s
cross join meses as m
left join qtd as q on q.cod_produto = s.cod_produto and q.mes = m.mes
left join (
    select cod_produto, mes_campanha, min(cod_campanha) as cod_campanha
    from trat group by 1, 2
) as t on t.cod_produto = s.cod_produto and t.mes_campanha = m.mes
left join primeira as p on p.cod_produto = s.cod_produto
