# SETUP GITHUB — Painel Soja JC

Passo-a-passo para colocar no ar e ativar a atualização automática.

## 1. Criar repositório GitHub

1. Vá em https://github.com/new
2. Nome sugerido: `painel-soja` (ou outro)
3. **Public** (necessário para GitHub Pages gratuito)
4. NÃO marcar "Initialize with README" (já temos)
5. Criar

## 2. Subir os arquivos

No terminal do seu computador:

```bash
cd ~/Downloads        # ou onde você descompactou
unzip painel-soja-repo.zip
cd repo

git init
git add .
git commit -m "Inicial · painel soja JC"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/painel-soja.git
git push -u origin main
```

Substitua `SEU_USUARIO` pelo seu username GitHub.

## 3. Ativar GitHub Pages (publicar o painel)

1. Repositório → **Settings** → **Pages** (menu lateral)
2. Source: **Deploy from a branch**
3. Branch: **main** · Folder: **/ (root)**
4. **Save**
5. Aguarde 1-2 minutos. URL será: `https://SEU_USUARIO.github.io/painel-soja/`

## 4. Ativar GitHub Actions (atualização automática)

1. Repositório → **Settings** → **Actions** → **General**
2. Em "Workflow permissions": marque **Read and write permissions**
3. Em "Actions permissions": **Allow all actions and reusable workflows**
4. **Save**

5. Aba **Actions** (no topo do repo)
6. Você verá "Atualizar dados" — clique nele
7. **Run workflow** → **Run workflow** (botão verde)
8. Aguarde 1-2 min. Se aparecer ✓ verde, está funcionando.

A partir daí, roda diariamente às 12:00 UTC (09:00 BRT) automaticamente.

## 5. O que será atualizado automaticamente

| Fonte | Frequência | API |
|---|---|---|
| **USD/BRL** | Diário | BCB SGS série 1 |
| **CDI** | Diário (anualizado) | BCB SGS série 12 |
| **IPCA** | Mensal | BCB SGS série 433 |
| **Selic** | Diário | BCB SGS série 4189 |
| **SIDRA Produtividade JC** | Anual (set/out) | apisidra.ibge.gov.br tabela 1612 |
| **CEPEA** | Diário (se você anexar .xls em `data/cepea/`) | manual upload + parse automático |

## 6. O que continua MANUAL (por enquanto)

| Fonte | Como atualizar |
|---|---|
| **CBOT futuros** | Edite `index.html` → state `cbotSoja` (módulo 03 curva) |
| **Prêmio Paranaguá** | Edite state `premio` no módulo 01 |
| **WASDE USDA** | Baixe PDF mensal → edite `USDA_HISTORICO` (linha ~225) |
| **Conab BR** | Edite `CONAB_HISTORICO` |
| **ANEC embarques** | Edite `ANEC_EXPORT_PADRAO` |
| **Conab custos** | Coloque Excel em `data/conab/` |
| **Emater RS** | Edite 2025-2026 em `PRODUTIVIDADE_JC` |

O **Módulo 16 do painel** (Atualização de dados) tem checklist em tempo real mostrando idade de cada fonte e link direto para a oficial. Use ele como guia mensal.

## 7. Fluxo recomendado para você

**Semanal (5 min):**
- Abre o painel → módulo 16
- Verifica linhas vermelhas (atrasadas)
- Atualiza CBOT/prêmio se mexeu muito

**Mensal (15 min):**
- WASDE sai dia ~10 do mês → atualiza estoques USA/mundo
- Conab BR sai dia ~10 → atualiza produção BR
- ANEC libera mensal dia ~5 → embarques

**Anual (1h em set/out):**
- SIDRA publica PAM ano anterior
- Workflow vai pegar sozinho da próxima rodada
- Você só confere

## 8. Como atualizar CEPEA manualmente

CEPEA não tem API pública direta. O processo:

1. Vá em https://www.cepea.esalq.usp.br/br/indicador/series/soja.aspx
2. Selecione "Paranaguá" · período desejado (até 12 meses por vez)
3. Baixe a planilha (.xls)
4. Copie o arquivo para `data/cepea/` no seu repo
5. Commit + push
6. GitHub Actions vai rodar e processar automático

## Troubleshooting

**Workflow falhou?**
- Verifique se as permissões "Read and write" foram salvas (passo 4)
- Veja log do erro na aba Actions

**Site não atualiza após push?**
- GitHub Pages demora ~1 min após push
- Force refresh com Ctrl+Shift+R no navegador
- Veja status em Settings → Pages

**SIDRA falha?**
- API SIDRA tem limite de requisições. Workflow tem retry automático.
- Pode tentar manualmente na URL: https://apisidra.ibge.gov.br/values/t/1612/n6/4311205/v/214/p/all/c81/2713

**Dúvidas?**
- Cada script tem comentários inline explicando o que faz
- O Módulo 16 do painel é seu guia visual
