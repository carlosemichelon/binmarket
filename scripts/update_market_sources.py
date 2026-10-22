#!/usr/bin/env python3
"""Coleta automática de preços CEPEA, safra Conab e PSD USDA.

Cada fonte é independente; se falhar preserva o último arquivo íntegro e
registra o erro no manifesto. Nunca escreve preço estimado como cotação.
"""
from __future__ import annotations

import csv
from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime
from io import StringIO, TextIOWrapper
import json
from pathlib import Path
import re
import tempfile
from zoneinfo import ZoneInfo
from zipfile import ZipFile, BadZipFile

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / 'data' / 'fontes'
STATUS = DIR / 'mercado.json'
CEPEA = DIR / 'cepea_soja.csv'
USDA = DIR / 'usda_soja.csv'
CONAB = DIR / 'conab_soja.xls'
CEPEA_URL = 'https://www.cepea.esalq.usp.br/br/indicador/soja.aspx'
CEPEA_BACKUP_URL = 'https://www.cepea.org.br/br/indicador/soja.aspx'
CONAB_URL = ('https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/'
             'safras/series-historicas/graos/soja/sojaseriehist.xls/@@download/file')
USDA_URL = 'https://apps.fas.usda.gov/psdonline/downloads/psd_alldata_csv.zip'
CEPEA_THIRD_URL = 'https://cultivee.com.br/cotacoes'
HEADERS = {'User-Agent':'Mozilla/5.0 (compatible; BinMarket-public-data/2.0; GitHub Actions)',
           'Accept-Language':'pt-BR,pt;q=0.9'}


def now_br() -> datetime:
    return datetime.now(ZoneInfo('America/Sao_Paulo'))


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return {}


def atomic_write(path: Path, content: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return False
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(content)
    tmp.replace(path)
    return True


def br_number(x: str) -> float:
    x = re.sub(r'[^\d,.-]', '', str(x)).strip()
    if ',' in x:
        x = x.replace('.', '').replace(',', '.')
    return float(x)


def validate_day(value: str, today: date | None = None) -> str:
    value = str(value).strip()
    day = datetime.strptime(value, '%d/%m/%Y').date()
    today = today or now_br().date()
    if day < date(2000, 1, 1) or day > today + timedelta(days=1):
        raise ValueError('Data fora da faixa permitida: ' + value)
    return day.isoformat()


def parse_cepea(html: str, today: date | None = None) -> list[dict]:
    """Seleciona a tabela de Paranaguá; não confunde com o indicador Paraná."""
    soup = BeautifulSoup(html, 'html.parser')
    target = None
    for table in soup.find_all('table'):
        # O primeiro quadro diário de soja no indicador oficial é Paranaguá.
        nearby = table.find_previous(string=re.compile(r'PARANAGU[ÁA]', re.I))
        if not nearby:
            continue
        preceding = str(nearby).upper()
        if 'PARANAGU' not in preceding and 'PARANAGUÁ' not in preceding:
            continue
        candidate = []
        for tr in table.find_all('tr'):
            cells = [v.get_text(' ', strip=True) for v in tr.find_all(['th', 'td'])]
            if len(cells) < 2:
                continue
            if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', cells[0]):
                continue
            try:
                day = validate_day(cells[0], today)
                price = br_number(cells[1])
                if not 35 <= price <= 400:
                    continue
                usd = br_number(cells[4]) if len(cells) > 4 and cells[4].strip() else None
                if usd is not None and not 5 <= usd <= 90:
                    usd = None
                candidate.append({'data':day,'brl_saca60':round(price,2),'usd_saca60':round(usd,2) if usd else None})
            except (ValueError, IndexError, OverflowError):
                pass
        if candidate:
            target = candidate
            break
    if not target:
        raise ValueError('Não foi possível reconhecer a tabela CEPEA Paranaguá com datas e preços válidos')
    out = {r['data']:r for r in target}
    return [out[d] for d in sorted(out)]


def load_cepea(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding='utf-8', newline='') as f:
        return {r['data']:r for r in csv.DictReader(f, delimiter=';') if r.get('data')}


def save_cepea(records: list[dict]) -> dict:
    prev = load_cepea(CEPEA)
    for record in records:
        prev[record['data']] = {
            'data':record['data'],
            'brl_saca60':f"{record['brl_saca60']:.2f}",
            'usd_saca60':f"{record['usd_saca60']:.2f}" if record['usd_saca60'] is not None else ''
        }
    s = StringIO()
    w = csv.DictWriter(s, delimiter=';', fieldnames=['data','brl_saca60','usd_saca60'], lineterminator='\n')
    w.writeheader()
    for k in sorted(prev):
        w.writerow(prev[k])
    atomic_write(CEPEA, s.getvalue().encode('utf-8'))
    last = prev[max(prev)]
    return {'data_referencia':last['data'],'valor':float(last['brl_saca60']),
            'unidade':'R$/saca de 60 kg','observacoes':len(prev)}


def parse_cepea_secondary(html: str, today: date | None = None) -> list[dict]:
    """Fonte secundária: lê somente valor e data explícita de apuração.

    Não confunde preços de outras praças ou data da consulta com apuração.
    """
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    match_day = re.search(r'apura(?:ç|c)[aã]o\s+de\s+(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})', text, re.I)
    match_price = re.search(r'Soja\s+Paranagu[áa].{0,100}?R\$\s*([\d.,]+)', text, re.I)
    months = {'janeiro':1,'fevereiro':2,'marco':3,'março':3,'abril':4,'maio':5,'junho':6,
              'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
    if not match_day or not match_price:
        raise ValueError('Tabela secundária CEPEA sem data explícita e preço de Paranaguá')
    dd, mm, yy = match_day.groups()
    month = months.get(mm.lower())
    if not month:
        raise ValueError('Mês secundário desconhecido')
    day = validate_day(f'{int(dd):02d}/{month:02d}/{yy}',today)
    price = br_number(match_price.group(1))
    if not 35 <= price <= 400:
        raise ValueError('Preço secundário fora da faixa de validação')
    return [{'data':day,'brl_saca60':round(price,2),'usd_saca60':None}]


def fetch_cepea(session: requests.Session) -> dict:
    err = None
    for url in (CEPEA_URL, CEPEA_BACKUP_URL):
        try:
            r = session.get(url, headers=HEADERS, timeout=40)
            r.raise_for_status()
            rows = parse_cepea(r.text)
            summary = save_cepea(rows)
            return {'status':'ok','url':url, **summary}
        except (requests.RequestException, ValueError) as exc:
            err = str(exc)
    # Fonte secundária já usada pelo painel principal; preserva proveniência.
    # Não substitui dado oficial de USD por valor inferido de câmbio.
    try:
        from update_data import fetch_noticias_agricolas_cepea, NA_CEPEA_URL
        backup = fetch_noticias_agricolas_cepea()
        parsed = []
        for row in backup.get('serie', []):
            day = validate_day(row['data'])
            price = float(row['valor'])
            if 35 <= price <= 400:
                parsed.append({'data':day,'brl_saca60':price,'usd_saca60':None})
        if parsed:
            summary = save_cepea(parsed)
            return {'status':'ok','url':NA_CEPEA_URL, **summary,
                    'observacao':'Fonte secundária: Notícias Agrícolas (indicador CEPEA)'}
    except Exception as exc:
        err = f'{err}; fallback: {exc}'
    # Terceira opção quando tanto o site oficial quanto o republicador estão bloqueados.
    try:
        r = session.get(CEPEA_THIRD_URL,headers=HEADERS,timeout=35)
        r.raise_for_status()
        summary = save_cepea(parse_cepea_secondary(r.text))
        return {'status':'ok','url':CEPEA_THIRD_URL,**summary,
                'observacao':'Fonte secundária republicada (Cultivee/CEPEA); somente BRL'}
    except (requests.RequestException, ValueError) as exc:
        err = f'{err}; fonte secundária: {exc}'
    raise RuntimeError(err or 'CEPEA indisponível')


def parse_usda_rows(reader) -> list[dict]:
    """Apenas séries oficiais de soja para Brasil/EUA e atributos selecionados.

    Unidade preservada como publicada no USDA (normalmente 1000 toneladas).
    """
    attrs = {'Production','Domestic Consumption','Ending Stocks','Exports','Imports'}
    output = {}
    for item in reader:
        commodity = str(item.get('Commodity_Code','')).lstrip('0')
        if commodity != '2222000':
            continue
        country = str(item.get('Country_Code','')).upper()
        attr = str(item.get('Attribute_Description',''))
        if country not in {'BR','US'} or attr not in attrs:
            continue
        try:
            year = int(item['Market_Year'])
            value = float(str(item['Value']).replace(',',''))
        except (ValueError, KeyError, TypeError):
            continue
        if 2010 <= year <= now_br().year+2 and 0 <= value <= 900000:
            key = (str(year),country,attr)
            output[key] = {'ano_safra':year,'pais':country,'indicador':attr,
                           'valor_mil_ton':value}
    result = sorted(output.values(), key=lambda x:(x['ano_safra'],x['pais'],x['indicador']))
    if not any(i['ano_safra'] >= now_br().year-2 for i in result) or len(result) < 50:
        raise ValueError('USDA não apresentou histórico coerente de soja para BR/US')
    return result


def fetch_usda(session: requests.Session) -> dict:
    # Abre ZIP em arquivo temporário para não descompactar ~200 MB em memória.
    with tempfile.TemporaryFile() as f:
        with session.get(USDA_URL, headers=HEADERS, stream=True, timeout=120) as r:
            r.raise_for_status()
            size = 0
            for part in r.iter_content(chunk_size=262144):
                size += len(part)
                if size > 60_000_000:
                    raise ValueError('ZIP USDA excede o limite de segurança de 60 MB')
                f.write(part)
        f.seek(0)
        with ZipFile(f) as z:
            members = [n for n in z.namelist() if n.lower().endswith('.csv') and 'psd' in n.lower()]
            if not members:
                raise ValueError('ZIP USDA sem CSV PSD')
            with z.open(members[0]) as data:
                reader = csv.DictReader(TextIOWrapper(data, encoding='utf-8-sig', newline=''))
                rows = parse_usda_rows(reader)
    s = StringIO()
    w = csv.DictWriter(s, fieldnames=['ano_safra','pais','indicador','valor_mil_ton'], delimiter=';', lineterminator='\n')
    w.writeheader(); w.writerows(rows)
    atomic_write(USDA, s.getvalue().encode('utf-8'))
    last_year = max(x['ano_safra'] for x in rows)
    prod = {x['pais']: x['valor_mil_ton'] for x in rows if x['ano_safra']==last_year and x['indicador']=='Production'}
    return {'status':'ok','url':USDA_URL,'data_referencia':str(last_year),
            'observacoes':len(rows),'unidade':'mil toneladas (USDA PSD)',
            'producao_br_mil_ton':prod.get('BR'),'producao_eua_mil_ton':prod.get('US')}


def parse_conab_producao(book) -> list[dict]:
    """Produção nacional de soja, por safra, na planilha oficial Conab.
    Não usa linhas de regiões/estados no lugar da soma Brasil.
    """
    sheet = next((sh for sh in book.sheets() if 'produção' in sh.name.lower() or 'producao' in sh.name.lower()), None)
    if sheet is None:
        raise ValueError('Aba Produção não localizada')
    header_row = next((i for i in range(min(sheet.nrows, 15))
                       if 'REGIÃO/UF' in str(sheet.cell_value(i,0)).upper()), None)
    if header_row is None:
        raise ValueError('Cabeçalho REGIÃO/UF não localizado')
    brasil_row = next((i for i in range(header_row+1, sheet.nrows)
                      if str(sheet.cell_value(i,0)).strip().upper() in ('BRASIL','TOTAL BRASIL')),None)
    if brasil_row is None:
        raise ValueError('Linha BRASIL não localizada')
    data = []
    for col in range(1,sheet.ncols):
        season = str(sheet.cell_value(header_row,col)).strip()
        if not re.fullmatch(r'20\d\d/\d\d', season):
            continue
        raw = sheet.cell_value(brasil_row,col)
        if not isinstance(raw,(float,int)) or not 10000 < raw < 250000:
            continue
        data.append({'safra':season, 'producao_mil_ton':round(float(raw),1)})
    if len(data)<5:
        raise ValueError('Dados nacionais de produção insuficientes')
    return data


def fetch_conab(session:requests.Session) -> dict:
    r = session.get(CONAB_URL, headers=HEADERS, timeout=90)
    r.raise_for_status()
    content = r.content
    if len(content) < 10000 or not (content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' or content[:2] == b'PK'):
        raise ValueError('Conab não retornou planilha Excel válida')
    # É um download automatizado da série oficial, NÃO dados de custos ou oferta/demanda.
    atomic_write(CONAB, content)
    conab_snapshot = {}
    # Registro auditável da estrutura da planilha; sem inferir valores antes de validar as células.
    try:
        import xlrd
        book = xlrd.open_workbook(file_contents=content)
        schema = []
        for sheet in book.sheets():
            preview = []
            for row_ix in range(min(sheet.nrows, 14)):
                cells = [str(sheet.cell_value(row_ix, col_ix))[:90] for col_ix in range(min(sheet.ncols, 10))]
                preview.append(cells)
            schema.append({'sheet':sheet.name,'rows':sheet.nrows,'columns':sheet.ncols,'preview':preview})
        atomic_write(DIR/'conab_estrutura.json', (json.dumps(schema,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        try:
            production = parse_conab_producao(book)
            output = StringIO()
            writer = csv.DictWriter(output,fieldnames=['safra','producao_mil_ton'],delimiter=';',lineterminator='\n')
            writer.writeheader()
            writer.writerows(production)
            atomic_write(DIR/'conab_producao.csv',output.getvalue().encode('utf-8'))
            conab_snapshot = {'ultima_safra':production[-1]['safra'],'producao_mil_ton':production[-1]['producao_mil_ton'],'observacoes':len(production)}
            print(f'Conab: {len(production)} safras nacionais extraídas; última {production[-1]["safra"]}',flush=True)
        except ValueError as exc:
            print(f'Conab: extração nacional pendente: {exc}',flush=True)
    except Exception as exc:
        print(f'Conab: estrutura do Excel indisponível: {exc}',flush=True)
    modified = r.headers.get('Last-Modified')
    try:
        reference = parsedate_to_datetime(modified).date().isoformat() if modified else None
    except (ValueError, TypeError):
        reference = None
    return {'status':'ok','url':CONAB_URL,'data_referencia':reference,
            'observacoes':None, 'unidade':'produção nacional em mil toneladas; demais séries do simulador não atualizadas', **conab_snapshot}



# FONTE 4 · COTRIJUC / JULIO DE CASTILHOS (COTACAO LOCAL REAL)
COTRIJUC_URL = 'https://www.cotrijuc.com.br/'
COTRIJUC_CSV = DIR / 'cotrijuc_soja.csv'


def parse_cotrijuc_soja(html: str, today: date | None = None) -> dict:
    """Extrai somente a primeira cotacao SOJA no bloco Graos da home.

    Exige data publicada pela propria cooperativa; nao usa dia da coleta.
    """
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    block = re.search(
        r'COTA(?:Ç|C)[OÕ]ES DO DIA(.{0,1500}?)(?:Bolsa de Chicago|Moeda|J[uú]lio de Castilhos)',
        text, re.I)
    if not block:
        raise ValueError('Cotrijuc: bloco de cotacoes de graos nao identificado')
    m = re.search(r'(\d{2}/\d{2}/\d{4}).{0,200}?\bSOJA\b\s*(\d{1,3}(?:\.\d{3})*,\d{2})', block.group(1), re.I)
    if not m:
        raise ValueError('Cotrijuc: par data e preco de soja nao identificado')
    ref = validate_day(m.group(1), today)
    value = br_number(m.group(2))
    if not 35 <= value <= 400:
        raise ValueError('Cotrijuc: preco fora da faixa permitida')
    return {'data':ref,'brl_saca60':round(value,2)}


def fetch_cotrijuc(session: requests.Session) -> dict:
    r = session.get(COTRIJUC_URL, headers=HEADERS, timeout=35)
    r.raise_for_status()
    record = parse_cotrijuc_soja(r.text)
    previous = load_cepea(COTRIJUC_CSV)
    prevdate = max(previous) if previous else None
    # Nao permitir regressao da referencia, mesmo se cache da fonte atrasar.
    if prevdate and record['data'] < prevdate:
        raise ValueError('Cotrijuc: fonte retornou data anterior a ultima registrada')
    previous[record['data']] = {'data':record['data'], 'brl_saca60':f"{record['brl_saca60']:.2f}"}
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=['data','brl_saca60'], delimiter=';', lineterminator='\n')
    writer.writeheader()
    for key in sorted(previous):
        writer.writerow(previous[key])
    atomic_write(COTRIJUC_CSV, output.getvalue().encode('utf-8'))
    return {'status':'ok','url':COTRIJUC_URL,
            'data_referencia':record['data'], 'valor':record['brl_saca60'],
            'unidade':'R$/saca de 60 kg - preco local de balcao',
            'observacoes':len(previous)}


# FONTE 5 · SOJA CBOT / CONTRATO LISTADO (REPUBLICADO DE CME)
CBOT_SOURCE = 'https://www.noticiasagricolas.com.br/cotacoes/soja'
CBOT_MONTHS = {'janeiro':1,'marco':3,'março':3,'maio':5,'julho':7,
               'agosto':8,'setembro':9,'novembro':11}


def parse_cbot_soja(html: str, today: date | None = None) -> dict:
    """Encontra futuro de soja mais proximo nao vencido na tabela CBOT.

    Nao mistura soja em Chicago (USD/bushel) com soja brasileira R$/saca.
    """
    today = today or now_br().date()
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    part = re.search(r'Soja\s*-\s*Bolsa de Chicago\b', text, re.I)
    if not part:
        raise ValueError('Tabela Soja - Bolsa de Chicago nao encontrada')
    block = text[part.end():part.end()+2500]
    dt = re.search(r'Atualizado em:\s*(\d{2}/\d{2}/\d{4})', block)
    if not dt:
        raise ValueError('CBOT sem data de fechamento visivel')
    ref = validate_day(dt.group(1), today)
    matches = re.findall(r'\b(Janeiro|Março|Marco|Maio|Julho|Agosto|Setembro|Novembro)/(\d{2}|\d{4})\s+(\d{1,2},\d{3,4})', block, re.I)
    possible = []
    for month_raw, yr_raw, price_raw in matches:
        month = CBOT_MONTHS.get(month_raw.lower())
        year = int(yr_raw) + (2000 if len(yr_raw)==2 else 0)
        price = br_number(price_raw)
        if month and 5 <= price <= 30 and (year,month) >= (today.year,today.month):
            possible.append((year,month,price))
    if not possible:
        raise ValueError('CBOT sem contrato futuro vigente identificavel')
    year,month,price = sorted(possible)[0]
    return {'data':ref,'valor':round(price,4),'contrato':f'{year}-{month:02d}'}


def fetch_cbot_soja(session: requests.Session) -> dict:
    r=session.get(CBOT_SOURCE, headers=HEADERS, timeout=35)
    r.raise_for_status()
    found=parse_cbot_soja(r.text)
    return {'status':'ok','url':CBOT_SOURCE,
            'data_referencia':found['data'],'valor':found['valor'],'contrato':found['contrato'],
            'unidade':'USD/bushel - contrato futuro mais proximo ainda vigente'}


# FONTE · Indicador de milho Esalq/B3 em R$/saca 60kg.
MILHO_URL = "https://www.noticiasagricolas.com.br/cotacoes/milho/indicador-cepea-esalq-milho"
MILHO_CSV = DIR / "milho_cepea.csv"

def parse_milho(html:str, today:date|None=None) -> dict:
    text=BeautifulSoup(html,"html.parser").get_text(" ",strip=True)
    title=re.search(r'Indicador do Milho Esalq/B3',text,re.I)
    if title is None:raise ValueError("Milho Esalq/B3 ausente")
    # A tabela do indicador antecede outras cotacoes de mercado.
    fragment=text[title.end():title.end()+1250]
    match=re.search(r'Fechamento:\s*(\d{2}/\d{2}/\d{4}).{0,150}?\b(\d{2}/\d{2}/\d{4})\s+([\d.,]+)',fragment,re.I)
    if not match:raise ValueError("Milho sem fechamento datado e preco")
    if match.group(1)!=match.group(2):raise ValueError("Data do fechamento de milho divergente")
    day=validate_day(match.group(1),today)
    value=br_number(match.group(3))
    if not 20 <= value <= 250:raise ValueError("Milho: preco fora de faixa")
    return {'data':day,'brl_saca60':round(value,2)}

def fetch_milho(session:requests.Session) -> dict:
    # Prefer indicador Esalq/B3. Se a pagina nao fornecer HTML estatico,
    # usar a fonte secundaria com apuracao datada.
    error=None
    source=MILHO_URL
    try:
        r=session.get(MILHO_URL,headers=HEADERS,timeout=35)
        r.raise_for_status()
        found=parse_milho(r.text)
    except (requests.RequestException,ValueError) as exc:
        error=str(exc)
        source=CEPEA_THIRD_URL
        r=session.get(CEPEA_THIRD_URL,headers=HEADERS,timeout=35)
        r.raise_for_status()
        plain=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
        m=re.search(r'apura(?:ç|c)[aã]o\s+de\s+(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})',plain,re.I)
        price_match=re.search(r'\bMilho\b.{0,70}?R\$\s*([\d.,]+)',plain,re.I)
        months={'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,
                'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
        if not m or not price_match or m.group(2).lower() not in months:
            raise ValueError('Milho: principal e fonte alternativa indisponiveis: '+str(error))
        d,mo,yr=m.groups()
        day=validate_day(f'{int(d):02d}/{months[mo.lower()]:02d}/{yr}')
        value=br_number(price_match.group(1))
        if not 20<=value<=250:raise ValueError('Milho fora da faixa')
        found={'data':day,'brl_saca60':round(value,2)}
    old=load_cepea(MILHO_CSV)
    old[found['data']]={'data':found['data'],'brl_saca60':f"{found['brl_saca60']:.2f}"}
    out=StringIO()
    writer=csv.DictWriter(out,fieldnames=['data','brl_saca60'],delimiter=';',lineterminator='\n')
    writer.writeheader()
    for key in sorted(old):writer.writerow(old[key])
    atomic_write(MILHO_CSV,out.getvalue().encode('utf-8'))
    last=old[max(old)]
    return {'status':'ok','url':source,'data_referencia':max(old),
            'valor':float(last['brl_saca60']),'unidade':'R$/saca de 60 kg',
            'observacoes':len(old),
            'observacao':'Fonte secundaria datada' if error else 'Indicador Esalq/B3'}


def run() -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    status = read_json(STATUS)
    sources = status.get('fontes') or {}
    checked = now_br().isoformat(timespec='seconds')
    with requests.Session() as session:
        for key, func in [('cepea_soja',fetch_cepea),('conab_safra',fetch_conab),('usda_psd',fetch_usda),('cotrijuc_soja',fetch_cotrijuc),('cbot_soja',fetch_cbot_soja),('milho_cepea',fetch_milho)]:
            before = sources.get(key) or {}
            try:
                fresh = func(session)
                sources[key] = {**fresh, 'verificado_em':checked, 'erro':None}
                print(f'{key}: sucesso, referência {fresh.get("data_referencia")}',flush=True)
            except Exception as exc:
                # Não modifica a data de referência nem os últimos arquivos íntegros.
                sources[key] = {**before, 'status':'falha', 'verificado_em':checked,
                                'erro':str(exc)[:300], 'url': before.get('url') or
                                {'cepea_soja':CEPEA_URL,'conab_safra':CONAB_URL,'usda_psd':USDA_URL,'cotrijuc_soja':COTRIJUC_URL,'cbot_soja':CBOT_SOURCE,'milho_cepea':MILHO_URL}[key]}
                print(f'{key}: falha: {exc}',flush=True)
    output = {'versao':1,'verificado_em':checked,'fontes':sources,
              'aviso':'Verificação automática não implica cotação nova. Custos, prêmios locais e séries estimadas do simulador não são preços coletados automaticamente.'}
    atomic_write(STATUS, (json.dumps(output,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
    return output


if __name__ == '__main__':
    result = run()
    # GitHub Actions marca falha se fontes críticas inoperantes, mas mantém dados publicados.
    missing = [k for k,v in result['fontes'].items() if v.get('status')!='ok']
    if missing:
        print('Fontes com falha: '+', '.join(missing),flush=True)
        raise SystemExit(1)
