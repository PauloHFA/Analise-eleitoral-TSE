const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{
 constructor(){this.value='';this.checked=false;this.children=[];this.attrs={};this.events={};this.style={};this.textContent='';this.title={textContent:''}}
 setAttribute(k,v){this.attrs[k]=String(v)}getAttribute(k){return this.attrs[k]}
 addEventListener(k,v){this.events[k]=v}append(v){this.children.push(v)}replaceChildren(...v){this.children=v}
 querySelector(){return this.title}closest(){return this}
}
const nodes=new Map(p.ids.map(id=>[id,new Element()]));
const paths=p.codes.map(code=>{const e=new Element();e.setAttribute('data-code',code);return e});
const circles=p.circles.map(code=>{const e=new Element();e.setAttribute('data-code',code);return e});
const svg=nodes.get('map-svg');svg.querySelectorAll=s=>s.startsWith('path')?paths:circles;
nodes.get('map-data').textContent=JSON.stringify(p.data);
nodes.get('map-turn').value='2';nodes.get('map-mode').value='winner';nodes.get('map-uf').value='BR';
const document={getElementById:k=>nodes.get(k)||null,createElement:()=>new Element()};
vm.runInNewContext(p.script,{document},{timeout:10000});
const index=new Map(p.data.features.map(r=>[r.ibge_code,r]));let checks=0;
for(const t of ['1','2']){
 nodes.get('map-turn').value=t;nodes.get('map-turn').events.change();
 paths.forEach(e=>assert.equal(e.getAttribute('fill'),p.colors[t][e.getAttribute('data-code')]));checks+=paths.length;
}
for(const uf of ['BR','RJ','MG']){
 nodes.get('map-go-'+uf).events.click();
 const count=paths.filter(e=>e.style.display!=='none').length;
 assert.equal(count,p.data.features.filter(r=>uf==='BR'||r.uf===uf).length);checks++;
}
nodes.get('map-go-BR').events.click();nodes.get('map-flips').checked=true;nodes.get('map-flips').events.change();
assert.equal(paths.filter(e=>e.style.display!=='none').length,p.data.features.filter(r=>r.flipped).length);checks++;
nodes.get('map-flips').checked=false;nodes.get('map-zeros').checked=true;nodes.get('map-zeros').events.change();
assert.equal(circles.filter(e=>e.style.display!=='none').length,p.circles.length);checks++;
for(const m of ['13','22']){nodes.get('map-mode').value=m;nodes.get('map-mode').events.change();assert.ok(paths.every(e=>/^#[0-9a-f]{6}$/.test(e.getAttribute('fill'))));checks++}
svg.events.click({target:paths[0]});assert.ok(nodes.get('map-info').children.length>=3);checks++;
nodes.get('map-zoom-in').events.click();nodes.get('map-zoom-out').events.click();nodes.get('map-reset').events.click();
assert.equal(svg.getAttribute('viewBox').split(' ').length,4);
console.log(JSON.stringify({status:'cores, turnos, filtros e consulta municipal válidos',checks,municipalities:paths.length}));
