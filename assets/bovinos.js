/* BinMarket · Gado de corte RS
   Cotação inicial: NESPro/UFRGS, painel consultado em 21/10/2026, última semana: 14/10/2026.
   Base inicial de 8 semanas. Atualizador GitHub Actions publica CSV com novas coletas NESPro.
   Este módulo não interfere no React do painel de soja. */
(() => {
  'use strict';
  const STORAGE_KEY = 'binmarket_bovinos_nespro_v1';
  const KEYS = ['pv_macho','pc_macho','pv_femea','pc_femea','terneiro','terneira','novilho','novilha','vaca_invernar','vaca_prenhe'];
  const CATS = {
    pv_macho: 'Boi gordo · PV', pc_macho: 'Boi gordo · carcaça',
    pv_femea: 'Vaca gorda · PV', pc_femea: 'Vaca gorda · carcaça',
    terneiro: 'Terneiro · 6–12 meses', terneira: 'Terneira · 6–12 meses',
    novilho: 'Novilho · 13–24 meses', novilha: 'Novilha · 13–24 meses',
    vaca_invernar: 'Vaca de invernar', vaca_prenhe: 'Vaca prenhe'
  };
  const BASE = [
    {data:'2026-08-26',pv_macho:13.15,pv_femea:11.85,terneiro:16.18,novilho:13.16},
    {data:'2026-09-02',pv_macho:12.95,pv_femea:11.65,terneiro:15.62,novilho:13.30},
    {data:'2026-09-09',pv_macho:12.95,pv_femea:11.40,terneiro:15.64,novilho:13.46},
    {data:'2026-09-16',pv_macho:12.75,pv_femea:10.90,terneiro:15.40,novilho:12.29},
    {data:'2026-09-23',pv_macho:12.65,pv_femea:10.65,terneiro:15.40,novilho:12.75},
    {data:'2026-09-30',pv_macho:12.65,pv_femea:10.65,terneiro:15.05,novilho:12.14},
    {data:'2026-10-07',pv_macho:12.65,pv_femea:10.50,terneiro:15.04,novilho:13.34},
    {data:'2026-10-14',pv_macho:12.65,pc_macho:24.25,pv_femea:10.50,pc_femea:22.00,terneiro:14.90,terneira:14.67,novilho:12.36,novilha:13.50,vaca_invernar:10.61,vaca_prenhe:11.77}
  ];
  // Variações publicadas para as categorias que ainda não têm duas observações em nossa amostra.
  const OFFICIAL_DELTAS = {pc_macho:0,pc_femea:0,terneira:0.89,novilha:5.63,vaca_invernar:3.11,vaca_prenhe:4.90};
  const $ = (s) => document.querySelector(s);
  const currency = (x) => Number.isFinite(x) ? x.toLocaleString('pt-BR',{style:'currency',currency:'BRL',minimumFractionDigits:2,maximumFractionDigits:2}) : '—';
  const fixed = (x,n=2) => Number.isFinite(x) ? x.toLocaleString('pt-BR',{minimumFractionDigits:n,maximumFractionDigits:n}) : '—';
  const pct = (x,n=1) => Number.isFinite(x) ? `${x>0?'+':''}${fixed(x,n)}%` : 'n/d';
  const datePt = (s) => /^\d{4}-\d\d-\d\d$/.test(s) ? `${s.slice(8,10)}/${s.slice(5,7)}/${s.slice(0,4)}` : '—';
  const parseDate = (s) => {
    s=String(s||'').trim();let m;
    if((m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s)))s=`${m[3]}-${m[2]}-${m[1]}`;
    if(!/^\d{4}-\d{2}-\d{2}$/.test(s))return null;
    const d=new Date(s+'T12:00:00Z');
    return Number.isNaN(d.getTime())||d.toISOString().slice(0,10)!==s?null:s;
  };
  const parseValue = (v) => {
    const s=String(v??'').trim().replace(/\s/g,'').replace(/R\$/gi,'');
    if(!s||s==='—'||s==='-')return null;
    let t=s;
    if(t.includes(',') && t.includes('.'))t=t.replace(/\./g,'').replace(',','.');
    else if(t.includes(','))t=t.replace(',','.');
    const n=Number(t);return Number.isFinite(n)&&n>0&&n<100000?n:null;
  };
  const normalize = (s) => String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');
  const ALIASES = {
    pv_macho:['pv_macho','boi_gordo','boi_pv','boi_gordo_pv','boi_gordo_peso_vivo','macho_pv','boi_vivo'],
    pc_macho:['pc_macho','boi_pc','boi_carcaca','macho_pc','boi_gordo_carcaca'],
    pv_femea:['pv_femea','vaca_gorda','vaca_pv','vaca_gorda_pv','femea_pv','vaca_gorda_peso_vivo'],
    pc_femea:['pc_femea','vaca_pc','vaca_carcaca','femea_pc'],
    terneiro:['terneiro','terneiro_6_12m','terneiro_6_12_meses','bezerro'],
    terneira:['terneira','terneira_6_12m','bezerra'],
    novilho:['novilho','novilho_13_24m','novilho_13_24_meses'],
    novilha:['novilha','novilha_13_24m'],
    vaca_invernar:['vaca_invernar','vaca_de_invernar','vaca_invernada'],
    vaca_prenhe:['vaca_prenhe','vaca_prenha','vaca_gestante']
  };
  const findKey=(v)=>KEYS.find(k=>ALIASES[k].includes(normalize(v)))||null;
  const cloneBase=()=>BASE.map(r=>({...r}));
  const cleanRows = (raw) => {
    const result=[];
    if(!Array.isArray(raw))return result;
    for(const obj of raw){if(!obj || typeof obj!=='object')continue;
      const d=parseDate(obj.data);if(!d)continue;
      const r={data:d};for(const key of KEYS){const v=parseValue(obj[key]);if(v!==null)r[key]=v;}
      if(Object.keys(r).length>1)result.push(r);
    }
    const dates=new Map();for(const r of result){const old=dates.get(r.data)||{data:r.data};dates.set(r.data,{...old,...r});}
    return Array.from(dates.values()).sort((a,b)=>a.data.localeCompare(b.data));
  };
  let officialRows=cloneBase();
  let rows=cloneBase();
  try{const saved=localStorage.getItem(STORAGE_KEY);if(saved){const parsed=cleanRows(JSON.parse(saved));if(parsed.length)rows=cleanRows([...rows,...parsed]);}}catch(e){/* armazenamento opcional */}
  let months=3;
  const num=(s,fallback)=>{const e=$(s);const n=Number(e?.value);return Number.isFinite(n)?n:fallback;};
  const last=()=>rows[rows.length-1]||{};
  const seriesFor=(key)=>rows.filter(r=>Number.isFinite(r[key]));
  const deltaFor=(key)=>{
    const s=seriesFor(key),recent=s[s.length-1];if(!recent)return {n:null,official:false};
    if(s.length>1){const a=s[s.length-1],b=s[s.length-2];return {n:(a[key]/b[key]-1)*100,official:false};}
    if(recent.data==='2026-10-14'&&Number.isFinite(OFFICIAL_DELTAS[key]))return {n:OFFICIAL_DELTAS[key],official:true};
    return {n:null,official:false};
  };
  function renderKpis(){
    const group=(key)=>{
      const series=seriesFor(key),obs=series[series.length-1]||{};
      const v=obs[key];const {n,official}=deltaFor(key);const klass=n===null||Math.abs(n)<.005?'flat':n>0?'up':'down';
      const arrow=n===null?'·':Math.abs(n)<.005?'▬':n>0?'▲':'▼';
      return `<article class="kpi"><div class="kpi-label">${CATS[key]}</div><div class="kpi-price">${Number.isFinite(v)?currency(v):'—'}<small>/kg</small></div><div class="delta ${klass}">${arrow} ${pct(n)} ${n===null?'· sem comparação':''}</div>${official?'<div class="kpi-note">Variação informada pelo NESPro*</div>':(obs.data&&obs.data!==last().data?`<div class="kpi-note">Última cotação: ${datePt(obs.data)} (anterior)</div>`:'')}</article>`;
    };
    $('#slaughterCards').innerHTML=['pv_macho','pc_macho','pv_femea','pc_femea'].map(group).join('');
    $('#replacementCards').innerHTML=['terneiro','novilho','vaca_invernar','vaca_prenhe','terneira','novilha'].map(group).join('');
    const d=last().data;
    $('#lastDate').textContent=datePt(d);
    $('#dataWarningDate').textContent=datePt(d);
    $('#sourceDate').textContent=d?`${d.slice(8,10)} / ${d.slice(5,7)} / ${d.slice(0,4)}`:'Sem dados';
    $('#seedNote').textContent=`Base carregada · ${rows.length} datas · campos ausentes preservados`;
    const age=d?Math.floor((Date.now()-Date.parse(d+'T12:00:00Z'))/86400000):null;
    const warning=$('#freshnessStatus');
    if(warning)warning.textContent=age===null?'Data não disponível':age>14?`ATENÇÃO: última coleta tem aproximadamente ${age} dias; confira a fonte.`:age>=0?`Coleta publicada há ${age} dia(s).`:'Coleta registrada.';
    const getMove=(key)=>deltaFor(key).n;
    const boi=getMove('pv_macho'),vaca=getMove('pv_femea'),terneiro=getMove('terneiro'),novilho=getMove('novilho');
    const br=(n,label)=>Number.isFinite(n)?`${label} ${n>0?'+':''}${fixed(n,1)}%`:`${label} sem comparação`; 
    const sl=[br(boi,'Boi gordo PV'),br(vaca,'vaca gorda PV')].join(' · ');
    const repo=[br(terneiro,'terneiro'),br(novilho,'novilho')].join(' · ');
    const agio=Number.isFinite(last().terneiro)&&Number.isFinite(last().pv_macho)?(last().terneiro/last().pv_macho-1)*100:NaN;
    const agioText=Number.isFinite(agio)?`O ágio do terneiro sobre o boi é ${fixed(agio,1)}% no preço/kg, sem ponderar demais custos.`:'Não há dados simultâneos suficientes para calcular o ágio da última data.';
    $('#marketReadout').textContent=`Abate: ${sl}. Reposição: ${repo}. ${agioText} Indicadores descrevem o mercado observado; não indicam lucro futuro nem substituem ofertas locais.`;
  }
  function rangeRows(){
    if(!months||!rows.length)return rows;
    const latest=new Date(last().data+'T12:00:00Z');
    latest.setUTCMonth(latest.getUTCMonth()-months);
    const s=latest.toISOString().slice(0,10);
    return rows.filter(r=>r.data>=s);
  }
  function renderChart(el,lines){
    const data=rangeRows();
    const points=data.filter(r=>lines.some(l=>Number.isFinite(r[l.key])));
    if(!points.length){$(el).innerHTML='<p style="padding:65px 12px;text-align:center;color:#859180;font-size:12px">Sem observações neste intervalo.</p>';return;}
    const all=points.flatMap(r=>lines.map(l=>r[l.key]).filter(Number.isFinite));
    let lo=Math.min(...all),hi=Math.max(...all);const spread=hi-lo;
    const buffer=Math.max(spread*.15,.30);lo=Math.max(0,lo-buffer);hi+=buffer;
    const W=560,H=248,L=52,R=17,T=15,B=35,PW=W-L-R,PH=H-T-B;
    const xs=points.map(p=>Date.parse(p.data+'T12:00:00Z'));
    let minX=xs[0],maxX=xs[xs.length-1];if(minX===maxX)maxX+=86400000;
    const x=(r)=>L+(Date.parse(r.data+'T12:00:00Z')-minX)/(maxX-minX)*PW;
    const y=(v)=>T+PH-(v-lo)/(hi-lo)*PH;
    let html=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="Série de preços" role="img">`;
    for(let i=0;i<=4;i++){const yy=T+i*PH/4,price=hi-(hi-lo)*i/4;html+=`<line class="gridline" x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}"/><text class="axis-label" x="${L-9}" y="${yy+4}" text-anchor="end">${fixed(price,2)}</text>`;}
    const step=Math.max(1,Math.ceil(points.length/5));
    for(let i=0;i<points.length;i++){if(i%step===0||i===points.length-1)html+=`<text class="axis-label" x="${x(points[i])}" y="${H-8}" text-anchor="middle">${points[i].data.slice(8,10)}/${points[i].data.slice(5,7)}</text>`;}
    for(const line of lines){
      let started=false;let d='';
      // Each missing observation produces a break in the line (no invented interpolation).
      for(const r of points){if(!Number.isFinite(r[line.key])){started=false;continue;}d+=`${started?'L':'M'}${x(r).toFixed(1)},${y(r[line.key]).toFixed(1)} `;started=true;}
      html+=`<path d="${d.trim()}" fill="none" stroke="${line.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
      points.forEach((r,i)=>{if(Number.isFinite(r[line.key]))html+=`<circle cx="${x(r).toFixed(1)}" cy="${y(r[line.key]).toFixed(1)}" r="3.2" fill="${line.color}"/><circle class="chart-hit" data-date="${r.data}" data-key="${line.key}" data-val="${r[line.key]}" data-color="${line.color}" cx="${x(r).toFixed(1)}" cy="${y(r[line.key]).toFixed(1)}" r="11"/>`;});
    }
    html+='</svg>';$(el).innerHTML=html;
    $(el).querySelectorAll('.chart-hit').forEach(hit=>{
      hit.addEventListener('pointerenter',e=>showTip(e,hit));
      hit.addEventListener('pointermove',e=>showTip(e,hit));
      hit.addEventListener('pointerleave',()=>$('#chartTooltip').hidden=true);
    });
  }
  function showTip(e,hit){
    const tip=$('#chartTooltip');
    tip.textContent=`${datePt(hit.dataset.date)} · ${CATS[hit.dataset.key]}: ${currency(Number(hit.dataset.val))}/kg`;
    tip.hidden=false;
    tip.style.left=`${Math.min(e.clientX+14,window.innerWidth-tip.offsetWidth-10)}px`;
    tip.style.top=`${Math.max(8,e.clientY-56)}px`;
  }
  function renderCharts(){
    renderChart('#chartSlaughter',[{key:'pv_macho',color:'#51772d'},{key:'pv_femea',color:'#b88342'}]);
    renderChart('#chartReplacement',[{key:'terneiro',color:'#426c91'},{key:'novilho',color:'#9f705e'}]);
    const period=rangeRows();
    $('#coverageNote').textContent=period.length?`Cobertura exibida: ${datePt(period[0].data)} a ${datePt(period[period.length-1].data)} · ${period.length} datas. A ausência de registros fora desse intervalo não significa estabilidade de preço.`:'Sem dados no período escolhido.';
  }
  function ratioHtml(title,value,description,badge,unit){
    return `<article class="ratio"><small>INDICADOR</small><h3>${title}</h3><div class="ratio-number">${Number.isFinite(value)?fixed(value,unit==='%'?1:2):'—'}${unit==='%'?'%':''}</div><p>${description}</p><span class="badge">${badge}</span></article>`;
  }
  function renderRatios(){
    const r=last();const mb=r.pv_macho,fb=r.pv_femea,t=r.terneiro,n=r.novilho;
    const v=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)&&b>0?a/b:NaN;
    const h1=v(mb*480,t*180),h2=v(mb*480,n*300),premium=(v(t,mb)-1)*100;
    const fem=v(fb,mb)*100,pren=(v(r.vaca_prenhe,fb)-1)*100;
    $('#ratioCards').innerHTML=[
      ratioHtml('Boi gordo : terneiro',h1,'Cabeças de terneiro de 180 kg adquiridas com a receita de 1 boi de 480 kg.','480 kg ÷ 180 kg · premissas fixas','x'),
      ratioHtml('Boi gordo : novilho',h2,'Cabeças de novilho de 300 kg adquiridas com a receita de 1 boi de 480 kg.','480 kg ÷ 300 kg · premissas fixas','x'),
      ratioHtml('Ágio do kg de terneiro',premium,'Quanto o preço/kg de terneiro supera o preço/kg do boi gordo.','ágio maior = reposição relativamente cara','%'),
      ratioHtml('Vaca gorda / boi gordo',fem,'Preço por kg PV da vaca gorda em relação ao do boi gordo.','comparação relativa entre categorias','%'),
      ratioHtml('Prêmio da vaca prenhe',pren,'Prêmio em R$/kg da vaca prenhe em relação à vaca gorda (PV).','cuidado: finalidade e condições variam','%')
    ].join('');
  }
  function renderDetail(){
    const key=$('#categorySelect').value||'pv_macho',data=seriesFor(key),tail=data.slice(-1)[0];
    const values=data.map(r=>r[key]);const n=values.length;
    const mean=n?values.reduce((a,b)=>a+b,0)/n:NaN;
    const min=n?Math.min(...values):NaN,max=n?Math.max(...values):NaN;
    const from=n?data[0][key]:NaN,change=n>1?(tail[key]/from-1)*100:NaN;
    const stats=[
      ['ÚLTIMA COTAÇÃO',n?currency(tail[key]):'—',n?datePt(tail.data):'Sem observação'],
      ['VARIAÇÃO NO PERÍODO',pct(change),n>1?`desde ${datePt(data[0].data)}`:'Histórico insuficiente'],
      ['PREÇO MÍNIMO',currency(min),n?datePt(data[values.indexOf(min)].data):'—'],
      ['PREÇO MÁXIMO',currency(max),n?datePt(data[values.indexOf(max)].data):'—'],
      ['MÉDIA DA AMOSTRA',currency(mean),`${n} observação(ões) · não é média histórica longa`],
      ['DATAS COBERTAS',String(n),n?`${datePt(data[0].data)} até ${datePt(tail.data)}`:'—']
    ];
    $('#categoryStats').innerHTML=stats.map(s=>`<div class="stat"><small>${s[0]}</small><strong>${s[1]}</strong><span>${s[2]}</span></div>`).join('');
    let html='';data.slice(-30).reverse().forEach((r,i)=>{const j=data.findIndex(z=>z.data===r.data);const before=j>0?data[j-1]:null;let diff=before?(r[key]/before[key]-1)*100:null;let source='';if(diff===null&&r.data==='2026-10-14'&&Number.isFinite(OFFICIAL_DELTAS[key])){diff=OFFICIAL_DELTAS[key];source='*';}
      const cls=diff===null||Math.abs(diff)<.005?'':diff>0?'style="color:#547b31"':'style="color:#b45444"';
      html+=`<tr><td>${datePt(r.data)}</td><td>${currency(r[key])}</td><td ${cls}>${pct(diff)}${source}</td></tr>`;
    });
    $('#historyRows').innerHTML=html||'<tr><td colspan="3">Nenhuma observação disponível.</td></tr>';
  }
  function renderSim(){
    const buy=num('#purchasePrice',NaN),sell=num('#salePrice',NaN),bw=num('#purchaseWeight',NaN),sw=num('#saleWeight',NaN),cost=num('#costHead',NaN),heads=num('#heads',NaN);
    const okay=[buy,sell,bw,sw,cost,heads].every(Number.isFinite)&&buy>0&&sell>0&&bw>0&&sw>0&&heads>=1&&cost>=0;
    const revenue=okay?sell*sw:NaN,purchase=okay?buy*bw:NaN,margin=okay?revenue-purchase-cost:NaN,breakeven=okay?(purchase+cost)/sw:NaN;
    $('#marginHead').textContent=currency(margin);
    $('#marginHead').style.color=margin<0?'#f1baa7':'#d0e4a8';
    $('#marginDescription').textContent=okay?`${margin<0?'Déficit':'Resultado'} antes de outros custos não informados, para ${fixed(sw,0)} kg vendidos por animal. Ganho físico pressuposto: ${fixed(sw-bw,0)} kg.`:'Preencha todos os campos com valores válidos.';
    $('#revenueHead').textContent=currency(revenue);$('#purchaseHead').textContent=currency(purchase);$('#breakEven').textContent=`${currency(breakeven)}/kg`;
    $('#marginTotal').textContent=currency(margin*heads);
  }
  const latestCategoryPrice=(key)=>last()[key];
  function setQuotePrices(){
    const cat=$('#simCategory').value;
    const bp=latestCategoryPrice(cat),sp=latestCategoryPrice('pv_macho');
    if(Number.isFinite(bp))$('#purchasePrice').value=bp.toFixed(2);
    if(Number.isFinite(sp))$('#salePrice').value=sp.toFixed(2);
    renderSim();
  }
  function renderAll(){renderKpis();renderCharts();renderRatios();renderDetail();renderSim();}
  function csvRows(text){
    // Quoted CSV, semicolon or comma; supports escaped double quotes and line breaks.
    text=text.replace(/^\uFEFF/,'');
    const line=text.split(/\r?\n/,1)[0]||'';
    const delimiter=(line.match(/;/g)||[]).length>=(line.match(/,/g)||[]).length?';':',';
    const result=[],arr=[];let field='',quoted=false;
    for(let i=0;i<text.length;i++){
      const c=text[i];
      if(quoted){if(c==='"'&&text[i+1]==='"'){field+='"';i++;}else if(c==='"'){quoted=false;}else{field+=c;}}
      else if(c==='"')quoted=true;
      else if(c===delimiter){arr.push(field);field='';}
      else if(c==='\n'){arr.push(field.replace(/\r$/,''));if(arr.some(t=>t.trim()))result.push(arr.splice(0));else arr.length=0;field='';}
      else field+=c;
    }
    arr.push(field.replace(/\r$/,''));if(arr.some(t=>t.trim()))result.push(arr);
    return result;
  }
  function parseCsv(text){
    const lines=csvRows(text);if(lines.length<2)throw new Error('O arquivo não contém dados após o cabeçalho.');
    if(lines.length>20000)throw new Error('Arquivo muito grande (máximo 20 mil linhas).');
    const head=lines[0].map(normalize);
    const dateIx=head.findIndex(h=>['data','date','semana'].includes(h));
    if(dateIx<0)throw new Error('É necessário incluir uma coluna "data".');
    const catIx=head.findIndex(h=>['categoria','category','indicador'].includes(h));
    const priceIx=head.findIndex(h=>['preco','preco_kg','valor','r_kg','price'].includes(h));
    const long=catIx>=0&&priceIx>=0;
    const wide=head.map((h,i)=>({key:findKey(h),i})).filter(x=>x.key);
    if(!long&&!wide.length)throw new Error('Não reconheci colunas de preços. Consulte o modelo na página.');
    const map=new Map();let accepted=0,ignored=0;
    for(const cells of lines.slice(1)){
      const d=parseDate(cells[dateIx]);if(!d){ignored++;continue;}
      const row=map.get(d)||{data:d};let updated=0;
      if(long){const key=findKey(cells[catIx]),v=parseValue(cells[priceIx]);if(key&&v!==null){row[key]=v;updated++;}}
      else{for(const entry of wide){const v=parseValue(cells[entry.i]);if(v!==null){row[entry.key]=v;updated++;}}}
      if(updated){map.set(d,row);accepted+=updated;}else ignored++;
    }
    if(!accepted)throw new Error('Nenhum valor de preço válido encontrado.');
    return {records:Array.from(map.values()),accepted,ignored};
  }
  function mergeRecords(current,addition){const merged=new Map(current.map(r=>[r.data,{...r}]));for(const r of addition){merged.set(r.data,{...(merged.get(r.data)||{data:r.data}),...r});}return cleanRows(Array.from(merged.values()));}
  function persist(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(rows));return true;}catch(e){return false;}}
  function csvExport(){
    const head=['data',...KEYS],values=[head.join(';')];
    rows.forEach(r=>values.push([datePt(r.data),...KEYS.map(k=>Number.isFinite(r[k])?r[k].toFixed(2).replace('.',','):'')].join(';')));
    const blob=new Blob(['\uFEFF'+values.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8;'}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=`binmarket_gado_rs_ate_${last().data}.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function setStatus(s,isError=false){const el=$('#importStatus');el.textContent=s;el.style.color=isError?'#b45444':'#527e31';}
  function setup(){
    const select=$('#categorySelect');select.innerHTML=KEYS.map(k=>`<option value="${k}">${CATS[k]}</option>`).join('');
    select.value='pv_macho';select.addEventListener('change',renderDetail);
    document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>{months=Number(b.dataset.period);document.querySelectorAll('[data-period]').forEach(x=>x.classList.toggle('active',x===b));renderCharts();}));
    $('#simCategory').addEventListener('change',()=>{$('#purchaseWeight').value=$('#simCategory').value==='terneiro'?'180':'300';setQuotePrices();});
    document.querySelectorAll('#simular input').forEach(el=>el.addEventListener('input',renderSim));
    $('#resetPrices').addEventListener('click',setQuotePrices);
    $('#csvInput').addEventListener('change',async(e)=>{
      const f=e.target.files?.[0];if(!f)return;
      try{if(f.size>2*1024*1024)throw new Error('Arquivo excede 2 MB.');
        const data=parseCsv(await f.text());rows=mergeRecords(rows,data.records);const saved=persist();renderAll();
        setStatus(`${data.accepted} preço(s) importado(s); ${data.ignored} linha(s) ignorada(s); ${rows.length} semanas na base. ${saved?'Salvo neste navegador.':'Não foi possível persistir no navegador; exporte uma cópia.'}`);
      }catch(error){setStatus(error?.message||'Erro ao importar CSV.',true);}finally{e.target.value='';}
    });
    $('#exportCsv').addEventListener('click',csvExport);
    $('#resetData').addEventListener('click',()=>{if(!confirm('Descartar importações locais e restaurar a base oficial publicada no GitHub?'))return;rows=officialRows.map(r=>({...r}));try{localStorage.removeItem(STORAGE_KEY);}catch(e){}renderAll();setQuotePrices();setStatus('Base oficial restaurada.');});
    renderAll();setQuotePrices();
    refreshOfficialCsv();
  }
  async function refreshOfficialCsv(){
    const status=$('#remoteUpdateStatus');
    try{
      // Sem cache: o CSV novo sempre prevalece sobre preços importados anteriormente.
      const r=await fetch('data/bovinos/historico.csv', {cache:'no-store'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      const parsed=parseCsv(await r.text());
      officialRows=mergeRecords(cloneBase(),parsed.records);
      rows=mergeRecords(rows,officialRows);
      renderAll();setQuotePrices();
      if(status)status.textContent=`Arquivo do GitHub carregado · ${officialRows.length} datas · última coleta ${datePt(officialRows[officialRows.length-1].data)}.`;
    }catch(e){
      if(status)status.textContent=`Não foi possível sincronizar com o GitHub (${e?.message||'erro de rede'}). Exibindo dados salvos disponíveis.`;
      console.warn('Sincronização do gado indisponível:',e);
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
})();
