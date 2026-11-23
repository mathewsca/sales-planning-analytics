-- Teste anti-vazamento: só meses COMPLETOS anteriores ao snapshot podem ter alvo (y);
-- o mês corrente (parcial) e os meses futuros precisam ter y nulo.
select unique_id, ds, y
from {{ ref('ml_serie_mensal') }}
where (ds >= date_trunc('month', '{{ var("snapshot_date") }}'::date) and y is not null)
   or (ds < date_trunc('month', '{{ var("snapshot_date") }}'::date) and y is null)
