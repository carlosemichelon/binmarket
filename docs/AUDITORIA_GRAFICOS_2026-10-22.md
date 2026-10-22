# BinMarket — auditoria dos gráficos e das premissas
Data: 22/10/2026 (America/Sao_Paulo)

## Escopo e critérios
Foram inventariadas as 18 instâncias JSX de LineChart, BarChart e ComposedChart presentes em `index.html`, inclusive os componentes auxiliares do módulo 13. O componente `FonteJuntoGrafico` aparece em 18 pontos após a revisão. Cada link é uma **fonte de consulta e comparação**, não uma certificação de que a curva plotada foi coletada em tempo real. As páginas CME e B3 de referência de contratos foram examinadas; a checagem direta da publicação GitHub Pages não foi possível no ambiente desta auditoria. A validação estática de JSX depende do workflow GitHub Actions.

| Nº | Módulo / gráfico | Origem e tratamento | Estado de atualização | Link de conferência |
|---:|---|---|---|---|
| 1 | 01 — Cenário e projeção de componentes | CBOT, câmbio, prêmio/frete editável e metas do usuário | **Simulação** sobre dados e premissas | CME / CEPEA |
| 2 | 02 — Evolução histórica do custo e preços | Histórico trimestral compilado `HISTORICO_CALC` | **Compilado**, não atualizado trimestralmente | Conab |
| 3 | 04 — Curva soja CBOT | `CURVA_SOJA` com vencimentos e preços exemplificativos | **Exemplo estático 2026/27** | CME soja |
| 4 | 04 — Curva UME/MFC de fertilizantes | `FERT_CURVA_EXEMPLO` unindo eixos de tempo | **Exemplo estático**; não são ajustes CME | CME UME / MAP Brasil |
| 5 | 06 — Comparador de estratégias | `simulacao.janela` sobre preço histórico estimado JC | **Simulador retrospectivo**, não negócio realizado | CEPEA |
| 6 | 10 — Histórico de preços e índices | `HISTORICO_CALC` com CEPEA e aproximações | **Compilação histórica** | CEPEA |
| 7 | 11 — Índices sazonais | `SAZONAL` derivado de base histórica | **Sazonalidade fixa**, não previsão | CEPEA |
| 8 | 11 — Fertilizantes sazonais | `SAZONAL_FERT` modelado | **Série ilustrativa/compilada** | CME fertilizantes |
| 9 | 12 — Produção mundial USDA | `USDA_WORLD` série inserida no código | **Compilação não sincronizada com PSD** | USDA PSD |
| 10 | 12 — Estoque/uso mundial | `USDA_WORLD`, cálculo e séries no código | **Compilado**, não feed global ao vivo | USDA PSD |
| 11 | 12 — Produção Brasil Conab | `conabSerieAuto || CONAB_BR` | **CSV automático quando disponível**; fallback estático | Conab |
| 12 | 12 — PSD Brasil/EUA | `usdaBrasilAuto` | **CSV automático** por ano USDA | USDA PSD |
| 13 | 12 — Embarques ANEC | `ANEC_EXPORT_PADRAO` | **Compilação / cenário** | ANEC |
| 14 | 13 — Comparação multicommodities | `HISTORICO_MULTI_CUSTOM` índices base 100 | **Compilado com proxies** | CEPEA / BCB |
| 15 | 13 — Custos e inflação (base 100) | Série `data` do bloco `CustosBloco` | **Compilação e referências estimadas** | Conab |
| 16 | 13 — Produtividade e rentabilidade | `data` do bloco de produtividade | **Produtividade de referência; margem simulada** | IBGE PAM |
| 17 | 13 — Rentabilidade acumulada | Somatório da simulação financeira `data` | **Modelo hipotético**, não balanço real | IBGE PAM / CEPEA |
| 18 | 13 — Custo/CBOT | `dadosAnuais` valores e razões calculadas | **Elaboração própria histórica** | Conab / CME |

## Observações obrigatórias
1. Coleta automática do prêmio **Paranaguá/PR** foi adicionada em `data/fontes/mercado.json`, com data de apuração e contratos por vencimento. Ela não define o prêmio **Rio Grande/RS** nem o preço contratado em Júlio de Castilhos.
2. O coletor CBOT monitora o contrato próximo, não alimenta todos os vencimentos da curva de exemplo.
3. Os rótulos UME e MFC remetem aos produtos CME de ureia granular FOB Oriente Médio e MAP CFR Brasil; as curvas do painel continuam estáticas.
4. Os limites e percentuais de proteção do módulo 05 são **heurísticas configuradas**, não sinais estatisticamente validados nem recomendação de percentual de safra física.
5. A calculadora de hedge de soja na B3 deve usar **SJC: 450 sacas de 60 kg, cotação em US$/saca**. O valor nocional em reais é apenas conversão hipotética, não preço físico local fixo.
6. Put e collar protegem o derivativo subjacente e podem deixar riscos de prêmio físico (basis), frete, moeda, custo da opção e execução.
7. Em three-way, a put adicional vendida limita a proteção de queda abaixo do strike inferior; prêmios de opções exibidos são cenários editáveis, não opções precificadas automaticamente.
8. A última auditoria consultada tinha 8 fontes automáticas dentro da tolerância e 9 grupos sem cobertura integral. A idade de cada dado deve ser calculada pela data da fonte, não só pela data do workflow.

## Conclusão de QA
**Verificado no código do repositório:** preservação dos 17 módulos, presença de 18 chamadas a `FonteJuntoGrafico`, correções de rótulos financeiros e divulgação das limitações de atualização. **Não verificado aqui:** screenshot e navegação interativa do site Pages em desktop/mobile, último resultado da execução do workflow após os commits de auditoria, checagem de todas as URLs em navegador e fidelidade estatística das séries históricas compiladas. Não declarar conclusão funcional 100% antes desses testes.

Links oficiais centrais:
- B3 SJC: https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/commodities/ficha-do-produto-8AA8D0CC95C8AC5601961606A59A4AD3.htm
- CME soja: https://www.cmegroup.com/markets/agriculture/oilseeds/soybean
- CME ureia: https://www.cmegroup.com/markets/agriculture/fertilizer/urea-granular-fob-middle-east/settlements
- CME MAP: https://www.cmegroup.com/markets/agriculture/fertilizer/map-cfr-brazil/settlements
