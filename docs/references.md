# Referências

Base científica e de mercado das escolhas do projeto. Todas as citações foram conferidas em fontes
bibliográficas (DOI, RePEc, editoras ou repositórios dos autores).

## Previsão de vendas e avaliação
- Makridakis, S., Spiliotis, E. & Assimakopoulos, V. (2022). M5 accuracy competition: Results, findings, and conclusions. *International Journal of Forecasting*, 38(4), 1346–1364. Usado em: LightGBM global como modelo principal. No M5, métodos de ML superaram os estatísticos pela primeira vez, e os melhores colocados usaram LightGBM.
- Makridakis, S., Spiliotis, E., Assimakopoulos, V., Chen, Z., Gaba, A., Tsetlin, I. & Winkler, R. L. (2022). The M5 uncertainty competition: Results, findings and conclusions. *International Journal of Forecasting*, 38(4), 1365–1385. Usado em: previsões probabilísticas avaliadas por perda pinball.
- Wickramasuriya, S. L., Athanasopoulos, G. & Hyndman, R. J. (2019). Optimal forecast reconciliation for hierarchical and grouped time series through trace minimization. *Journal of the American Statistical Association*, 114(526), 804–819. Usado em: reconciliação MinT-shrink. Garante que as metas de representante, supervisor, coordenador e UF somem a mesma meta da empresa.
- Hyndman, R. J. & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22(4), 679–688. Usado em: MASE.
- Romano, Y., Patterson, E. & Candès, E. J. (2019). Conformalized quantile regression. *NeurIPS 32*. Usado em: intervalos P10–P90 por calibração conformal.
- Fildes, R., Goodwin, P., Lawrence, M. & Nikolopoulos, K. (2009). Effective forecasting and judgmental adjustments. *International Journal of Forecasting*, 25(1), 3–23. Usado em: por que as metas partem de uma previsão estatística e não de ajustes de julgamento, que tendem a ser otimistas.
- Hyndman, R. J. & Athanasopoulos, G. (2021). *Forecasting: Principles and Practice* (3ª ed.). OTexts. Usado em: validação com origem móvel, baselines ingênuos e ETS.
- Nixtla: [mlforecast](https://github.com/Nixtla/mlforecast), [statsforecast](https://github.com/Nixtla/statsforecast) e [hierarchicalforecast](https://github.com/Nixtla/hierarchicalforecast).
- Kaggle: [M5 Forecasting – Accuracy](https://www.kaggle.com/competitions/m5-forecasting-accuracy), com 1º lugar em LightGBM, e [Corporación Favorita](https://www.kaggle.com/competitions/favorita-grocery-sales-planning-analytics), cujas variáveis de promoção influenciaram as variáveis de campanha.

## Metas e remuneração da força de vendas
- Weitzman, M. L. (1980). The "ratchet principle" and performance incentives. *Bell Journal of Economics*, 11(1), 302–308. Usado em: diagnóstico da regra legada. Quando a meta usa o desempenho passado, quem supera é punido com uma meta maior.
- Gonik, J. (1978). Tie salesmen's bonuses to their forecasts. *Harvard Business Review*, 56(3), 116–123. Usado em: extensão discutida, em que o vendedor é premiado pela precisão da própria previsão.
- Mantrala, M. K., Sinha, P. & Zoltners, A. A. (1994). Structuring a multiproduct sales quota-bonus plan for a heterogeneous sales force. *Marketing Science*, 13(2), 121–144.
- Zoltners, A. A., Sinha, P. & Lorimer, S. E. (2006). *The Complete Guide to Sales Force Incentive Compensation*. AMACOM. Usado em: metas justas por território e potencial.
- Chung, D. J., Steenburgh, T. & Sudhir, K. (2014). Do bonuses enhance sales productivity? A dynamic structural analysis of bonus-based compensation plans. *Marketing Science*, 33(2), 165–187. Usado em: metas atingíveis e bônus periódicos como "marcapasso".
- Efron, B. & Morris, C. (1975). Data analysis using Stein's estimator and its generalizations. *JASA*, 70(350), 311–319. Usado em: shrinkage para separar habilidade de sorte.
- Gelman, A. & Hill, J. (2007). *Data Analysis Using Regression and Multilevel/Hierarchical Models*. Cambridge University Press. Usado em: modelo de efeitos mistos.

## Campanhas e inferência causal
- Callaway, B. & Sant'Anna, P. H. C. (2021). Difference-in-differences with multiple time periods. *Journal of Econometrics*, 225(2), 200–230. Usado em: DiD escalonado com controles ainda não tratados.
- van Heerde, H. J., Leeflang, P. S. H. & Wittink, D. R. (2004). Decomposing the sales promotion bump with store data. *Marketing Science*, 23(3), 317–334. Usado em: antecipação de compras (efeito no período seguinte).
- Brodersen, K. H., Gallusser, F., Koehler, J., Remy, N. & Scott, S. L. (2015). Inferring causal impact using Bayesian structural time-series models. *Annals of Applied Statistics*, 9(1), 247–274. Usado em: alternativa discutida para séries agregadas.

## Dashboards, dados públicos e Engenharia de Produção
- Eckerson, W. W. (2010). *Performance Dashboards: Measuring, Monitoring, and Managing Your Business* (2ª ed.). Wiley. Usado em: painéis operacional, tático e estratégico por público.
- Few, S. (2006). *Information Dashboard Design*. O'Reilly. Usado em: um painel por decisão, poucos KPIs e sem decoração.
- Kimball, R. & Ross, M. (2013). *The Data Warehouse Toolkit* (3ª ed.). Wiley. Usado em: modelo dimensional e camada semântica única.
- Gama, J. et al. (2014). A survey on concept drift adaptation. *ACM Computing Surveys*, 46(4). Usado em: monitoramento do erro como detector de drift.
- IBGE: [API de Localidades](https://servicodados.ibge.gov.br/api/docs/localidades) e SIDRA ([tabela 6579](https://sidra.ibge.gov.br/tabela/6579), população; [tabela 5938](https://sidra.ibge.gov.br/tabela/5938), PIB dos municípios).
- Feriados: pacote [`holidays`](https://github.com/vacanza/holidays) (nacionais e estaduais) e [joaopbini/feriados-brasil](https://github.com/joaopbini/feriados-brasil) (municipais, licença MIT).
- Coordenadas: [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (licença MIT).
