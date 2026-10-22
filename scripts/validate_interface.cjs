// Verificacao estática: erro JSX interrompe a publicacao.
const fs=require('fs');
const parser=require('@babel/parser');
const html=fs.readFileSync('index.html','utf8');
const m=html.match(/<script\s+type="text\/babel"[^>]*>([\s\S]*?)<\/script>/i);
if(!m)throw new Error('Script React/Babel do painel não encontrado');
parser.parse(m[1],{sourceType:'script',plugins:['jsx']});
const required=['id="operacional"','id="mercado-dados"','id="auditoria-fontes"','function AtualizacaoBloco()','function MetodoGrafico('];
for(const key of required)if(!html.includes(key))throw Error('UI ausente: '+key);
const all=[...m[1].matchAll(/\{\/\*\s*(\d{2})\s*[—-]/g)].map(x=>Number(x[1]));
for(let n=1;n<=17;n++)if(all.filter(x=>x===n).length!==1)throw Error('Módulo '+n+' ausente/duplicado');
for(const file of ['assets/bovinos.js','assets/market-status.js'])parser.parse(fs.readFileSync(file,'utf8'),{sourceType:'script'});
console.log('JSX válido; módulos 01–17 presentes e únicos; abas e JS auxiliares válidos.');
