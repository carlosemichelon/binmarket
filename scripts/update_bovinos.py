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


def update(html: str, today: date | None = None, *, persist: bool = True) -> dict:
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
        print("NESPro:", json.dumps(outcome, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(f"ERRO na coleta NESPro: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
