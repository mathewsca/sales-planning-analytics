-- Municípios IBGE com população (SIDRA 6579) e PIB (SIDRA 5938)
select
    cod_ibge::int                    as cod_ibge,
    municipio,
    uf,
    cod_regiao_imediata::int         as cod_regiao_imediata,
    regiao_imediata,
    cod_regiao_intermediaria::int    as cod_regiao_intermediaria,
    regiao_intermediaria,
    populacao::bigint                as populacao,
    pib::numeric(18, 2)              as vlr_pib,
    pib_per_capita::numeric(14, 2)   as vlr_pib_per_capita,
    latitude::double precision       as latitude,
    longitude::double precision      as longitude,
    coalesce(capital::int, 0) = 1    as eh_capital
from {{ source('public', 'ibge_municipios') }}
