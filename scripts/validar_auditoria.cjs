const fs=require('fs'),vm=require('vm'),assert=require('assert');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const nodes={uf:{id:'uf',value:'all',addEventListener(){}},group:{id:'group',value:'all',addEventListener(){}},count:{}};
const cases=p.cases.map(dataset=>({dataset,hidden:false}));
const document={querySelector:s=>nodes[s.slice(1)],querySelectorAll:s=>cases};
const context={document};vm.createContext(context);vm.runInContext(p.script,context);
let checks=0;
for(const uf of ['all',...new Set(p.cases.map(c=>c.uf))])for(const group of ['all','prioritario','comparacao']){
  nodes.uf.value=uf;nodes.group.value=group;vm.runInContext('filter()',context);
  let count=0;
  for(const c of cases){const expected=(uf==='all'||c.dataset.uf===uf)&&(group==='all'||c.dataset.group===group);assert.equal(c.hidden,!expected);count+=+expected;checks++}
  assert.equal(nodes.count.textContent,count+' seções exibidas');checks++;
}
process.stdout.write(JSON.stringify({checks,filters:'UF e grupo; todas as combinações'}));
