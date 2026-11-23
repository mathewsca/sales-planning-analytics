-- tipo: F = faturamento (R$), Q = quantidade (unidades), V = positivação (clientes distintos)
select
    campanha_id::int                    as cod_campanha,
    descricao,
    fornecedor_id::int                  as cod_fornecedor,
    tipo,
    to_date(periodo, 'YYYY-MM')         as mes_campanha
from {{ source('erp', 'campanhas') }}
