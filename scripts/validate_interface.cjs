// Verificacao estática: erro JSX interrompe a publicacao.
const fs=require('fs');
const parser=require('@babel/parser');
const html=fs.readFileSync('index.html','utf8');
const m=html.match(/^[ \t]*<script[ \t]+type="text\/babel"[^>]*>([\s\S]*?)<\/script>/im);
if(!m)throw new Error('Script React/Babel do painel não encontrado');
parser.parse(m[1],{sourceType:'script',plugins:['jsx']});
const required=['id="operacional"','id="mercado-dados"','id="auditoria-fontes"','function AtualizacaoBloco()','function MetodoGrafico('];
for(const key of required)if(!html.includes(key))throw Error('UI ausente: '+key);
const all=[...m[1].matchAll(/\{\/\*\s*(\d{2})\s*[—-]/g)].map(x=>Number(x[1]));
const expected=Array.from({length:17},(_,i)=>i+1);
if(JSON.stringify(all)!==JSON.stringify(expected))throw Error('Índices dos módulos estão fora de ordem: '+all.join(', '));
const anchors=[...m[1].matchAll(/<section id="modulo-(\d{2})"/g)].map(x=>Number(x[1]));
if(JSON.stringify(anchors)!==JSON.stringify(expected))throw Error('Âncoras dos módulos fora de ordem ou ausentes: '+anchors.join(', '));
const headers=[...m[1].matchAll(/<div[^>\n]*>(\d{2})\s*[—–-]/g)].map(x=>Number(x[1]));
if(JSON.stringify(headers)!==JSON.stringify(expected))throw Error('Títulos dos módulos inconsistentes: '+headers.join(', '));
const methods=[...m[1].matchAll(/<MetodoGrafico id=\{(\d+)\}/g)].map(x=>Number(x[1]));
if(!methods.every(n=>expected.includes(n)))throw Error('Metodologia aponta para índice inexistente');
for(let n=1;n<=17;n++)if(!html.includes('href="#modulo-'+String(n).padStart(2,'0')+'"'))throw Error('Índice navegável não contém módulo '+n);
// Checagens contra regressões detectadas na auditoria de 22/10/2026.
const graficos=[...m[1].matchAll(/<(?:LineChart|BarChart|ComposedChart|AreaChart|ScatterChart|PieChart)(?=[\s>])/g)].length;
const referencias=[...m[1].matchAll(/<FonteJuntoGrafico\s/g)].length;
if(graficos!==18)throw new Error('Inventário dos gráficos mudou; revisar documentação e fontes: '+graficos);
if(referencias<graficos)throw new Error('Há gráficos sem chamada de FonteJuntoGrafico: '+referencias+'/'+graficos);
if(html.includes('EXAME_ESTRATEGIAS[i].pro'))throw new Error('Blocos duplicados de estratégias não devem retornar');
for(const requiredText of [
 'EXPLICA_ESTRATEGIAS[i].p',
 'ANALISE_MATRIZ[c.key].pro',
 'FonteJuntoGrafico modulo={13} ordem={4}',
 'Futuro SJC da B3:',
 'Prêmios observados por vencimento',
 'premio_soja_paranagua'
])if(!html.includes(requiredText))throw new Error('Elemento da auditoria financeira ausente: '+requiredText);
for(const forbidden of ['Prêmio CALL venda (auto)','Nº contratos SFI','RISCO DOBRADO porque ficou vendido em put'])
 if(html.includes(forbidden))throw new Error('Texto tecnicamente inconsistente: '+forbidden);
for(const file of ['assets/bovinos.js','assets/market-status.js'])parser.parse(fs.readFileSync(file,'utf8'),{sourceType:'script'});
console.log('JSX válido; índices 01–17 sequenciais; links, metodologia e abas presentes; JavaScript válido.');
