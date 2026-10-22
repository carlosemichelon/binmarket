#!/usr/bin/env python3
"""Atualiza cotações NESPro no repositório BinMarket.

Coleta a página pública, valida data e preços e preserva lacunas no histórico.
Falhas causam exit code != 0 (para alertas de GitHub Actions), sem alterar dados.
Use --fixture arquivo.html para testes sem acesso à rede.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data/bovinos/historico.csv"
STATUS_PATH = ROOT / "data/bovinos/atualizacao.json"
SOURCE = "https://bovinos-indices.nesproufrgs.com/"
COLS = ["pv_macho", "pc_macho", "pv_femea", "pc_femea", "terneiro", "terneira", "novilho", "novilha", "vaca_invernar", "vaca_prenhe"]
LABELS = {
    "pv_macho": "PV Macho", "pc_macho": "PC Macho", "pv_femea": "PV Fêmea", "pc_femea": "PC Fêmea",
    "terneiro": "Terneiro", "terneira": "Terneira", "novilho": "Novilho", "novilha": "Novilha",
    "vaca_invernar": "Vaca Invernar", "vaca_prenhe": "Vaca Prenhe",
}


def normal(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip().lower()


def date_value(value: str) -> str:
    s = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return date.fromisoformat(s).isoformat()
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", s)
    if not m:
        raise ValueError(f"Data inválida: {value!r}")
    d, mo, year = map(int, m.groups())
    if year < 100:
        year += 2000
    return date(year, mo, d).isoformat()


def price_value(value: str) -> float | None:
    s = str(value or "").strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    if not s or s in ("-", "—", "n/d"):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return None
    return round(n, 2) if 1 <= n <= 200 else None


def load_csv(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        items = csv.DictReader(f, delimiter=";")
        if not items.fieldnames or "data" not in items.fieldnames:
            raise ValueError("Cabeçalho inválido no CSV existente")
        rows = {}
        for raw in items:
            try:
                day = date_value(raw["data"])
            except (ValueError, TypeError):
                continue
            obs = {"data": day}
            for col in COLS:
                v = price_value(raw.get(col, ""))
                if v is not None:
                    obs[col] = v
            if len(obs) > 1:
                rows[day] = obs
        return rows


def serialize_csv(rows: dict[str, dict]) -> str:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["data", *COLS], delimiter=";", lineterminator="\n")
    writer.writeheader()
    for day in sorted(rows):
        r = rows[day]
        writer.writerow({"data": day, **{c: (f"{r[c]:.2f}".replace(".", ",") if c in r else "") for c in COLS}})
    return out.getvalue()


def parse_cards(text: str) -> dict[str, float]:
    """Lê cartões de preço do bloco semanal, sem confundir dados históricos."""
    cleaned = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    start = re.search(r"Gado Gordo\s*[·-]\s*Semana Atual", cleaned, re.I)
    end = re.search(r"Análise Técnica Semanal|Resumo dos Indicadores da Semana|Variação R\$/kg", cleaned, re.I)
    block = cleaned[start.start():end.start()] if start and end and end.start() > start.start() else cleaned
    values = {}
    for key, label in LABELS.items():
        m = re.search(r"\b" + re.escape(label) + r"\b.{0,45}?R\$\s*([\d.,]+)", block, re.I)
        if m:
            value = price_value(m.group(1))
            if value is not None:
                values[key] = value
    return values


def parse_table(html: str) -> dict[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = {}
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        header = [normal(x.get_text(" ", strip=True)) for x in trs[0].find_all(["th", "td"], recursive=False)]
        if not (any("pv macho" in h for h in header) and any("terneiro" in h for h in header) and any("novilho" in h for h in header)):
            continue
        indices = {}
        for i, h in enumerate(header):
            if h == "data":
                indices["data"] = i
            elif "pv macho" in h:
                indices["pv_macho"] = i
            elif "pv femea" in h:
                indices["pv_femea"] = i
            elif "terneiro" in h and "boi" not in h:
                indices["terneiro"] = i
            elif "novilho" in h and "boi" not in h:
                indices["novilho"] = i
        if "data" not in indices:
            continue
        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"], recursive=False)]
            try:
                day = date_value(cells[indices["data"]])
            except (ValueError, IndexError):
                continue
            record = {"data": day}
            for key, ix in indices.items():
                if key == "data" or ix >= len(cells):
                    continue
                value = price_value(cells[ix])
                if value is not None:
                    record[key] = value
            if len(record) >= 3:
                rows[day] = record
        break
    return rows


def parse_page(html: str) -> tuple[str, dict[str, dict]]:
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup.find_all(["script", "style", "noscript"]):
        bad.decompose()
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\bAtualizado\s+(\d{1,2}/\d{2}/\d{2,4})", text, re.I)
    if not match:
        raise ValueError("A página não apresenta a data 'Atualizado DD/MM/AA'")
    day = date_value(match.group(1))
    cards = parse_cards(text)
    mandatory = {"pv_macho", "pv_femea", "terneiro", "novilho"}
    if not mandatory.issubset(cards):
        raise ValueError(f"Cartões semanais incompletos: encontrados {sorted(cards)}")
    previous = parse_table(html)
    previous[day] = {**previous.get(day, {"data": day}), **cards}
    return day, previous


def fetch_html() -> str:
    response = requests.get(
        SOURCE,
        timeout=35,
        headers={"User-Agent": "BinMarket/1.0 (indicadores de mercado; dados públicos NESPro/UFRGS)", "Accept": "text/html"},
    )
    response.raise_for_status()
    if len(response.content) < 300:
        raise RuntimeError("Página NESPro com HTML incompleto")
    return response.text


def fetch_browser_html() -> str:
    """Fallback para quando o site depender de renderização JavaScript."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(locale="pt-BR", timezone_id="America/Sao_Paulo")
            page.goto(SOURCE, wait_until="domcontentloaded", timeout=60000)
            page.get_by_text("PV Macho", exact=True).first.wait_for(timeout=25000)
            page.wait_for_timeout(1500)
            return page.content()
        finally:
            browser.close()



# Download automatico do historico completo exposto pela pagina NESPro.
# Datas e categorias nao reconhecidas sao ignoradas; nunca inventar preco.
def decode_export(content: bytes, filename: str) -> dict:
    from io import BytesIO, StringIO
    if len(content) > 18_000_000:
        raise ValueError("Exportacao NESPro muito grande")
    if filename.lower().endswith(".xlsx") or content[:2] == b"PK":
        from openpyxl import load_workbook
        wb = load_workbook(BytesIO(content), data_only=True, read_only=True)
        sheets = [list(sh.values) for sh in wb.worksheets if "ovino" not in normal(sh.title) and "varejo" not in normal(sh.title)]
        wb.close()
    elif filename.lower().endswith(".xls"):
        import xlrd
        wb=xlrd.open_workbook(file_contents=content)
        sheets=[[sh.row_values(i) for i in range(sh.nrows)] for sh in wb.sheets() if "ovino" not in normal(sh.name) and "varejo" not in normal(sh.name)]
    else:
        txt=content.decode("utf-8-sig")
        try:sep=csv.Sniffer().sniff(txt[:2000],delimiters=",;\t").delimiter
        except csv.Error:sep=";"
        sheets=[list(csv.reader(StringIO(txt),delimiter=sep))]
    aliases={"boi_gordo_pv":"pv_macho","boi_gordo_pc":"pc_macho","vaca_gorda_pv":"pv_femea","vaca_gorda_pc":"pc_femea","vaca_de_invernar":"vaca_invernar"}
    results={}
    for grid in sheets:
        for pos in range(min(len(grid),20)):
            header=[normal(v).replace(" ","_") for v in grid[pos]]
            datecol=next((i for i,h in enumerate(header) if h in ("data","date","semana","data_coleta")),None)
            if datecol is None:continue
            columns={i:(h if h in COLS else aliases.get(h)) for i,h in enumerate(header) if h in COLS or h in aliases}
            categ=next((i for i,h in enumerate(header) if h in ("categoria","indicador")),None)
            pricecol=next((i for i,h in enumerate(header) if h in ("valor","preco","preco_kg")),None)
            if not columns and (categ is None or pricecol is None):continue
            for values in grid[pos+1:]:
                if datecol>=len(values):continue
                try:
                    v=values[datecol]
                    day=(v.date() if isinstance(v,datetime) else v).isoformat() if isinstance(v,(datetime,date)) else date_value(str(v))
                except (ValueError,TypeError):continue
                record=results.setdefault(day,{"data":day})
                if categ is not None and pricecol is not None and max(categ,pricecol)<len(values):
                    raw=normal(values[categ]).replace(" ","_")
                    key=raw if raw in COLS else aliases.get(raw)
                    val=price_value(values[pricecol])
                    if key and val is not None:record[key]=val
                else:
                    for i,key in columns.items():
                        if i<len(values):
                            val=price_value(values[i])
                            if val is not None:record[key]=val
            break
    results={d:r for d,r in results.items() if len(r)>1}
    if not results:raise ValueError("Sem dados bovinos reconhecidos na exportacao")
    return results


def download_full_history() -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(accept_downloads=True,locale="pt-BR",timezone_id="America/Sao_Paulo")
            page.goto(SOURCE,wait_until="domcontentloaded",timeout=60000)
            initial=page.get_by_role("button",name=re.compile("Baixar base de dados",re.I)).first
            try:
                with page.expect_download(timeout=20000) as event:
                    initial.click()
                download=event.value
            except Exception as first_error:
                # Alguns sites abrem um menu "Gado"/"CSV"/"Excel" antes do download.
                options=page.locator('button,[role="menuitem"],a').all_text_contents()
                requested=None
                for label in ('Baixar CSV', 'Baixar Excel', 'Exportar CSV', 'Exportar Excel', 'CSV', 'XLSX'):
                    matches=page.get_by_role('button',name=re.compile(re.escape(label),re.I))
                    if matches.count() and matches.first.is_visible():
                        requested=matches.first
                        break
                if requested is None:
                    visible=[str(v).strip()[:80] for v in options if re.search('baix|dados|export|excel|csv|gado|repor',str(v),re.I)]
                    raise RuntimeError(f"Botao nao iniciou download; controles relevantes: {visible[:12]}") from first_error
                with page.expect_download(timeout=40000) as event:
                    requested.click()
                download=event.value
            return decode_export(Path(download.path()).read_bytes(),download.suggested_filename)
        finally:browser.close()

def update(html: str, today: date | None = None, *, persist: bool = True, extra: dict | None = None) -> dict:
    today = today or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    source_day, published = parse_page(html)
    if source_day > (today + timedelta(days=1)).isoformat():
        raise ValueError(f"NESPro apresenta data futura: {source_day}")
    if source_day < "2020-01-01":
        raise ValueError(f"Data NESPro inesperadamente antiga: {source_day}")
    if len(published[source_day]) < 5:
        raise ValueError("Cotação NESPro sem os quatro preços principais")

    before = load_csv(CSV_PATH)
    merged = {d: dict(row) for d, row in before.items()}
    for day,record in (extra or {}).items():
        if '2020-01-01' <= day <= (today + timedelta(days=1)).isoformat():
            merged[day] = {**merged.get(day,{'data':day}), **record}
    for day, new_record in published.items():
        if day > (today + timedelta(days=1)).isoformat():
            continue
        merged[day] = {**merged.get(day, {"data": day}), **new_record}
    new_content = serialize_csv(merged)
    old_content = CSV_PATH.read_text(encoding="utf-8-sig") if CSV_PATH.exists() else ""
    changed = new_content != old_content
    checked = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d")
    status = {"fonte": SOURCE, "ultima_coleta": max(merged), "checado_em": checked, "quantidade_datas": len(merged), "observacao": "Coletas semanais; última checagem não implica preço novo."}
    if persist:
        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        if changed:
            CSV_PATH.write_text(new_content, encoding="utf-8")
        STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"changed": changed, "ultima_coleta": status["ultima_coleta"], "checado_em": checked, "datas": len(merged), "novas_datas": len(set(merged) - set(before)), "fonte_data": source_day}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, help="HTML local para depuração/testes")
    parser.add_argument("--dry-run", action="store_true", help="Valida sem escrever no disco")
    args = parser.parse_args()
    try:
        if args.fixture:
            outcome = update(args.fixture.read_text(encoding="utf-8"), persist=not args.dry_run)
        else:
            try:
                outcome = update(fetch_html(), persist=not args.dry_run)
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                print(f"Coleta HTTP não disponível ({exc}); tentando navegador Chromium...", flush=True)
                outcome = update(fetch_browser_html(), persist=not args.dry_run)
        if not args.fixture:
            try:
                full=download_full_history()
                outcome=update(fetch_html(),persist=not args.dry_run,extra=full)
                outcome['historico_exportado']=len(full)
                if not args.dry_run:
                    status=json.loads(STATUS_PATH.read_text(encoding='utf-8'))
                    status['historico_exportacao']={'resultado':'ok','datas_extraidas':len(full),'checado_em':datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds')}
                    STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            except Exception as error:
                print(f'NESPro: download historico indisponivel ({error}); preservando dados anteriores',flush=True)
                if not args.dry_run and STATUS_PATH.exists():
                    status=json.loads(STATUS_PATH.read_text(encoding='utf-8'))
                    status['historico_exportacao']={'resultado':'falha','erro':str(error)[:600],'checado_em':datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds')}
                    STATUS_PATH.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print("NESPro:", json.dumps(outcome, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(f"ERRO na coleta NESPro: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
