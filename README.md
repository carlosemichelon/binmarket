# Painel Soja · Júlio de Castilhos / RS

Dashboard interativo de hedge de soja com dados reais CEPEA/Esalq, fundamentos USDA/Conab, multi-ativos e estratégias clássicas.

## 📚 Material teórico (consultor)

Curso de gestão de commodities (31 PDFs) está em `material/` organizado por tópico:

- `01_agronegocio` — fundamentos do agro (5 aulas)
- `02_custos_financeiro` — custos e margens (8 aulas)
- `03_formacao_precos` — PPE, análise fundamentalista/técnica (5 aulas)
- `04_comercializacao` — basis, formas de venda (3 aulas)
- `05_gestao_riscos` — derivativos e opções (8 aulas)
- `06_fertilizantes` — adubos e relação de troca (2 aulas)

**Mapa aula → módulo do painel:** veja `material/INDICE.md`

A metodologia do consultor (Flat Price = Futuro + Prêmio + Câmbio − Logística) é exatamente o modelo dos módulos 01 e 03. Conceitos de basis, análise fundamentalista, margem de contribuição estão embutidos nos módulos correspondentes.

## 🤖 Automação de dados (configuração pendente)

Os arquivos da automação via GitHub Actions já estão prontos no repo:

```
.github/workflows/update-data.yml    ← workflow diário
scripts/update_data.py               ← processador
scripts/requirements.txt
data/cepea/                          ← onde dropar planilhas
```

**Para ativar quando quiser:**

### 1. Subir os arquivos para o GitHub

Crie um **repositório público** no GitHub (ex: `painel-soja`) e suba esta estrutura:

```
painel-soja/
├── index.html                      ← o dashboard
├── .github/
│   └── workflows/
│       └── update-data.yml         ← automação
├── scripts/
│   ├── update_data.py
│   └── requirements.txt
└── data/
    └── cepea/
        └── (planilhas CEPEA aqui)
```

### 2. Ativar o GitHub Pages

No repositório: **Settings → Pages → Source: Deploy from branch → main / (root) → Save**

Após ~1 minuto, seu painel estará em `https://SEU_USUARIO.github.io/painel-soja/`

### 3. Ativar a automação

A automação está em `.github/workflows/update-data.yml`. Já é ativada automaticamente quando você sobe o arquivo no repo. Para confirmar:

- Aba **Actions** do GitHub → deve aparecer o workflow "Atualizar dados"
- Você pode rodá-la manualmente: **Run workflow → Run workflow**
- Cronograma: roda diariamente às **09:00 BRT** (12:00 UTC)

### 4. Dar permissão de escrita ao workflow

GitHub bloqueia escritas automáticas por padrão. Habilite:

**Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save**

Sem isso, o workflow não consegue fazer commit das atualizações.

---

## 📊 O que é atualizado automaticamente

| Fonte | Frequência | Como funciona |
|---|---|---|
| **USD/BRL (dólar atual)** | Diário | API pública BCB SGS — não falha |
| **CDI anual** | Diário | API pública BCB SGS — recalcula composto |
| **IPCA anual** | Diário | API pública BCB SGS — recalcula composto |
| **Timestamp do painel** | Diário | Data automática |
| **CEPEA Paranaguá (soja)** | Quando você sobe planilha | Veja abaixo |
| **CEPEA Campinas (milho)** | Quando você sobe planilha | Veja abaixo |

## 🔄 Atualizando as séries CEPEA

CEPEA não tem API aberta — eles bloqueiam scraping. Mas o fluxo é simples:

1. Acesse `cepea.org.br/br/indicador/series/soja.aspx?id=92` (ou milho id=77)
2. Clique em "Indicador" → exporta o `.xls`
3. Renomeie ou mantenha o nome (não importa) e jogue dentro de `data/cepea/`
4. Faça `git add` e `git commit` (ou suba pela interface web do GitHub)
5. Na próxima execução do workflow (ou rodando manual em **Actions**), o painel será atualizado

**Dica:** uma vez por semana já é suficiente — os dados de soja mudam aos pequenos solavancos diariamente, mas os trimestres consolidados não.

## 🛠 Atualizando manualmente (sem esperar o cron)

Aba **Actions** → "Atualizar dados" → **Run workflow** → Run.

Em ~1 minuto, se houver mudança, um commit aparece no repo e o painel atualiza no GitHub Pages.

## ⚠️ Fontes manuais (sem automação)

Estas fontes ficam congeladas até você (ou eu) atualizar manualmente no `index.html`:

- **USDA WASDE** (módulo 09 mundial) — atualiza mensalmente, 2ª quinta-feira
- **Conab Brasil** (módulo 09 BR) — atualiza mensalmente
- **NESPRO/UFRGS** (boi gordo RS) — semanal
- **Cotrijuc balcão** — editável direto no painel (campo de input)
- **Ouro / cobre** (módulo 08) — anual

Para integrar essas, mande o release/planilha aqui que eu atualizo, ou aprendemos juntos como buscar via API.

## 🧪 Testando localmente (opcional)

```bash
cd painel-soja
pip install -r scripts/requirements.txt
python scripts/update_data.py
```

O script imprime o que foi atualizado e modifica o `index.html` no lugar. Para reverter: `git checkout index.html`.

## 🐛 Debugging

Se o workflow falhar:

1. Aba **Actions** → clique na execução com X vermelho
2. Veja o log do step "Executar atualizador"
3. Erros comuns:
   - **Permissão negada no commit** → veja item 4 do setup
   - **BCB SGS timeout** → próxima execução resolve
   - **Falha conversão xls** → planilha CEPEA mal-formada, baixe de novo

## 📜 Licença

Uso pessoal. Dados de fontes públicas (CEPEA-Esalq/USP, BCB, USDA, Conab, NESPRO/UFRGS, Banco Mundial).
