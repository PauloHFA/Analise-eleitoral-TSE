const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{
 constructor(){this.value='';this.checked=false;this.children=[];this.attrs={};this.events={};this.style={};this.textContent='';this.title={textContent:''}}
 setAttribute(k,v){this.attrs[k]=String(v)}getAttribute(k){return this.attrs[k]}
 addEventListener(k,v){this.events[k]=v}append(v){this.children.push(v)}replaceChildren(...v){this.children=v}
 querySelector(){return this.title}closest(){return this}getBoundingClientRect(){return {width:650,height:650}}
}
const nodes=new Map(p.ids.map(id=>[id,new Element()])),get=k=>nodes.get('national-'+k);
const paths=p.codes.map(code=>{const el=new Element();el.setAttribute('data-code',code);return el});
get('svg').querySelectorAll=()=>paths;
get('data').textContent=JSON.stringify(p.data);
for(const [k,v] of Object.entries({uf:'BR',mode:'margin',turn:'2',pattern:'all',minimum:String(p.data.minimum),coverage:String(p.data.coverage)}))get(k).value=v;
const document={getElementById:id=>nodes.get(id)||null,createElement:()=>new Element()};
vm.runInNewContext(p.script,{document},{timeout:15000});let checks=0;
function change(key,value){get(key).value=value;get(key).events.change()}
for(const mode of ['margin','rate','winner']){
 change('mode',mode);
 for(const turn of ['1','2']){
  change('turn',turn);
  for(const el of paths)assert.equal(el.getAttribute('fill'),p.colors[mode][turn][el.getAttribute('data-code')]);
  checks+=paths.length;
 }
}
for(const uf of [...new Set(p.data.features.map(r=>r.uf)),'BR']){
 change('uf',uf);
 assert.equal(paths.filter(el=>el.style.display!=='none').length,p.data.features.filter(r=>uf==='BR'||r.uf===uf).length);checks++;
}
change('uf','BR');
for(const [pattern,predicate] of [['flips',r=>r.flip_to_13||r.flip_to_22],['13',r=>r.flip_to_13],['22',r=>r.flip_to_22],['loss22',r=>r.loss_22_10pp],['loss13',r=>r.loss_13_10pp],['ties',r=>r.tie_1!==r.tie_2]]){
 change('pattern',pattern);assert.equal(paths.filter(el=>el.style.display!=='none').length,p.data.features.filter(predicate).length);checks++;
}
change('pattern','all');change('mode','rate');
change('minimum','0');assert.equal(get('minimum').value,'1');change('coverage','101');assert.equal(get('coverage').value,'100');
change('minimum','');assert.equal(get('minimum').value,String(p.data.minimum));change('coverage','');assert.equal(get('coverage').value,String(p.data.coverage));checks+=4;
const unknown=p.data.features.find(r=>r.rate_per_1000===null);
if(unknown){const shape=paths.find(el=>el.getAttribute('data-code')===unknown.ibge_code);get('svg').events.click({target:shape});assert.ok(get('info').children.some(el=>el.textContent.includes('= indisponível por 1.000')));checks++}
get('svg').events.keydown({key:'Enter',preventDefault(){},target:paths[0]});assert.ok(get('info').children.length>=7);checks++;
get('plus').events.click();get('minus').events.click();get('reset').events.click();assert.ok(get('svg').getAttribute('viewBox').split(' ').map(Number).every(Number.isFinite));checks++;
console.log(JSON.stringify({status:'cores, turnos, todas as UFs, padrões, máscaras, valores ausentes e teclado válidos',checks,municipalities:paths.length}));
