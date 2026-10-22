#!/usr/bin/env node
/** Homologação do GitHub Pages em Chromium; grava evidências para o GitHub Actions.
 *  Não altera preços nem transforma cenários simulados em cotações reais.
 */
const {chromium} = require('playwright');
const fs = require('node:fs');
const BASE = 'https://carlosemichelon.github.io/binmarket/';
const OUT = 'qa-evidence';
fs.mkdirSync(OUT,{recursive:true});
const checks = {tested_at:new Date().toISOString(), url:BASE, checks:[], errors:[]};
const record=(name,ok,detail={})=>{
  checks.checks.push({name,ok,...detail});
  console.log((ok?'PASS':'FAIL')+' '+name, detail);
  if(!ok) checks.errors.push(name);
};
async function checkPublishedHTML(){
  let html='';
  for(let i=0;i<7;i++){
    const res=await fetch(BASE+'index.html?qa='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(30000)});
    if(res.ok)html=await res.text();
    if(html.includes('Futuro SJC da B3:') && html.includes('EXPLICA_ESTRATEGIAS[i].v'))break;
    await new Promise(resolve=>setTimeout(resolve,12000));
  }
  record('Pages responde HTML atualizado',html.includes('Futuro SJC da B3:') && html.includes('EXPLICA_ESTRATEGIAS[i].v'),
    {length:html.length});
  record('Correções de opções no Pages',html.includes('cenário editável') && !html.includes('Prêmio CALL venda (auto)'));
}
async function checkBrowser(browser,label,viewport) {
  const page=await browser.newPage({viewport,deviceScaleFactor:1});
  const runtimeErrors=[];
  page.on('pageerror',e=>runtimeErrors.push(String(e.message)));
  page.on('console',msg=>{if(msg.type()==='error')console.log('CONSOLE '+label+': '+msg.text().slice(0,320));});
  try {
    const response=await page.goto(BASE+'index.html?qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:65000});
    record(label+' HTTP',!!response&&response.status()===200,{http:response?.status()});
    await page.locator('#modulo-05').waitFor({state:'attached',timeout:50000});
    record(label+' React renderizou 05',await page.locator('#modulo-05').count()===1);
    record(label+' 17 módulos',await page.locator('section[id^="modulo-"]').count()===17);
    record(label+' prêmio Paranaguá separado',await page.getByText('Prêmios observados por vencimento',{exact:false}).count()>0);
    record(label+' sem erro de carregamento', !(await page.locator('#erro').isVisible()),{runtimeErrors});
    const buttons=page.locator('.estrat-toggle');
    record(label+' 9 estratégias',await buttons.count()===9);
    if(await buttons.count()===9){
      await buttons.first().click();
      record(label+' estratégia interativa',await page.getByText('VANTAGENS POTENCIAIS',{exact:true}).count()>0);
    }
    await page.screenshot({path:OUT+'/soja-'+label+'.png',fullPage:false});
    const width=await page.evaluate(()=>({body:document.documentElement.scrollWidth,viewport:document.documentElement.clientWidth}));
    checks.checks.push({name:label+' largura',ok:true,...width,overflow:width.body-width.viewport});
  } catch(e){
    record(label+' carregamento',false,{error:String(e).slice(0,1200),runtimeErrors});
    try{await page.screenshot({path:OUT+'/soja-'+label+'-error.png',fullPage:false});}catch{}
  }finally{await page.close();}
}
async function checkBovinos(browser) {
  const page=await browser.newPage();
  try {
    const res=await page.goto(BASE+'bovinos.html',{waitUntil:'domcontentloaded',timeout:35000});
    record('Bovinos HTTP',!!res && res.status()===200,{http:res?.status()});
    record('Bovinos conteúdo', (await page.locator('body').innerText()).length>500);
    await page.screenshot({path:OUT+'/bovinos-desktop.png',fullPage:false});
  }catch(e){record('Bovinos página',false,{error:String(e).slice(0,300)});}
  finally{await page.close();}
}
(async()=>{
  try{
    await checkPublishedHTML();
    const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    try{
      await checkBrowser(browser,'desktop',{width:1365,height:950});
      await checkBrowser(browser,'mobile',{width:390,height:844});
      await checkBovinos(browser);
    }finally{await browser.close();}
  }catch(e){record('Falha geral',false,{error:String(e).slice(0,1000)});}
  fs.writeFileSync(OUT+'/resultado.json',JSON.stringify(checks,null,2)+'\n');
  if(checks.errors.length)process.exitCode=1;
})();
