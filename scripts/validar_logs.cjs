const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2]||'outputs/2026/auditoria/logs/relatorio.html','utf8');
const rows=[...html.matchAll(/<tr class="unit" data-uf="([^"]+)" data-group="([^"]+)" data-review="([^"]+)">/g)].map(m=>({dataset:{uf:m[1],group:m[2],review:m[3]},hidden:false}));
const controls=Object.fromEntries(['uf','group','review'].map(id=>[id,{id,value:'all',addEventListener(_,fn){this.change=fn}}]));
const count={textContent:''};
const document={querySelector(s){return s==='#count'?count:controls[s.slice(1)]},querySelectorAll(s){assert.equal(s,'.unit');return rows}};
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];assert.equal(scripts.length,1);
vm.runInNewContext(scripts[0][1],{document});
let checks=0;
for(const uf of ['all',...new Set(rows.map(r=>r.dataset.uf))])for(const group of ['all','prioritario','comparacao'])for(const review of ['all','sim','nao']){
 for(const [id,value] of Object.entries({uf,group,review}))controls[id].value=value;
 controls.uf.change();
 let visible=0;
 for(const row of rows){const expected=Object.entries({uf,group,review}).every(([id,v])=>v==='all'||row.dataset[id]===v);assert.equal(!row.hidden,expected);visible+=expected;checks++}
 assert.equal(count.textContent,visible+' unidades exibidas');checks++;
}
console.log(JSON.stringify({units:rows.length,filter_conditions:checks,status:'válido'}));
