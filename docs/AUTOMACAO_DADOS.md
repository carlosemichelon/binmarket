# Automação e integridade de dados — BinMarket

## O que é automático

- **Gado NESPro**: verificação duas vezes ao dia em `update-bovinos.yml`; publica `data/bovinos/historico.csv`. O NESPro publica semanalmente, portanto a verificação diária não produz cotações novas diariamente.
- **Soja (BCB, SIDRA, CEPEA republicado/CBOT)**: rotina diária existente `update-data.yml`; atualiza `index.html` quando as fontes públicas e os padrões de leitura funcionam.
- **CEPEA Paranaguá**: `update-market-sources.yml` tenta a página oficial duas vezes ao dia e preserva série diária incremental em `data/fontes/cepea_soja.csv`.
- **Conab — soja / safra**: baixa o arquivo oficial `SojaSerieHist.xls` sem importação humana. Este arquivo é de *safra*, **não** de custos de produção. Por ora, a planilha baixada é armazenada para posterior transformação validada; os números de custo do simulador não são substituídos automaticamente.
- **USDA — PSD soja**: baixa o dataset público completo (sem chave), extrai séries de Brasil e EUA por safra e atributo, e escreve `data/fontes/usda_soja.csv`. Não substitui os agregados globais do gráfico sem confirmação de comparabilidade.

## O que NÃO pode ser chamado de 100% atualizado

Dados ilustrativos, premissas e preços locais sem fonte pública confiável — por exemplo: custos detalhados de propriedade, frete contratual, prêmio na praça local, preços de veículos, séries históricas reconstruídas de commodities e estimativas do simulador. São cenários editáveis, não cotações de mercado verificadas. Para transformá-los em dados reais é necessário identificar uma fonte reproduzível específica para cada conceito e validar as unidades. O painel mostra essa distinção no botão "Fontes de dados".

## Garantias de integridade

- Cada fonte é atualizada de forma independente e um erro não elimina o último CSV válido.
- Na coleta com falha, o arquivo de status registra `falha`; a execução GitHub Actions falha visivelmente.
- O manifest registra separadamente `verificado_em` e `data_referencia` — executar script **não significa** cotação nova.
- Atualizações agendadas no GitHub não têm SLA: podem atrasar; terceiros podem ficar indisponíveis ou alterar a estrutura do site.
- O dashboard possui indicador de estado consultando `data/fontes/mercado.json` e `data/bovinos/atualizacao.json` sem cache.

## Onde acompanhar

- https://github.com/carlosemichelon/binmarket/actions/workflows/update-data.yml
- https://github.com/carlosemichelon/binmarket/actions/workflows/update-bovinos.yml
- https://github.com/carlosemichelon/binmarket/actions/workflows/update-market-sources.yml
