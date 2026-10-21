# Atualização automática — Gado de corte BinMarket

Fonte: https://bovinos-indices.nesproufrgs.com/ — NESPro/UFRGS (preços semanais do Rio Grande do Sul, R$/kg).

O GitHub Actions executa .github/workflows/update-bovinos.yml diariamente às 08h15 e 19h35 (horário de Brasília, UTC−3). Agendamentos podem atrasar ou falhar. Também é possível executar manualmente pela aba Actions.

O programa scripts/update_bovinos.py primeiro lê a página NESPro em HTML e usa navegador Chromium/Playwright caso o conteúdo seja carregado por JavaScript. A rotina só grava cotações com data e valores válidos. Os novos registros são combinados aos antigos, preservando campos ausentes; não estima preços não publicados.

O histórico oficial fica em data/bovinos/historico.csv e a última checagem bem-sucedida em data/bovinos/atualizacao.json. A página bovinos.html lê o CSV publicado em cada visita. Importações manuais dos visitantes continuam locais.

Se o NESPro estiver inacessível ou alterar o formato, o job falha visivelmente em GitHub Actions sem apagar dados antigos. A data da última cotação permanece visível. Uma checagem não significa que tenha ocorrido nova coleta.

Verificar execuções: https://github.com/carlosemichelon/binmarket/actions/workflows/update-bovinos.yml

Limitações: a integração depende da estrutura pública do painel; não existe contrato de API verificado para este projeto. Não inclui ovinos nem preços de varejo.

Soja: o workflow existente .github/workflows/update-data.yml permanece sem alterações. Ele atualiza dados de BCB; preços CEPEA ainda dependem das planilhas importadas no processo anterior. As melhorias de PROXIMA_SESSAO.md não foram implementadas.
