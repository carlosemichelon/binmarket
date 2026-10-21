/* Transparência sobre qualidade dos dados. Não muda os valores do simulador. */
(() => {
  'use strict';
  const labels = {
    cepea_soja:'Soja CEPEA · Paranaguá',
    conab_safra:'Conab · série de safra',
    usda_psd:'USDA · soja Brasil/EUA',
    nespro_gado:'NESPro · gado RS'
  };
  const limits = {cepea_soja:6,conab_safra:120,usda_psd:60,nespro_gado:15};
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
    if (key==='conab_safra' && !str) return ['atencao','Arquivo recebido; data não identificada'];
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
  const render=(items,checked)=>{
    let allOk=true, anyFail=false;
    box.querySelector('.bm-rows').innerHTML=Object.entries(items).map(([key,item])=>{
      const [kind,label]=state(key,item);
      allOk&&=kind==='ok';anyFail ||= kind==='falha';
      const info=item?.data_referencia || item?.ultima_coleta;
      const uri=item?.url || item?.fonte || '';
      const link=(typeof uri==='string'&&/^https:\/\//.test(uri))?` <a href="${escapeHtml(uri)}" target="_blank" rel="noopener noreferrer">Fonte</a>`:'';
      const when=key==='usda_psd'&&info?'Safra '+info:fmtDate(info);
      return `<div class="bm-row"><strong>${escapeHtml(labels[key]||key)}</strong><span class="bm-status ${kind}">${escapeHtml(label)}</span><br/><small>Referência: ${escapeHtml(when)} · ${link}</small>${item?.erro?`<br/><small>Erro: ${escapeHtml(String(item.erro).slice(0,140))}</small>`:''}</div>`;
    }).join('')+`<small>Última verificação registrada: ${escapeHtml(checked?checked.replace('T',' ').slice(0,16):'não disponível')}.</small>`;
    box.querySelector('.bm-dot').className='bm-dot '+(anyFail?'falha':allOk?'ok':'');
  };
  Promise.allSettled([
    fetch('data/fontes/mercado.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}),
    fetch('data/bovinos/atualizacao.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();})
  ]).then(([market,gado])=>{
    const m=market.status==='fulfilled'?market.value:{};
    const g=gado.status==='fulfilled'?gado.value:{};
    render({...m.fontes,nespro_gado:{status:g.ultima_coleta?'ok':'pendente', data_referencia:g.ultima_coleta,url:g.fonte||'https://bovinos-indices.nesproufrgs.com/',erro:g.erro}},m.verificado_em);
  }).catch(()=>render({fontes:{status:'falha',erro:'Falha ao ler manifesto de dados'}},null));
})();
