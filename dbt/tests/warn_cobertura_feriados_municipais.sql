-- Qualidade de dado público: municípios ATENDIDOS sem nenhum feriado municipal na fonte aberta.
-- É um aviso (não falha): a base aberta de feriados municipais é incompleta, e isso fica documentado
-- no data card. O número de linhas retornadas é o tamanho da lacuna.
{{ config(severity='warn', warn_if='>0') }}
select m.cod_ibge, m.municipio, m.uf, m.qtd_clientes
from {{ ref('dim_municipio') }} as m
where m.atendido
  and not exists (
      select 1 from {{ ref('dim_calendario_municipal') }} as c
      where c.cod_ibge = m.cod_ibge and c.tipo_feriado = 'MUNICIPAL'
  )
