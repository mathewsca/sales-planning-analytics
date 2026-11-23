-- Hierarquia comercial: coordenador -> supervisor -> representante (+ filial)
select
    r.cod_representante,
    r.nome_representante,
    r.dt_admissao,
    s.cod_supervisor,
    s.nome_supervisor,
    c.cod_coordenador,
    c.nome_coordenador,
    f.cod_filial,
    f.nome_filial
from {{ ref('stg_erp__representantes') }} as r
inner join {{ ref('stg_erp__supervisores') }} as s on s.cod_supervisor = r.cod_supervisor
inner join {{ ref('stg_erp__coordenadores') }} as c on c.cod_coordenador = r.cod_coordenador
inner join {{ ref('stg_erp__filiais') }} as f on f.cod_filial = r.cod_filial
