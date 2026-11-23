select
    c.cod_campanha,
    c.descricao,
    c.tipo,
    case c.tipo when 'F' then 'Faturamento (R$)' when 'Q' then 'Quantidade' else 'Positivação' end as tipo_descricao,
    c.mes_campanha,
    c.cod_fornecedor,
    f.nome_fornecedor,
    count(cp.cod_produto) as qtd_skus
from {{ ref('stg_erp__campanhas') }} as c
inner join {{ ref('stg_erp__fornecedores') }} as f on f.cod_fornecedor = c.cod_fornecedor
left join {{ ref('stg_erp__campanhas_produtos') }} as cp on cp.cod_campanha = c.cod_campanha
group by 1, 2, 3, 4, 5, 6, 7
