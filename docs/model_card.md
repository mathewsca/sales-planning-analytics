# Model card: previsão hierárquica de vendas + nowcast intramensal

| | |
|---|---|
| **Tarefa** | Prever o faturamento líquido mensal (h = 1 a 3) em todos os níveis da hierarquia comercial e geográfica, e projetar o fechamento do mês corrente a partir do acumulado |
| **Modelo** | LightGBM global (mlforecast, objetivo Tweedie, alvo escalado por série) + reconciliação MinT-shrink (hierarchicalforecast); nowcast com LightGBM (perda L1) |
| **Hierarquia** | Total → UF → região intermediária → região imediata (IBGE) · Total → coordenador → supervisor → representante · canal · base = representante × município × canal (1.789 séries) |
| **Variáveis** | defasagens (1, 2, 3, 6, 12), médias móveis (3 e 12), mês, **dias úteis do município**, feriados municipais, pontes, vésperas, nº de campanhas, escala e nível da série |
| **Intervalos** | P10/P90 por conformal *pooled* por nível e horizonte, calibrado só com as origens anteriores do backtest |
| **Registro** | MLflow (`sales-forecast-lgbm`), aliases `champion` e `challenger`, decisões auditadas em `ml.model_decisions` |

## Uso pretendido
- **Sim:** base para as metas mensais, projeção de receita (financeiro) e acompanhamento do mês (vendas e gestão).
- **Não:** avaliação individual de pessoas sem contexto. A previsão é uma expectativa com incerteza, não um julgamento de desempenho. O desempenho individual tem modelo próprio, com shrinkage (`ml/performance.py`).

## Protocolo de avaliação (definido antes dos resultados)
- Validação com **origem móvel**: 8 origens mensais (mai a dez/2025), horizonte de até 3 meses.
- Métrica principal: **WAPE no nível representante, h = 1**, que é o nível e o prazo das metas. MASE fica como secundária.
- Aceite: o modelo só entra se superar o **melhor baseline** com IC 95% do bootstrap pareado (por série) inteiramente abaixo de zero.
- Gate de promoção: o desafiante não pode piorar mais de 10% o WAPE do campeão.

## Resultados (nível representante, h = 1)

| Modelo | WAPE | Diferença do LightGBM+MinT (IC 95%) |
|---|---|---|
| **LightGBM + MinT** | **0,213** | — |
| ETS (melhor baseline) | 0,224 | −0,012 [−0,017; −0,007] |
| Média 3 meses | 0,245 | −0,032 [−0,040; −0,025] |
| Catraca (regra antiga das metas) | 0,261 | −0,049 [−0,059; −0,038] |
| Sazonal ingênuo | 0,281 | −0,069 [−0,081; −0,056] |

- Cobertura do intervalo P10–P90 no nível representante: **80%** (alvo: 80%).
- **No total da empresa, o sazonal ingênuo é competitivo.** A série total é suave e muito sazonal. O ganho do modelo global aparece onde há muitas séries ruidosas e com variáveis exógenas (representante e município), um padrão já observado no M5.
- **MinT × previsão base:** o WAPE é praticamente igual. O ganho da reconciliação está na **coerência**: as metas de representante, supervisor, coordenador e empresa somam exatamente.

## Desafiante recusado: correção do viés

**Problema.** O campeão (v3) subestima de forma sistemática: o viés é de **−7,1%** em h = 1, igual em todos os níveis, porque o MinT torna o viés coerente. A causa é estrutural. O gerador tem crescimento de cerca de 6% ao ano, e árvores de decisão aplicadas ao **nível** da série não preveem acima do que já viram. No representante o ruído individual domina e o viés pesa pouco. No Total quase todo o erro é viés, e a Catraca (`max(ano anterior, média 3m)`) vence por acaso.

**Seleção (sem tocar o backtest oficial).** As variantes foram comparadas em 3 origens de **validação** (dez/2024, fev/2025 e abr/2025), anteriores às 8 origens do backtest:

| Variante | Viés médio (h = 1–3) | WAPE Total (h = 1) | WAPE Representante (h = 1) |
|---|---|---|---|
| Campeão (nível, Tweedie) | −11,2% | 0,115 | 0,226 |
| Escala pelo nível dos últimos 12 meses | −8,3% | 0,117 | 0,228 |
| **Alvo diferenciado em 1 mês** (escolhida) | **+2,3%** | **0,054** | **0,215** |
| Escala recente + alvo diferenciado | +3,6% | 0,055 | 0,219 |

A diferença sazonal (12 meses) era a candidata natural, mas não cabe no histórico: os dados começam em fev/2023, e a diferença de 12 meses mais os lags de 12 meses deixariam só ~4 meses de treino por série.

**Backtest oficial (8 origens, mai–dez/2025), uma única execução:**

| WAPE · h = 1 | Campeão v3 | Desafiante v4 | Catraca | ETS |
|---|---|---|---|---|
| Total | 0,077 | **0,057** | 0,064 | 0,069 |
| UF | 0,087 | 0,076 | **0,074** | 0,086 |
| Coordenador | 0,084 | **0,072** | 0,075 | 0,087 |
| Supervisor | 0,097 | **0,091** | 0,093 | 0,107 |
| **Representante** | **0,213** | 0,229 | 0,261 | 0,224 |
| Viés h = 1 / h = 3 | −7,1% / −6,2% | +4,1% / +8,7% | | |

**Decisão.** O desafiante melhora os níveis agregados, mas **passa do ponto**: a variação prevista acumula com o horizonte, e o viés vai de +4% a +9%. Além disso, piora o nível representante, que é o critério de aceite. Ele não vence o ETS (IC 95% de −0,2 a +1,1 p.p.) e foi **recusado pelo gate**. A configuração fica no código como `DIFF_CONFIG` (`ml/forecast.py`) e está registrada no MLflow como v4 (`challenger`).

**Primeiro ciclo.** Quando ainda não há nenhuma previsão em produção, não existe campeão para manter. Nesse caso um modelo recusado é publicado como **provisório** (decisão registrada com `"provisorio": true` em `ml.model_decisions`, sem o alias `champion`), para que metas, nowcast e dashboards não fiquem sem previsão. Do segundo ciclo em diante, um modelo recusado nunca é publicado.

**Por que a validação não antecipou o resultado.** Em 3 origens, o viés do campeão era maior (−11%), e a correção tinha mais a ganhar. Em 8 origens, o ruído do representante pesa mais que o viés. A divergência entre validação e teste é exatamente o motivo de existir um gate em dados não vistos.

**Próximo passo sugerido** (não testado): corrigir só o viés agregado, sem mudar o modelo. Um exemplo é um fator de nível estimado nas origens anteriores e aplicado antes da reconciliação. Ele seria avaliado com o mesmo protocolo.

## Nowcast (mês corrente)
Comparado com a "Tendência" do Power BI, que projeta o fechamento como acumulado ÷ dias úteis decorridos × dias úteis do mês:

| Fase do mês | Tendência legada | Tendência com calendário municipal | Modelo |
|---|---|---|---|
| Início (até 30% dos dias úteis) | 0,498 | 0,495 | **0,210** |
| Meio (30–60%) | 0,213 | 0,213 | **0,158** |
| Fim (60–95%) | 0,104 | 0,104 | **0,094** |
| Meses com feriado estadual ou municipal | 0,249 | 0,245 | **0,149** |

No início do mês o acumulado é ruidoso e a projeção linear explode. O modelo pondera o histórico recente e o erro cai pela metade.

## Limitações
- Dados sintéticos. A estrutura de erro real pode ter mais choques (preço, ruptura de estoque, perda de clientes grandes).
- Os intervalos são marginais por nível e horizonte, não condicionais a cada série.
- Mudanças de carteira (rotatividade) não são modeladas.
- O campeão subestima a tendência (viés de −7%). Nos níveis agregados (empresa, UF), a Catraca e o sazonal ingênuo erram menos. Use a previsão agregada com essa ressalva.
