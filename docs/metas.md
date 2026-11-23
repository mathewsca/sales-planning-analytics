# Métodos de cálculo de metas

## O problema da regra antiga
A meta mensal de cada representante era (1 + 10%) × máx(venda do mesmo mês do ano anterior, média dos
últimos 3 meses). A regra é simples e intuitiva, mas tem três defeitos conhecidos:

1. **Efeito catraca** (Weitzman, 1980): o desempenho de hoje vira a meta de amanhã. Quem supera a meta é
   "punido" com uma meta maior, e o máx(·) só deixa a meta subir. O resultado previsível é a maioria da
   equipe abaixo de 100% na maior parte dos meses.
2. **Ignora o território:** dois representantes com o mesmo histórico recebem a mesma meta, mesmo que um
   atenda municípios em crescimento e o outro um território saturado.
3. **Ignora o calendário:** um mês com feriado municipal tem menos dias de venda naquele território.

## Os quatro métodos comparados
Para cada mês do backtest, a meta é definida **só com a informação disponível no fim do mês anterior**
(previsão h = 1 e desempenho estimado até o corte) e depois confrontada com o realizado.

| Método | Fórmula | Fundamento |
|---|---|---|
| **Legado** | (1 + 10%) × máx(ano anterior, média 3m) | prática comum, efeito catraca |
| **Previsão** | P50 da previsão reconciliada × (1 + esticamento) | a meta parte do que é **esperado**, não do que já foi feito (Fildes et al., 2009) |
| **Potencial** | venda esperada do **território** (IBGE + carteira) × habilidade^θ, escalada para a meta da empresa | metas por potencial (Zoltners, Sinha & Lorimer, 2006); θ decide quanto da habilidade comprovada entra na meta |
| **Probabilidade** | quantil da previsão probabilística com P(atingir) = alvo | metas desafiadoras, mas atingíveis (Chung, Steenburgh & Sudhir, 2014) |

A **meta da empresa** é a mesma para os métodos "potencial" e "previsão" (5% acima da previsão total).
Como a previsão é reconciliada (MinT), a soma das metas individuais fecha com a meta da empresa.

## Critérios
- **Atingibilidade:** % de representantes que batem a meta e atingimento mediano.
- **Justiça territorial:** correlação de Spearman entre o atingimento e o potencial do território. Perto de 0
  significa que o tamanho do território não decide quem bate a meta.
- **Dispersão:** intervalo interquartil do atingimento.
- **Custo do prêmio** (plano ilustrativo: 3% da venda ao bater a meta + 2% sobre o excedente, até 150%), em %
  da venda.
- **Oráculo** (só nos relatórios de validação): correlação entre o atingimento e a habilidade **real**. Uma meta
  justa premia habilidade, não território.

## Política de escolha (definida antes dos resultados)
Entre os métodos em que **40% a 70%** dos representantes batem a meta (atingível, mas desafiadora),
escolher o de menor |correlação com o território|. Em caso de empate, o de menor custo.

## Resultados
Simulação nos 8 meses do backtest: cada meta é definida com a informação do fim do mês anterior e confrontada com o realizado.

| Método | % que bate a meta | Atingimento mediano | Correlação com o território | Correlação com a **habilidade real** (oráculo) | Custo do prêmio (% da venda) |
|---|---|---|---|---|---|
| **Legado (catraca)** | **17%** | 74% | 0,01 | 0,04 | 0,7% |
| Previsão (P50 + 5%) | 51% | 101% | −0,05 | 0,02 | 2,0% |
| **Probabilidade de atingir = 50%** ✅ | 57% | 105% | −0,03 | −0,01 | 2,3% |
| Potencial IBGE × habilidade⁰ | 49% | 100% | −0,27 | **0,53** | 2,0% |
| Potencial IBGE × habilidade⁰·⁵ | 51% | 101% | −0,22 | 0,36 | 2,0% |

- **A regra antiga fica, em média, 44% acima do que a previsão indica**, e só 17% da equipe bate a meta: é o efeito catraca, medido.
- A política definida **antes** dos resultados (entre 40% e 70% batendo a meta, escolher o mais neutro ao território) escolheu a meta por **probabilidade de atingir = 50%**.
- **Achado:** as metas por previsão são atingíveis e neutras ao território, mas **não premiam habilidade**. A previsão aprende o nível de cada representante, então os melhores recebem metas maiores, uma "catraca disfarçada". As metas por **potencial do território** premiam habilidade (correlação de 0,53 com a verdade), mas herdam o erro de medir o potencial. O caminho natural é um **híbrido**: âncora no potencial IBGE e calibração pela previsão.

## Meta diária
A meta mensal é distribuída pelos **dias úteis da carteira do representante** (média dos calendários
municipais ponderada pelo nº de clientes): sábado = 0,5, e domingo e feriados (inclusive municipais) = 0.
No mês corrente, "venda necessária por dia útil" = (meta − realizado) ÷ dias úteis restantes.

## Vendedores internos e campanhas
- A meta do vendedor interno nas campanhas era fixa em 20% da meta do representante. Ela é mantida como
  referência no dashboard e agora pode ser comparada com a participação real do canal interno.
- **Meta de campanha proposta** = linha de base dos SKUs (média dos 3 meses anteriores) × (1 + efeito causal
  estimado para o tipo de campanha). Substitui o "+30% sobre o histórico", que ignorava que as campanhas vão
  para itens de giro lento e que parte do efeito é só antecipação.

## Limitações e extensões
- A simulação não modela a **resposta comportamental** às metas (esforço, *sandbagging*). Com dados reais de
  vários ciclos, a extensão natural é um modelo estrutural (Chung, Steenburgh & Sudhir, 2014).
- **Esquema de Gonik (1978):** o representante informa a própria previsão e o prêmio é maior quando ele acerta.
  Isso incentiva a revelar informação de campo. É uma extensão possível: a previsão do modelo vira a âncora e a
  do representante, um ajuste auditável.
