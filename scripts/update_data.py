#!/usr/bin/env python3
"""
Atualizador automático do Painel Soja.
Rodado pelo GitHub Actions diariamente.

O que ele faz:
  1. BCB SGS — busca USD/BRL atual, CDI/IPCA anuais (sempre tenta)
  2. CEPEA — processa qualquer arquivo .xls em data/cepea/ (manual upload)
  3. Atualiza timestamp de última atualização no rodapé

Cada fonte é independente — se uma falha, as outras continuam.
"""
from __future__ import annotations

import re
import sys
import json
import subprocess
from datetime import datetime, date
from pathlib import Path
from io import BytesIO

import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
DATA_DIR = ROOT / "data"
CEPEA_DIR = DATA_DIR / "cepea"

BU_PER_SACA = 2.2046


# ===========================================================================
# UTILITÁRIOS
# ===========================================================================

def log(msg: str, ok: bool = True) -> None:
    prefix = "✓" if ok else "✗"
    print(f"{prefix} {msg}", flush=True)


def replace_block(html: str, marker_start: str, marker_end: str, new_content: str) -> tuple[str, bool]:
    """Substitui conteúdo entre dois marcadores. Mantém os marcadores."""
    pattern = re.escape(marker_start) + r"(.*?)" + re.escape(marker_end)
    if not re.search(pattern, html, re.DOTALL):
        return html, False
    new_html = re.sub(pattern, marker_start + new_content + marker_end, html, count=1, flags=re.DOTALL)
    return new_html, True


# ===========================================================================
# FONTE 1 · BCB SGS (USD/BRL, CDI, IPCA, Selic)
# Documentação: api.bcb.gov.br/dados/serie/bcdata.sgs.{id}/dados
# ===========================================================================

BCB_SGS = {
    "usdbrl": 1,        # cotação de venda
    "cdi_diario": 12,   # CDI taxa anualizada base 252 dias úteis
    "ipca_mensal": 433, # IPCA % mensal
    "selic_meta": 432,  # Selic meta anualizada
}


def fetch_bcb_sgs(series_id: int, start_year: int = 2010) -> pd.DataFrame:
    """Busca série temporal do BCB SGS. Retorna DataFrame [data, valor]."""
    url = (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados"
        f"?formato=json&dataInicial=01/01/{start_year}"
    )
    headers = {"User-Agent": "PainelSoja/1.0 (github-actions)"}
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()
    data = r.json()
    if not data:
        return pd.DataFrame(columns=["data", "valor"])
    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"])
    return df


def cdi_acumulado_anual(df_cdi_diario: pd.DataFrame) -> dict[int, float]:
    """Calcula retorno anual composto do CDI por ano civil."""
    # SGS 12 retorna taxa diária em %; converter para fator e compor por ano
    df = df_cdi_diario.copy()
    df["fator"] = 1 + df["valor"] / 100
    df["ano"] = df["data"].dt.year
    return df.groupby("ano")["fator"].prod().subtract(1).to_dict()


def ipca_acumulado_anual(df_ipca_mensal: pd.DataFrame) -> dict[int, float]:
    """Calcula IPCA acumulado anual."""
    df = df_ipca_mensal.copy()
    df["fator"] = 1 + df["valor"] / 100
    df["ano"] = df["data"].dt.year
    return df.groupby("ano")["fator"].prod().subtract(1).to_dict()


def update_dolar_atual(html: str) -> tuple[str, bool, str]:
    """Atualiza o valor inicial de `useState(X)` para USD/BRL."""
    try:
        df = fetch_bcb_sgs(BCB_SGS["usdbrl"], start_year=2025)
        if df.empty:
            return html, False, "BCB SGS retornou vazio"
        latest = df.iloc[-1]
        valor = round(float(latest["valor"]), 2)
        data_str = latest["data"].strftime("%d/%m/%Y")

        # Substitui: const [dolar, setDolar] = useState(X.XX);
        new_html, n = re.subn(
            r"(const \[dolar, setDolar\] = useState\()[\d.]+(\);)",
            rf"\g<1>{valor}\g<2>",
            html,
            count=1,
        )
        if n == 0:
            return html, False, "padrão dolar não encontrado"
        log(f"USD/BRL atualizado: R$ {valor} ({data_str})")
        return new_html, True, f"R$ {valor} em {data_str}"
    except Exception as e:
        log(f"USD/BRL falhou: {e}", ok=False)
        return html, False, str(e)


def update_macro_anual(html: str) -> tuple[str, bool]:
    """Atualiza CDI e IPCA anuais no objeto MACRO_ANUAL."""
    try:
        cdi_df = fetch_bcb_sgs(BCB_SGS["cdi_diario"], start_year=2010)
        ipca_df = fetch_bcb_sgs(BCB_SGS["ipca_mensal"], start_year=2010)
        cdi_anual = cdi_acumulado_anual(cdi_df)
        ipca_anual = ipca_acumulado_anual(ipca_df)

        # Para cada ano presente em MACRO_ANUAL, substituir cdi e ipca
        def update_year(match: re.Match) -> str:
            ano = int(match.group(1))
            ouro = match.group(2)
            cobre = match.group(3)
            cdi_old = match.group(4)
            ipca_old = match.group(5)
            custo = match.group(6)
            cdi_new = round(cdi_anual.get(ano, float(cdi_old)), 4)
            ipca_new = round(ipca_anual.get(ano, float(ipca_old)), 4)
            return (
                f"  {ano}: {{ ouro: {ouro}, cobre: {cobre}, "
                f"cdi: {cdi_new}, ipca: {ipca_new}, custo: {custo} }},"
            )

        pattern = (
            r"  (\d{4}): \{ ouro: (\d+), cobre: (\d+), "
            r"cdi: ([\d.]+), ipca: ([\d.]+), custo: (\d+) \},"
        )
        new_html, n = re.subn(pattern, update_year, html)
        if n == 0:
            return html, False
        log(f"MACRO_ANUAL atualizado ({n} anos · CDI/IPCA fechados do BCB)")
        return new_html, True
    except Exception as e:
        log(f"MACRO_ANUAL falhou: {e}", ok=False)
        return html, False


# ===========================================================================
# FONTE 2 · CEPEA (planilhas .xls em data/cepea/)
# ===========================================================================

def converter_xls_para_xlsx(xls_path: Path) -> Path | None:
    """Usa libreoffice para converter .xls do CEPEA (CFB corrompido para xlrd)."""
    out_dir = xls_path.parent / "_tmp"
    out_dir.mkdir(exist_ok=True)
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "xlsx",
             "--outdir", str(out_dir), str(xls_path)],
            check=True, capture_output=True, timeout=120,
        )
        xlsx = out_dir / (xls_path.stem + ".xlsx")
        return xlsx if xlsx.exists() else None
    except Exception as e:
        log(f"Conversão xls→xlsx falhou: {e}", ok=False)
        return None


def processar_cepea_soja(xlsx_path: Path) -> list[dict] | None:
    """Lê planilha CEPEA Paranaguá soja, retorna agregado trimestral."""
    try:
        df = pd.read_excel(xlsx_path, header=None, skiprows=4, names=["data", "brl", "usd"])
        df = df.dropna(subset=["data"])
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
        df = df.dropna(subset=["data"])
        df["brl"] = pd.to_numeric(df["brl"], errors="coerce")
        df["usd"] = pd.to_numeric(df["usd"], errors="coerce")
        df["dolar"] = df["brl"] / df["usd"]
        df["cbot_premio"] = df["usd"] / BU_PER_SACA

        df = df[df["data"] >= "2010-01-01"].copy()
        df["ano"] = df["data"].dt.year
        df["tri"] = df["data"].dt.quarter
        df["label"] = df["ano"].astype(str).str[2:] + "Q" + df["tri"].astype(str)

        trim = df.groupby("label").agg(
            saca_brl=("brl", "mean"),
            saca_usd=("usd", "mean"),
            dolar=("dolar", "mean"),
            cbot_premio=("cbot_premio", "mean"),
            ano=("ano", "first"),
            tri=("tri", "first"),
        ).reset_index()
        trim = trim.sort_values(["ano", "tri"])
        return trim.to_dict(orient="records")
    except Exception as e:
        log(f"Processamento CEPEA falhou: {e}", ok=False)
        return None


# Tabelas auxiliares para reconstruir HISTORICO (mesma lógica do init)
ROTTERDAM_TON = {
    "10Q1":419,"10Q2":402,"10Q3":449,"10Q4":519,"11Q1":562,"11Q2":557,"11Q3":547,"11Q4":484,
    "12Q1":525,"12Q2":580,"12Q3":677,"12Q4":601,"13Q1":597,"13Q2":529,"13Q3":528,"13Q4":552,
    "14Q1":529,"14Q2":516,"14Q3":453,"14Q4":441,"15Q1":422,"15Q2":391,"15Q3":384,"15Q4":371,
    "16Q1":376,"16Q2":425,"16Q3":416,"16Q4":405,"17Q1":397,"17Q2":385,"17Q3":399,"17Q4":393,
    "18Q1":412,"18Q2":421,"18Q3":370,"18Q4":374,"19Q1":377,"19Q2":353,"19Q3":366,"19Q4":378,
    "20Q1":378,"20Q2":363,"20Q3":396,"20Q4":488,"21Q1":580,"21Q2":620,"21Q3":581,"21Q4":552,
    "22Q1":663,"22Q2":727,"22Q3":671,"22Q4":640,"23Q1":635,"23Q2":601,"23Q3":612,"23Q4":543,
    "24Q1":518,"24Q2":482,"24Q3":420,"24Q4":429,"25Q1":408,"25Q2":412,"25Q3":407,"25Q4":430,
    "26Q1":452,"26Q2":470,
}
UREIA_USD = {  # Black Sea FOB, World Bank/IndexMundi
    "10Q1":281,"10Q2":238,"10Q3":277,"10Q4":360,"11Q1":318,"11Q2":322,"11Q3":489,"11Q4":466,
    "12Q1":379,"12Q2":488,"12Q3":358,"12Q4":369,"13Q1":397,"13Q2":351,"13Q3":308,"13Q4":302,
    "14Q1":337,"14Q2":271,"14Q3":311,"14Q4":314,"15Q1":302,"15Q2":271,"15Q3":279,"15Q4":259,
    "16Q1":209,"16Q2":179,"16Q3":185,"16Q4":203,"17Q1":216,"17Q2":193,"17Q3":198,"17Q4":249,
    "18Q1":228,"18Q2":226,"18Q3":260,"18Q4":284,"19Q1":253,"19Q2":248,"19Q3":255,"19Q4":226,
    "20Q1":220,"20Q2":213,"20Q3":238,"20Q4":245,"21Q1":318,"21Q2":351,"21Q3":436,"21Q4":828,
    "22Q1":821,"22Q2":774,"22Q3":623,"22Q4":581,"23Q1":372,"23Q2":310,"23Q3":367,"23Q4":384,
    "24Q1":339,"24Q2":314,"24Q3":341,"24Q4":360,"25Q1":404,"25Q2":400,"25Q3":488,"25Q4":399,
    "26Q1":538,"26Q2":538,
}
EVENTOS = {
    "10Q1":"Pós-crise","10Q2":"Estabilidade","10Q3":"Rally inicia","10Q4":"China compra forte",
    "11Q1":"Super-ciclo","11Q2":"Real forte (1,60)","11Q3":"Ureia dispara","11Q4":"Correção",
    "12Q1":"Quebra Argentina","12Q2":"Seca EUA","12Q3":"PICO 2012","12Q4":"Correção",
    "13Q1":"Safra BR recorde","13Q2":"Prêmio cai","13Q3":"Dólar +","13Q4":"Estabilidade",
    "14Q1":"Tensão Crimeia","14Q2":"Real recupera","14Q3":"Safra EUA","14Q4":"Eleições BR",
    "15Q1":"Crise política","15Q2":"CBOT fundo","15Q3":"Dólar 4","15Q4":"Impeachment",
    "16Q1":"Pico dólar","16Q2":"Quebra Argentina","16Q3":"Real volta","16Q4":"Ureia barata",
    "17Q1":"Safra recorde BR","17Q2":"Estoques altos","17Q3":"Estabilidade","17Q4":"Ureia reage",
    "18Q1":"Tensão comercial","18Q2":"Guerra China-EUA","18Q3":"Prêmio BR explode","18Q4":"China compra BR",
    "19Q1":"Trégua frágil","19Q2":"CBOT fundo 2019","19Q3":"Fase 1 EUA-China","19Q4":"Acordo",
    "20Q1":"COVID choque","20Q2":"Dólar dispara","20Q3":"China volta forte","20Q4":"Rally começa",
    "21Q1":"Boom commodities","21Q2":"Pico CBOT 2021","21Q3":"Insumos disparam","21Q4":"Ureia HISTÓRICA",
    "22Q1":"Guerra Ucrânia","22Q2":"PICO ABSOLUTO","22Q3":"Correção","22Q4":"Normalização",
    "23Q1":"Safra recorde BR","23Q2":"Prêmio DERRETE","23Q3":"Real forte","23Q4":"Estoques altos",
    "24Q1":"CBOT cai","24Q2":"Prêmio reage","24Q3":"CBOT 4-anos mín","24Q4":"Dólar DISPARA",
    "25Q1":"Real recupera","25Q2":"Estabilização","25Q3":"Ureia sobe","25Q4":"Fim ano lateral",
    "26Q1":"Lateral","26Q2":"Atual",
}


def frete_estimado(t: str) -> int:
    ano = 2000 + int(t[:2])
    if ano <= 2012: return 4
    if ano <= 2014: return 5
    if ano <= 2017: return 6
    if ano <= 2019: return 7
    if ano == 2020: return 8
    if ano == 2021: return 11
    if ano == 2022: return 13
    return 10


def gerar_linhas_historico_soja(trim: list[dict]) -> list[str]:
    """Reconstrói as linhas do array HISTORICO a partir dos dados CEPEA."""
    lines = []
    for row in trim:
        t = row["label"]
        cbot_futures = round((ROTTERDAM_TON.get(t, 400) - 30) / 36.7437, 2)
        premio = round(row["cbot_premio"] - cbot_futures, 2)
        line = (
            f"  {{ t: '{t}', cbot: {cbot_futures:.2f}, premio: {premio:.2f}, "
            f"dolar: {row['dolar']:.2f}, ureiaUSD: {UREIA_USD.get(t, 400)}, "
            f"frete: {frete_estimado(t)}, conf: true, "
            f"evento: '{EVENTOS.get(t, '')}' }},"
        )
        lines.append(line)
    return lines


def gerar_linhas_historico_milho(df: pd.DataFrame) -> list[str]:
    """Reconstrói HISTORICO_MILHO a partir do .xls CEPEA Campinas."""
    df = df.dropna(subset=["data"])
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["data"])
    df["brl"] = pd.to_numeric(df["brl"], errors="coerce")
    df = df[df["data"] >= "2010-01-01"].copy()
    df["ano"] = df["data"].dt.year
    df["tri"] = df["data"].dt.quarter
    df["label"] = df["ano"].astype(str).str[2:] + "Q" + df["tri"].astype(str)
    trim = df.groupby("label").agg(brl=("brl", "mean"), ano=("ano", "first"), tri=("tri", "first")).reset_index()
    trim = trim.sort_values(["ano", "tri"])
    return [f"  {{ t:'{r['label']}', milhoSP:{r['brl']:.2f} }}," for _, r in trim.iterrows()]


def update_historico_cepea(html: str) -> tuple[str, bool, str]:
    """Procura arquivos .xls em data/cepea/ e atualiza HISTORICO + HISTORICO_MILHO."""
    if not CEPEA_DIR.exists():
        return html, False, "pasta data/cepea/ não existe"

    arquivos = sorted(CEPEA_DIR.glob("*.xls")) + sorted(CEPEA_DIR.glob("*.xlsx"))
    if not arquivos:
        return html, False, "nenhum arquivo encontrado"

    changed = False
    mensagens = []
    for arq in arquivos:
        # Detecta tipo (soja Paranaguá ou milho Campinas) pelo título
        try:
            if arq.suffix == ".xls":
                xlsx = converter_xls_para_xlsx(arq)
                if not xlsx:
                    continue
                df_head = pd.read_excel(xlsx, header=None, nrows=4)
            else:
                xlsx = arq
                df_head = pd.read_excel(xlsx, header=None, nrows=4)

            titulo = str(df_head.iloc[0, 0]).upper()

            if "SOJA" in titulo:
                trim = processar_cepea_soja(xlsx)
                if not trim:
                    continue
                linhas = gerar_linhas_historico_soja(trim)
                conteudo = "\n" + "\n".join(linhas) + "\n"
                novo_html, ok = replace_block(
                    html, "const HISTORICO = [", "\n];", conteudo
                )
                if ok:
                    html = novo_html
                    changed = True
                    mensagens.append(f"soja: {len(linhas)} trimestres")

            elif "MILHO" in titulo:
                df_full = pd.read_excel(xlsx, header=None, skiprows=4, names=["data", "brl", "usd"])
                linhas = gerar_linhas_historico_milho(df_full)
                conteudo = "\n" + "\n".join(linhas) + "\n"
                novo_html, ok = replace_block(
                    html, "const HISTORICO_MILHO = [", "\n];", conteudo
                )
                if ok:
                    html = novo_html
                    changed = True
                    mensagens.append(f"milho: {len(linhas)} trimestres")
        except Exception as e:
            log(f"Falha processando {arq.name}: {e}", ok=False)

    if changed:
        log(f"CEPEA atualizado · {', '.join(mensagens)}")
        return html, True, ", ".join(mensagens)
    return html, False, "sem mudanças nos arquivos"


# ===========================================================================
# FONTE 3 · TIMESTAMP DE ATUALIZAÇÃO
# ===========================================================================

def update_timestamp(html: str) -> str:
    """Atualiza o badge de 'última atualização' no eyebrow."""
    hoje = date.today().strftime("%d/%m/%Y")
    pattern = r"(dados CEPEA )(\d{2}/\d{2}/\d{4})"
    new_html, n = re.subn(pattern, rf"\g<1>{hoje}", html, count=1)
    if n > 0:
        log(f"Timestamp atualizado para {hoje}")
    return new_html


# ===========================================================================
# MAIN
# ===========================================================================

# ===========================================================================
# FONTE 4 · SIDRA IBGE · Produtividade JC anual (tabela 1612)
# Documentação: apisidra.ibge.gov.br
# URL: /values/t/1612/n6/4311205/v/214/p/all/c81/2713
# ===========================================================================

SIDRA_JC_CODE = "4311205"  # Júlio de Castilhos
SIDRA_VAR_RENDIMENTO = "214"  # Rendimento médio kg/ha
SIDRA_PROD_SOJA = "2713"  # Soja em grão (classifier 81)


def fetch_sidra_jc() -> dict[int, int]:
    """Busca rendimento médio soja JC por ano. Retorna {ano: kg_ha}."""
    url = (f"https://apisidra.ibge.gov.br/values/"
           f"t/1612/n6/{SIDRA_JC_CODE}/v/{SIDRA_VAR_RENDIMENTO}/p/all/c81/{SIDRA_PROD_SOJA}")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log(f"SIDRA fetch falhou: {exc}", ok=False)
        return {}
    # SIDRA retorna lista: primeiro item é cabeçalho, resto são valores
    # Campos: D2C = ano, V = valor (kg/ha)
    result = {}
    for row in data[1:]:
        try:
            ano = int(row.get("D2C", row.get("D3C", "")))
            valor_str = row.get("V", "")
            if valor_str in ("...", "..", "-", "X", ""):
                continue
            kg_ha = int(float(valor_str))
            if kg_ha > 0:
                result[ano] = kg_ha
        except (ValueError, KeyError):
            continue
    return result


def update_produtividade_jc(html: str) -> tuple[str, bool, str]:
    """Atualiza PRODUTIVIDADE_JC com dados SIDRA mais recentes."""
    sidra = fetch_sidra_jc()
    if not sidra:
        return html, False, "API SIDRA não retornou dados"
    updated = 0
    for ano, kg_ha in sidra.items():
        if ano < 2010 or ano > 2030:
            continue
        sc_ha = round(kg_ha / 60, 1)
        status = ('quebrasev' if sc_ha < 25 else
                  'quebra' if sc_ha < 35 else
                  'normal' if sc_ha < 50 else 'boa')
        # Regex: encontra linha do ano e substitui kgHa/scHa preservando obs
        pattern = rf"(\s*{ano}: \{{ kgHa:)\d+(, scHa:)[\d.]+(, status:)'[^']+'(, +obs:'[^']+'.*?\}},)"
        new_line = rf"\g<1>{kg_ha}\g<2>{sc_ha}\g<3>'★ SIDRA · safra ' + obs_sidra(\g<1>)\g<4>"
        # Simpler approach: regex substituição direta
        old_pattern = re.compile(rf"(\s+{ano}: \{{ kgHa:)\d+(, scHa:)[\d.]+(, status:'[^']+', +obs:')[^']*('.*?\}},)")
        m = old_pattern.search(html)
        if m:
            obs = f"★ SIDRA · atualizado {date.today().isoformat()}"
            new_html = old_pattern.sub(
                rf"\g<1>{kg_ha}\g<2>{sc_ha}, status:'{status}', obs:'{obs}\g<4>",
                html, count=1
            )
            if new_html != html:
                html = new_html
                updated += 1
    if updated > 0:
        return html, True, f"{updated} ano(s) atualizados"
    return html, False, "nenhuma alteração necessária"


# ===========================================================================
# FONTE 5 · USDA WASDE (estoques EUA, mundo) — automação parcial
# Site: usda.gov/oce/commodity/wasde/
# Os relatórios mensais ficam em wasde-NNNN.pdf — difícil parse confiável.
# Alternativa: usda.gov/data-products/wasde-historical-data → CSV
# IMPLEMENTAÇÃO: marca como "manual" mas registra no log de TODO.
# ===========================================================================

def todo_usda(html: str) -> tuple[str, bool, str]:
    """Marca USDA como pendente de atualização manual."""
    # Apenas registra no console — não muda nada
    return html, False, "USDA WASDE = atualização manual (vide README)"


# ===========================================================================
# FONTE 6 · CONAB CUSTOS DE PRODUÇÃO — manual
# Site: conab.gov.br/info-agro/custos-de-producao
# Publica Excel anual com custos por UF/região.
# Estrutura: usuário baixa o Excel, coloca em data/conab/, script processa.
# IMPLEMENTAÇÃO: stub que detecta arquivo em data/conab/ e parse.
# ===========================================================================

def update_conab_custos(html: str) -> tuple[str, bool, str]:
    """Processa Excel Conab se presente em data/conab/."""
    CONAB_DIR = DATA_DIR / "conab"
    if not CONAB_DIR.exists():
        return html, False, "nenhum arquivo Conab em data/conab/"
    excels = list(CONAB_DIR.glob("*.xls*"))
    if not excels:
        return html, False, "nenhum arquivo Conab em data/conab/"
    # Parse seria específico ao formato Conab — placeholder por ora
    return html, False, f"{len(excels)} arquivo(s) Conab encontrado(s) — parse manual via build_db.py"



    if not INDEX.exists():
        log(f"index.html não encontrado em {INDEX}", ok=False)
        return 1

    html = INDEX.read_text(encoding="utf-8")
    original = html
    sources_updated = []

    # 1) BCB SGS — USD/BRL atual
    html, ok, info = update_dolar_atual(html)
    if ok:
        sources_updated.append(f"dólar: {info}")

    # 2) BCB SGS — CDI/IPCA anuais em MACRO_ANUAL
    html, ok = update_macro_anual(html)
    if ok:
        sources_updated.append("macro CDI/IPCA")

    # 3) CEPEA — planilhas em data/cepea/
    html, ok, info = update_historico_cepea(html)
    if ok:
        sources_updated.append(f"CEPEA: {info}")

    # 4) SIDRA — produtividade JC
    html, ok, info = update_produtividade_jc(html)
    if ok:
        sources_updated.append(f"SIDRA JC: {info}")

    # 5) Conab — custos (manual)
    html, ok, info = update_conab_custos(html)
    if ok:
        sources_updated.append(f"Conab: {info}")
    else:
        print(f"  · Conab: {info}")

    # 6) USDA — manual
    _, _, info = todo_usda(html)
    print(f"  · USDA: {info}")

    # 7) Timestamp
    html = update_timestamp(html)

    # Grava se mudou
    if html != original:
        INDEX.write_text(html, encoding="utf-8")
        print(f"\n=== RESUMO ===\n{len(sources_updated)} fontes atualizadas:")
        for s in sources_updated:
            print(f"  · {s}")
        return 0
    else:
        print("\n=== RESUMO ===\nNenhuma alteração no painel.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
