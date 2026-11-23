# Data card: vendas sintéticas de um atacado distribuidor + dados públicos

## Origem e privacidade
- **Vendas, equipe, clientes, produtos, campanhas e metas: 100% sintéticos.** Nenhum registro, nome, documento, código ou valor real é usado ou publicado.
- **Dados públicos reais:** municípios, população e PIB (IBGE) e feriados. Eles descrevem a geografia, não a empresa.
- **Dados gerados:**
  - IDs aleatórios e não sequenciais, com quantidade de dígitos própria (cliente com 10, produto com 9, representante com 7...).
  - Pessoas geradas como "Nome + inicial" (Faker pt_BR). Clientes têm razão social fictícia composta.
  - Fornecedores aparecem só como "Fornecedor 01–24" e produtos só por código e linha (A–H).
  - Geografia: municípios do Centro-Oeste e do Tocantins. Calendário: fev/2023 a fev/2026.
  - Valores monetários com perturbação aleatória de ±1–5% por linha.
- Empresa fictícia.

## Dados públicos (snapshot versionado em `data/public/`, coleta em `_metadata.json`)
| Arquivo | Fonte | Observações |
|---|---|---|
| `municipios.csv` | IBGE Localidades + SIDRA 6579 (população 2025) + SIDRA 5938 (PIB 2023) + coordenadas (kelvins, MIT) | 607 municípios (GO, MT, MS, DF, TO). Um município criado depois de 2023 (MT) ainda sem PIB publicado teve o PIB per capita imputado pela mediana da região imediata (`pib_imputado = true`). |
| `feriados_nacionais_estaduais.csv` | pacote `holidays` (Python) | Inclui feriados móveis (Sexta-feira Santa, Corpus Christi). |
| `feriados_municipais.csv` | joaopbini/feriados-brasil (MIT) | **Cobertura parcial:** 364 de 607 municípios. O teste dbt `warn_cobertura_feriados_municipais` lista os municípios atendidos sem feriado municipal na base aberta. Para esses, o calendário considera só os feriados nacionais e estaduais. |

## Mecanismo gerador (verdade conhecida)
1. **Potencial municipal:** `população^0,85 × PIB per capita^0,6` (modelo gravitacional). Os clientes se distribuem conforme esse potencial. Municípios longe das filiais tendem a não ser atendidos, o que alimenta o mapa de oportunidades.
2. **Pedidos do cliente no mês:** Poisson(taxa do cliente × **habilidade latente do representante** × sazonalidade × tendência × **dias úteis do município**).
3. **Dia do pedido:** peso do dia da semana. Feriados nacionais, estaduais e municipais zeram o dia. A véspera de feriado tem +25% (antecipação) e a ponte −50%.
4. **Escolha do SKU:** popularidade × (1 + incremento) se o SKU está em campanha. No mês seguinte há uma queda proporcional ao incremento (antecipação de compras).
5. **Campanhas:** 4–5 por mês, de um fornecedor. **Preferem SKUs de giro lento** (viés de seleção). Tipos: F (R$), Q (unidades) e V (positivação).
6. **Metas legadas:** (1+10%) × máx(mesmo mês do ano anterior, média de 3 meses). É a regra da catraca, que mantém o atingimento mediano abaixo de 100%.
7. **Devoluções:** cerca de 0,2% das linhas, lançadas como negativas dias depois.
8. **Cenário de choque** (`--scenario shock`): retração de 28% no MT a partir de dez/2025, para demonstrar a detecção de drift.

A verdade do gerador (potencial, habilidade, incremento das campanhas) fica em `data/ground_truth/`, fora do git e do warehouse. Ela é usada só como **oráculo** nos relatórios de validação.

## Volumes (cenário base)
6 filiais · 5 coordenadores · 15 supervisores · ~140 representantes · 16 vendedores internos · 6.000 clientes · 2.500 SKUs · 24 fornecedores · ~150 campanhas · ~1,37 milhão de itens vendidos.

## Limitações
- Sem rotatividade da equipe nem mudança de carteira ao longo do tempo.
- A resposta da equipe às metas não é modelada: o esforço não muda com a meta. Por isso a simulação compara justiça e alcance das metas, mas não captura o efeito motivacional (Chung, Steenburgh & Sudhir, 2014).
- Feriados municipais com cobertura parcial na fonte aberta.
