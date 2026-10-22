#!/usr/bin/env python3
"""Auditoria automatica de cobertura das fontes do BinMarket.

Uma execucao do GitHub Actions nao e sinonimo de nova cotacao. Cada grupo e
classificado segundo o valor efetivamente publicado e a data da fonte.
"""
from __future__ import annotations
from datetime import date,datetime
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'data'
NOW=date.today()
MARKET=BASE/'fontes/mercado.json'
NESPRO=BASE/'bovinos/atualizacao.json'
OUT=BASE/'fontes/auditoria.json'

def read(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError):return {}

def days(d):
    try:
        if not d:return None
        return (NOW-date.fromisoformat(d[:10])).days
    except (TypeError,ValueError):return None

def status(name,rec,period,notes):
    ref=rec.get('data_referencia') or rec.get('ultima_coleta')
    age=days(ref)
    if name in ('conab_safra','usda_psd'):
        # Fontes por safra: verificar quando a coleta ocorreu, nao deduzir
        # idade a partir do ano de comercializacao.
        checked=rec.get('verificado_em')
        age=days(checked)
    state='atualizado' if rec.get('status')=='ok' and age is not None and age<=period else ('falha' if rec.get('status')=='falha' else 'defasado')
    return {'tipo':'fonte_automatica','situacao':state,'data_referencia':ref,
            'dias_desde_referencia':age,'fonte':rec.get('url') or rec.get('fonte'),
            'periodicidade_tolerancia_dias':period,'observacao':notes}

def main():
    m=read(MARKET).get('fontes',{})
    g=read(NESPRO)
    if g:
        g=dict(g);g['status']='ok' if g.get('ultima_coleta') else 'falha'
        g['data_referencia']=g.get('ultima_coleta')
        g['url']=g.get('fonte')
    covered={
        'cotrijuc_soja':status('cotrijuc_soja',m.get('cotrijuc_soja',{}),5,'Preco local de balcao de soja'),
        'cepea_soja':status('cepea_soja',m.get('cepea_soja',{}),5,'Referencia portuaria, nao preco local'),
        'milho_cepea':status('milho_cepea',m.get('milho_cepea',{}),5,'Indicador milho Esalq/B3'),
        'cbot_soja':status('cbot_soja',m.get('cbot_soja',{}),5,'Futuro de soja; contrato deve ser identificado'),
        'usda_psd':status('usda_psd',m.get('usda_psd',{}),65,'PSD Brasil/EUA, ano de comercializacao USDA'),
        'conab_safra':status('conab_safra',m.get('conab_safra',{}),95,'Somente producao nacional, nao custos individuais'),
        'nespro_gado':status('nespro_gado',g,15,'Cotacao semanal RS, nao historico de varejo e ovinos'),
    }
    snapshots={
        'historico_usda_mundo':'Grafico mundial historico compilado, nao conectado a uma serie mundial automatica',
        'historico_completo_cepea':'Serie trimestral antiga nao recebe automaticamente todas as cotacoes diarias',
        'historico_milho_trimestral':'Serie trimestral antiga separada da cotacao diaria automatica',
        'historico_multicommodities':'Comparacoes anuais incluem varias series compiladas',
        'preco_local_frete':'Frete local varia por propriedade, prazo e transportador; premissa de simulacao',
        'premio_portuario':'Premio base local nao e cotacao diaria contratada; premissa de simulacao',
        'custos_agricolas':'Custos de sementes, defensivos, terra e maquinas sao cenarios personalizaveis',
        'outros_precos_mercado':'Ouro, cobre, ureia, Hilux e demais comparacoes anuais sao series historicas de referencia',
        'ovinos_e_varejo_nespro':'Nao integrados ao painel de gado de corte',
    }
    data={
        'gerado_em':datetime.now().astimezone().isoformat(timespec='seconds'),
        'resumo':{'fontes_automaticas_monitoradas':len(covered),
                  'fontes_com_dados_recentes':sum(1 for v in covered.values() if v['situacao']=='atualizado'),
                  'modulos_sem_automacao_completa':len(snapshots),
                  'cobertura_integral':False},
        'indicadores_automaticos':covered,
        'series_nao_integralmente_automaticas':snapshots,
        'aviso':'Coleta automatica nao significa que todos os campos do site estao sincronizados. Sem valores inventados.'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    if not OUT.exists() or OUT.read_text(encoding='utf-8')!=content:OUT.write_text(content,encoding='utf-8')
    print(f"Auditoria: {data['resumo']}",flush=True)

if __name__=='__main__':
    main()
