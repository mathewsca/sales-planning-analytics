# Do DAX (Power BI) para SQL (dbt) + modelos

O relatório original calculava metas e tendências em medidas DAX. Aqui cada regra virou SQL
versionado e testado. Onde a regra antiga tinha uma limitação, ela foi substituída por um modelo, e
a regra antiga continua calculada como **baseline**.

| Medida antiga | O que fazia | Onde está agora | O que mudou |
|---|---|---|---|
| `DIAS UTEIS` | seg–sex = 1, sábado = 0,5, feriado = 0 | `dim_calendario_municipal.peso_legado` | O mesmo peso, mas o calendário passa a ser **por município**: `peso_dia_util` inclui feriados estaduais e municipais. |
| `Objetivo Diário` | meta do mês ÷ dias úteis × dias úteis do dia | `rpt_vendas_meta_diaria.meta_dia` | Distribuída pelos dias úteis **da carteira do representante**. |
| `Tendência` | acumulado ÷ dias úteis decorridos × dias úteis do mês | `nowcast.proj_legado` (baseline) | Substituída pelo **nowcast** (LightGBM), que pondera o histórico no início do mês. |
| `SUGESTÃO` | (meta − acumulado) ÷ dias a trabalhar | `rpt_vendas_mes_corrente.venda_necessaria_por_du` | Usa os dias úteis restantes do município. |
| `% Objetivo` | faturado ÷ objetivo | `pct_meta_mtd`, `pct_atingimento` | Igual. |
| `% Participação Vendedores Internos` | faturado com televendas ÷ faturado | `canal = 'Interno'` em `fct_vendas` | Canal virou uma dimensão da hierarquia de previsão. |
| Objetivo de campanha (tipo F/Q) | meta em R$ ou em unidades por representante; vendedor interno = 20% | `rpt_campanhas_mes` | Meta proposta = linha de base × (1 + **efeito causal** estimado do tipo de campanha). |
| `Produtos Não Vendidos` | SKUs da campanha sem venda | `ml_painel_campanha` | Entra no estudo de efeito. |
| Meta mensal (tabela de objetivos) | definida fora do BI, pelo histórico | `mart_metas_legado` (regra da catraca) + `ml.quota_proposta` | Quatro métodos comparados por simulação (`docs/metas.md`). |
