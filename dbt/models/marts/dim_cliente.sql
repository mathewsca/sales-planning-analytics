select
    c.cod_cliente,
    c.razao_social,
    c.porte,
    c.segmento,
    c.dt_cadastro,
    c.cod_representante,
    c.cod_interno,
    c.cod_ibge,
    m.municipio,
    m.uf,
    m.regiao_imediata,
    m.regiao_intermediaria
from {{ ref('stg_erp__clientes') }} as c
inner join {{ ref('dim_municipio') }} as m on m.cod_ibge = c.cod_ibge
