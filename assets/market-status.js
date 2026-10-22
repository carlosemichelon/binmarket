/* Transparência sobre qualidade dos dados. Não muda os valores do simulador. */
(() => {
  'use strict';
  const labels = {
    cepea_soja:'Soja CEPEA · Paranaguá',
    cotrijuc_soja:'Soja balcão · Cotrijuc Júlio de Castilhos',
    cbot_soja:'Soja futuros · CBOT (Chicago)',
    milho_cepea:'Milho · indicador CEPEA/Esalq-B3',
    conab_safra:'Conab · série de safra',
    usda_psd:'USDA · soja Brasil/EUA',
    nespro_gado:'NESPro · gado RS'
  };
  const limits = {cepea_soja:5,cotrijuc_soja:5,cbot_soja:5,milho_cepea:5,conab_safra:120,usda_psd:60,nespro_gado:15};
  const fmtDate=(v)=>/^\d{4}-\d{2}-\d{2}/.test(v||'')?v.slice(0,10).split('-').reverse().join('/'):'não informada';
  const state=(key,rec)=>{
    if (!rec || rec.status==='pendente') return ['pendente','Não verificado'];
    if (rec.status==='falha') return ['falha','Falha na coleta'];
    if (rec.status!=='ok') return ['pendente','Sem confirmação'];
    const str=rec.data_referencia;
    if (key==='usda_psd') {
      const year=Number(str);
      if (!Number.isFinite(year)) return ['atencao','Sem safra identificada'];
      return year < new Date().getFullYear()-2?['atencao','Safra antiga']:['ok','Coleta concluída'];
    }
    if (key==='conab_safra' && rec.ultima_safra) return ['ok','Planilha e produção processadas'];
    if (key==='conab_safra' && !str) return ['atencao','Arquivo recebido; produção não extraída'];
    const today=new Date(),ref=new Date(`${str}T12:00:00Z`);
    if (!Number.isFinite(ref.getTime())) return ['atencao','Data de referência não disponível'];
    const age=(today-ref)/86400000;
    return age>limits[key]?['atencao','Fonte defasada']:['ok','Fonte recente'];
  };
  const escapeHtml=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const css=`#bm-dados{position:fixed;bottom:16px;right:16px;z-index:99999;font-family:system-ui,Arial,sans-serif;font-size:13px;color:#26352a;max-width:min(370px,calc(100vw - 32px))}#bm-dados button{font-family:inherit;cursor:pointer}#bm-dados .bm-trigger{display:flex;align-items:center;gap:8px;border-radius:40px;background:#fff;color:#243829;border:1px solid #b9cab5;padding:11px 15px;box-shadow:0 5px 20px #0002;font-weight:650}#bm-dados .bm-dot{width:9px;height:9px;border-radius:50%;background:#d5a33b;display:inline-block}#bm-dados .bm-dot.ok{background:#4b915c}#bm-dados .bm-dot.falha{background:#c45847}#bm-dados .bm-card{background:#fff;color:#26352a;border:1px solid #bfccbf;box-shadow:0 9px 30px #0003;padding:16px;border-radius:14px;max-height:70vh;overflow:auto;margin-bottom:9px}#bm-dados .bm-title{font-size:15px;font-weight:750;margin:0 0 8px}#bm-dados .bm-row{border-top:1px solid #e8ede7;padding:10px 0;line-height:1.4}#bm-dados .bm-row strong{display:block}#bm-dados .bm-row small{color:#526554;font-size:11px}#bm-dados .bm-row .bm-status{font-size:11px;font-weight:750}#bm-dados .bm-status.ok{color:#287b4a}#bm-dados .bm-status.falha{color:#b43e35}#bm-dados .bm-status.atencao{color:#95700b}#bm-dados .bm-footer{font-size:11px;line-height:1.45;color:#627064;margin:8px 0 0}#bm-dados a{color:#345a79}#bm-dados .bm-close{float:right;background:transparent;border:0;font-size:18px;padding:0 3px;color:#617060}`;
  const style=document.createElement('style');style.textContent=css;document.head.appendChild(style);
  const box=document.createElement('aside');box.id='bm-dados';box.setAttribute('aria-label','Estado das fontes de dados');
  box.innerHTML='<div class="bm-card" hidden><button type="button" class="bm-close" aria-label="Fechar">×</button><p class="bm-title">Qualidade e atualização dos dados</p><div class="bm-rows">Verificando fontes…</div><p class="bm-footer">Preços automáticos não são necessariamente novas cotações. Custos, fretes, prêmios locais e séries marcadas como estimativa continuam sendo premissas do simulador.</p></div><button class="bm-trigger" type="button" aria-expanded="false"><span class="bm-dot"></span> Fontes de dados</button>';
  document.body.appendChild(box);
  const card=box.querySelector('.bm-card'),btn=box.querySelector('.bm-trigger');
  const toggle=()=>{card.hidden=!card.hidden;btn.setAttribute('aria-expanded',String(!card.hidden));};
  btn.addEventListener('click',toggle);box.querySelector('.bm-close').addEventListener('click',toggle);
  const render=(items,checked,audit)=>{
    let allOk=true, anyFail=false;
    box.querySelector('.bm-rows').innerHTML=Object.entries(items).map(([key,item])=>{
      const [kind,label]=state(key,item);
      allOk&&=kind==='ok';anyFail ||= kind==='falha';
      const info=item?.data_referencia || item?.ultima_coleta;
      const uri=item?.url || item?.fonte || '';
      const link=(typeof uri==='string'&&/^https:\/\//.test(uri))?` <a href="${escapeHtml(uri)}" target="_blank" rel="noopener noreferrer">Fonte</a>`:'';
      const when=key==='usda_psd'&&info?'Safra '+info:key==='conab_safra'&&item?.ultima_safra?'Safra '+item.ultima_safra:fmtDate(info);
      const money=n=>Number(n).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
      const fmtMt=n=>(Number(n)/1000).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1});
      const extras=[];
      if(key==='cepea_soja' && Number.isFinite(Number(item?.valor)))extras.push('Cotação: R$ '+money(item.valor)+'/saca de 60 kg');
      if(key==='conab_safra' && Number.isFinite(Number(item?.producao_mil_ton)) && item?.producao_mil_ton!=null)extras.push('Brasil: '+fmtMt(item.producao_mil_ton)+' milhões t produzidas');
      if(key==='usda_psd' && item?.producao_br_mil_ton!=null)extras.push('Brasil: '+fmtMt(item.producao_br_mil_ton)+' milhões t');
      if(key==='usda_psd' && item?.producao_eua_mil_ton!=null)extras.push('EUA: '+fmtMt(item.producao_eua_mil_ton)+' milhões t');
      const detail=extras.length?'<br/><small>'+escapeHtml(extras.join(' · '))+'</small>':'';
      return `<div class="bm-row"><strong>${escapeHtml(labels[key]||key)}</strong><span class="bm-status ${kind}">${escapeHtml(label)}</span><br/><small>Referência: ${escapeHtml(when)} · ${link}</small>${detail}${item?.erro?`<br/><small>Erro: ${escapeHtml(String(item.erro).slice(0,140))}</small>`:''}</div>`;
    }).join('')+`<small>Última verificação registrada: ${escapeHtml(checked?checked.replace('T',' ').slice(0,16):'não disponível')}.</small>`;
    const pending=Object.entries(audit?.series_nao_integralmente_automaticas||{});
    const summary=audit?.resumo;
    if(summary){
      const note=document.createElement('div');
      note.className='bm-row';
      note.innerHTML='<strong>Cobertura efetiva do site</strong><small>'+
          escapeHtml(String(summary.fontes_com_dados_recentes))+' de '+escapeHtml(String(summary.fontes_automaticas_monitoradas))+
          ' fontes recentes; '+escapeHtml(String(summary.modulos_sem_automacao_completa))+
          ' grupos ainda contêm premissas ou séries históricas não integradas.</small>';
      const details=document.createElement('details');
      const title=document.createElement('summary');
      title.textContent='Ver grupos que ainda não são automáticos';
      details.appendChild(title);
      for(const [key,reason] of pending){
        const p=document.createElement('p');
        p.style.fontSize='11px';
        p.style.margin='8px 0';
        p.textContent=key.replaceAll('_',' ')+' — '+reason;
        details.appendChild(p);
      }
      note.appendChild(details);
      box.querySelector('.bm-rows').prepend(note);
    }
    // Nao usar verde para afirmar que TODO o painel esta automatizado.
    box.querySelector('.bm-dot').className='bm-dot '+(anyFail?'falha':allOk&&summary?.cobertura_integral?'ok':'');
  };
  Promise.allSettled([
    fetch('data/fontes/mercado.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}),
    fetch('data/bovinos/atualizacao.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}),
    fetch('data/fontes/auditoria.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();})
  ]).then(([market,gado,auditoria])=>{
    const m=market.status==='fulfilled'?market.value:{};
    const g=gado.status==='fulfilled'?gado.value:{};
    const a=auditoria.status==='fulfilled'?auditoria.value:null;
    render({...m.fontes,nespro_gado:{status:g.ultima_coleta?'ok':'pendente', data_referencia:g.ultima_coleta,url:g.fonte||'https://bovinos-indices.nesproufrgs.com/',erro:g.erro}},m.verificado_em,a);
  }).catch(()=>render({fontes:{status:'falha',erro:'Falha ao ler manifesto de dados'}},null,null));
})();
