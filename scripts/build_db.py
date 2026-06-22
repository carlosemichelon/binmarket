"""Constrói base de dados — versão corrigida."""
import re
from pathlib import Path
import pandas as pd

INDEX = Path('/home/claude/index.html')
OUT = Path('/home/claude/db_build/out'); OUT.mkdir(exist_ok=True)
CSV = OUT / 'csv'; CSV.mkdir(exist_ok=True)
html = INDEX.read_text(encoding='utf-8')

def extrai_array(nome):
    p = re.compile(r'const ' + re.escape(nome) + r' = \[\n(.*?)\n\];', re.DOTALL)
    m = p.search(html)
    return m.group(1) if m else None

def extrai_obj(nome):
    p = re.compile(r'const ' + re.escape(nome) + r' = \{\n(.*?)\n\};', re.DOTALL)
    m = p.search(html)
    return m.group(1) if m else None

def parse_objects(s):
    """Parsa TODOS os objetos JS { k:v, k:v } na string."""
    objs = []
    # Encontra objetos delimitados por { e }
    depth = 0; start = -1
    for i, c in enumerate(s):
        if c == '{':
            if depth == 0: start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                body = s[start+1:i]
                obj = {}
                for kv in re.finditer(r"(\w+)\s*:\s*('[^']*'|[-\d.]+|true|false)", body):
                    k, v = kv.group(1), kv.group(2)
                    if v.startswith("'"): obj[k] = v.strip("'")
                    elif v in ('true','false'): obj[k] = v == 'true'
                    else:
                        try: obj[k] = float(v) if '.' in v or 'e' in v.lower() else int(v)
                        except: obj[k] = v
                if obj: objs.append(obj)
                start = -1
    return objs

# ============== Soja CIF ==============
hist = parse_objects(extrai_array('HISTORICO'))
for r in hist:
    fob = (r['cbot'] + r['premio']) * 2.2046 * r['dolar']
    r['saca_fob_brl'] = round(fob, 2)
    r['saca_cif_brl_jc'] = round(fob - r['frete'], 2)
    r['ano'] = 2000 + int(r['t'][:2])
    r['tri'] = int(r['t'][3])
df_soja = pd.DataFrame(hist).rename(columns={
    't':'trimestre','cbot':'cbot_usd_bu','premio':'premio_usd_bu',
    'dolar':'dolar_brl_usd','ureiaUSD':'ureia_usd_ton','frete':'frete_brl_sc'
})
df_soja = df_soja[['trimestre','ano','tri','cbot_usd_bu','premio_usd_bu','dolar_brl_usd','ureia_usd_ton','frete_brl_sc','saca_fob_brl','saca_cif_brl_jc','evento']]
df_soja.to_csv(CSV/'01_historico_soja.csv', index=False, encoding='utf-8-sig')
print(f"✓ Soja: {len(df_soja)}")

# Milho
milho = parse_objects(extrai_array('HISTORICO_MILHO'))
for r in milho: r['ano']=2000+int(r['t'][:2]); r['tri']=int(r['t'][3])
df_milho = pd.DataFrame(milho).rename(columns={'t':'trimestre','milhoSP':'milho_cepea_sp_brl_sc'})
df_milho = df_milho[['trimestre','ano','tri','milho_cepea_sp_brl_sc']]
df_milho.to_csv(CSV/'02_historico_milho.csv', index=False, encoding='utf-8-sig')
print(f"✓ Milho: {len(df_milho)}")

# Boi
boi = parse_objects(extrai_array('HISTORICO_GADO'))
for r in boi: r['ano']=2000+int(r['t'][:2]); r['tri']=int(r['t'][3])
df_boi = pd.DataFrame(boi).rename(columns={'t':'trimestre','boiVivo':'boi_vivo_brl_kg_rs','arroba':'arroba_brl'})
df_boi = df_boi[['trimestre','ano','tri','boi_vivo_brl_kg_rs','arroba_brl']]
df_boi.to_csv(CSV/'03_historico_boi.csv', index=False, encoding='utf-8-sig')
print(f"✓ Boi: {len(df_boi)}")

# Macro
def parse_yearly_dict(s):
    out = []
    for m in re.finditer(r'(\d{4}):\s*\{([^}]+)\}', s):
        ano, body = int(m.group(1)), m.group(2)
        row = {'ano': ano}
        for kv in re.finditer(r"(\w+)\s*:\s*([-\d.]+)", body):
            try: row[kv.group(1)] = float(kv.group(2))
            except: pass
        out.append(row)
    return out

df_macro = pd.DataFrame(parse_yearly_dict(extrai_obj('MACRO_ANUAL'))).rename(columns={
    'ouro':'ouro_usd_oz', 'prata':'prata_usd_oz', 'cobre':'cobre_usd_ton',
    'minerioFe':'minerio_fe_usd_ton', 'cdi':'cdi_ann', 'ipca':'ipca_ann',
    'selic':'selic_ann', 'diesel':'diesel_brl_litro', 'hilux':'hilux_brl_mil',
    'custo':'custo_soja_conab_brl_sc'
})
df_macro.to_csv(CSV/'04_macro_anual.csv', index=False, encoding='utf-8-sig')
print(f"✓ Macro: {len(df_macro)}")

# Agrícolas BR
df_agro = pd.DataFrame(parse_yearly_dict(extrai_obj('AGRICOLAS_BR'))).rename(columns={
    'feijao':'feijao_carioca_brl_sc60', 'mandioca':'mandioca_raiz_brl_ton',
    'cebola':'cebola_brl_cx20', 'leite':'leite_produtor_brl_litro'
})
df_agro.to_csv(CSV/'05_agricolas_br.csv', index=False, encoding='utf-8-sig')
print(f"✓ Agrícolas BR: {len(df_agro)}")

# Sazonalidades
df_saz_soja = pd.DataFrame(parse_objects(extrai_array('SAZONAL')))
df_saz_soja.to_csv(CSV/'06_sazonalidade_soja.csv', index=False, encoding='utf-8-sig')
print(f"✓ Sazonalidade soja: {len(df_saz_soja)}")

df_saz_fert = pd.DataFrame(parse_objects(extrai_array('SAZONAL_FERT')))
df_saz_fert.to_csv(CSV/'07_sazonalidade_fertilizantes.csv', index=False, encoding='utf-8-sig')
print(f"✓ Sazonalidade fert: {len(df_saz_fert)}")

# Curvas de futuros
df_cs = pd.DataFrame(parse_objects(extrai_array('CURVA_SOJA')))
df_cs.to_csv(CSV/'08_curva_soja_cbot.csv', index=False, encoding='utf-8-sig')
df_cu = pd.DataFrame(parse_objects(extrai_array('CURVA_UREIA')))
df_cu.to_csv(CSV/'09_curva_ureia.csv', index=False, encoding='utf-8-sig')
df_cm = pd.DataFrame(parse_objects(extrai_array('CURVA_MAP')))
df_cm.to_csv(CSV/'10_curva_map.csv', index=False, encoding='utf-8-sig')
print(f"✓ Curvas: soja {len(df_cs)} · ureia {len(df_cu)} · MAP {len(df_cm)}")

# USDA WORLD + Conab BR
df_wasde = pd.DataFrame(parse_objects(extrai_array('USDA_WORLD')))
df_wasde.to_csv(CSV/'11_usda_wasde_mundial.csv', index=False, encoding='utf-8-sig')
print(f"✓ USDA WASDE: {len(df_wasde)}")

df_conab = pd.DataFrame(parse_objects(extrai_array('CONAB_BR')))
df_conab.to_csv(CSV/'12_conab_brasil.csv', index=False, encoding='utf-8-sig')
print(f"✓ Conab BR: {len(df_conab)}")

# Eventos
df_eventos_str = extrai_array('EVENTOS_CHAVE')
if df_eventos_str:
    df_ev = pd.DataFrame(parse_objects(df_eventos_str))
    df_ev.to_csv(CSV/'13_eventos_chave.csv', index=False, encoding='utf-8-sig')
    print(f"✓ Eventos: {len(df_ev)}")
else:
    df_ev = None
    print("(EVENTOS_CHAVE não encontrado)")

# Save dfs for next step
import pickle
DFS = {
    '01_Soja_CEPEA_Paranagua': df_soja,
    '02_Milho_CEPEA_Campinas': df_milho,
    '03_Boi_vivo_RS': df_boi,
    '04_Macro_anual': df_macro,
    '05_Agricolas_BR': df_agro,
    '06_Sazonalidade_Soja': df_saz_soja,
    '07_Sazonalidade_Fertilizantes': df_saz_fert,
    '08_Curva_Soja_CBOT': df_cs,
    '09_Curva_Ureia': df_cu,
    '10_Curva_MAP': df_cm,
    '11_USDA_WASDE_Mundial': df_wasde,
    '12_CONAB_Brasil': df_conab,
}
if df_ev is not None: DFS['13_Eventos_chave'] = df_ev
with open('/home/claude/db_build/dfs.pkl', 'wb') as f: pickle.dump(DFS, f)
print(f"\n→ Total: {len(DFS)} datasets prontos")
