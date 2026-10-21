# Base de dados — Gado de corte · RS

Fonte: **NESPro/UFRGS**, https://bovinos-indices.nesproufrgs.com/ , consulta em 21/10/2026.

`nespro_2026-10-14.csv` guarda **as oito datas semanais** mostradas na tabela pública do painel NESPro, entre 26/08/2026 e 14/10/2026, para PV macho/fêmea, terneiro e novilho. A última linha inclui também preços de PC macho/fêmea e categorias de reposição exibidos no painel para 14/10/2026. Células vazias significam **não verificado/não disponível**, nunca zero. Não se deve ligar os valores de 2010–2026 de `data/base/csv/03_historico_boi.csv` a essa série: aquele arquivo é um histórico agregado de outra metodologia, não observações semanais NESPro.

Valores em **R$/kg**. PV = peso vivo; PC = peso de carcaça. As relações de troca são calculadas com pesos editáveis, inicialmente boi gordo 480 kg, terneiro 180 kg e novilho 300 kg, parâmetros explicativos adotados pelo painel de referência.

## Ampliar a base

Na aba `bovinos.html`, clique **Importar CSV** para carregar outras semanas reais. A aplicação aceita CSV no formato acima (`;` + vírgula decimal), um formato largo equivalente ou um formato longo `data;categoria;preco`. A importação preserva campos anteriores vazios, guarda a base expandida no localStorage **somente no navegador usado** e pode ser exportada novamente. Para tornar uma série histórica **compartilhada com todos** no GitHub Pages, atualize `nespro_2026-10-14.csv` e os dados iniciais em `assets/bovinos.js` mediante curadoria, ou adicione um script de build posterior.

**Sem atualização automática do NESPro nesta versão.** Não foi confirmada uma API pública ou URL estável de download automático. A data da coleta é exibida separadamente da data do acesso. Séries de varejo e ovinos do site de referência não foram importadas para a aba exclusiva de gado de corte.

## Limites

- A base inicial de oito semanas não permite análises sazonais, médias históricas multianuais, ou previsões de preços.
- Preços locais em Júlio de Castilhos podem divergir dos índices do RS; cotar ofertas antes de decidir.
- O simulador é didático e não desconta taxas, impostos, bonificações, financiamento ou risco biológico a menos que incluídos manualmente nos custos.
