(()=>{
 const data=JSON.parse(document.getElementById('national-data').textContent),rows=data.features;
 const nodes=Object.fromEntries(['svg','info','uf','mode','turn','pattern','minimum','coverage','count','scale'].map(k=>[k,document.getElementById('national-'+k)]));
 const shapes=[...nodes.svg.querySelectorAll('path[data-code]')],lookup=new Map(rows.map(r=>[r.ibge_code,r]));let view=[],current=null,drag=null,moved=false;
 const finite=v=>v!==null&&Number.isFinite(v),num=v=>finite(v)?v.toLocaleString('pt-BR',{maximumFractionDigits:2}):'indisponível';
 function tint(base,strength){return '#'+[1,3,5].map(i=>Math.round(255+(parseInt(base.slice(i,i+2),16)-255)*strength).toString(16).padStart(2,'0')).join('')}
 function status(r){if(!finite(r.eligible_sections)||r.eligible_sections<=0)return 'sem denominador elegível';if(r.eligible_sections<Number(nodes.minimum.value))return 'quantidade de elegíveis abaixo do limite';if(!finite(r.eligible_coverage_pct)||r.eligible_coverage_pct<Number(nodes.coverage.value))return 'cobertura elegível abaixo do limite ou desconhecida';return 'apresentável pelos limites escolhidos'}
 function color(r){const m=nodes.mode.value,t=nodes.turn.value;
  if(m==='rate'){if(status(r)!=='apresentável pelos limites escolhidos'||!finite(r.rate_per_1000))return '#c5cbd3';return tint('#6d28a8',Math.sqrt(r.rate_per_1000/1000))}
  if(m==='margin'){if(!finite(r.margin_change_pp))return '#c5cbd3';if(r.margin_change_pp===0)return '#ffffff';return tint(r.margin_change_pp>0?'#165dcc':'#cf2639',.18+.82*Math.sqrt(Math.abs(r.margin_change_pp)/200))}
  const f=r['votes_22_'+t],l=r['votes_13_'+t];if(!finite(f)||!finite(l)||f+l<=0||f===l)return '#c5cbd3';return tint(f>l?'#165dcc':'#cf2639',.32+.68*Math.abs(f-l)/(f+l));
 }
 function matches(r){const p=nodes.pattern.value;return (nodes.uf.value==='BR'||r.uf===nodes.uf.value)&&
  (p==='all'||(p==='flips'&&(r.flip_to_13||r.flip_to_22))||(p==='13'&&r.flip_to_13)||(p==='22'&&r.flip_to_22)||
  (p==='loss22'&&r.loss_22_10pp)||(p==='loss13'&&r.loss_13_10pp)||(p==='ties'&&(r.tie_1!==r.tie_2)));}
 function info(r){nodes.info.replaceChildren();if(!r){nodes.info.textContent='Clique em um município para consultar os dois turnos, os denominadores e a coorte.';return}
  const h=document.createElement('h3');h.textContent=r.municipality_name_1+' / '+r.uf;nodes.info.append(h);
  function line(text){const p=document.createElement('p');p.textContent=text;nodes.info.append(p)}
  for(const t of [1,2])line(t+'º turno: Flávio '+num(r['votes_22_'+t])+', Lula '+num(r['votes_13_'+t])+'. Soma nominal '+num(r['valid_'+t])+'. Margem entre finalistas '+num(r['margin_'+t+'_pp'])+' pp. Comparecimento '+num(r['attendance_'+t])+' / aptos '+num(r['aptos_'+t])+'.');
  line('Mudança da margem: '+num(r.margin_change_pp)+' pp. Variação de votos absolutos: Flávio '+num(r.delta_votes_22)+', Lula '+num(r.delta_votes_13)+'. Eliminados no primeiro turno: '+num(r.eliminated_votes_1)+'.');
  line('Triagem original: '+num(r.reference_alert_sections)+' / '+num(r.eligible_sections)+' elegíveis = '+num(r.rate_per_1000)+' por 1.000. Cobertura elegível: '+num(r.eligible_coverage_pct)+'% de '+num(r.observed_sections)+' seções observadas. Exibição da taxa: '+status(r)+'.');
  line('Comparação territorial completa: '+(r.comparable?'composição e aptos compatíveis':r.comparison_reason)+'.');
  line('Coorte das mesmas '+num(r.cohort_sections)+' seções comparáveis, incluindo pequenas: margem '+num(r.cohort_margin_1_pp)+' → '+num(r.cohort_margin_2_pp)+' pp. Cobertura do comparecimento: '+num(r.cohort_coverage_attendance_1_pct)+'% / '+num(r.cohort_coverage_attendance_2_pct)+'%. A coorte não substitui o resultado completo.');
  line('Conferência BU disponível: '+num(r.document_records)+' linhas; '+num(r.document_pending)+' com apontamento. Essa contagem não certifica completude de urnas nem explica a escolha dos eleitores.');
  const a=document.createElement('a');a.href='../taxas/municipios.csv';a.textContent='Tabela municipal completa, com quantidades e coberturas';nodes.info.append(a);
 }
 function render(){let visible=0,masked=0;nodes.turn.disabled=nodes.mode.value!=='winner';
  const minimum=Number(nodes.minimum.value),coverage=Number(nodes.coverage.value);
  nodes.minimum.value=String(nodes.minimum.value!==''&&Number.isFinite(minimum)?Math.max(1,Math.floor(minimum)):data.minimum);
  nodes.coverage.value=String(nodes.coverage.value!==''&&Number.isFinite(coverage)?Math.max(0,Math.min(100,coverage)):data.coverage);
  for(const shape of shapes){const r=lookup.get(shape.getAttribute('data-code')),show=matches(r);shape.style.display=show?'':'none';if(show){visible++;if(nodes.mode.value==='rate'&&status(r)!=='apresentável pelos limites escolhidos')masked++;}
   shape.setAttribute('fill',color(r));shape.setAttribute('stroke',(r.flip_to_13||r.flip_to_22)?'#c28b00':'#ffffff');shape.setAttribute('stroke-width',(r.flip_to_13||r.flip_to_22)?'1.1':'.3');shape.querySelector('title').textContent=r.municipality_name_1+' / '+r.uf+' — Δmargem '+num(r.margin_change_pp)+' pp; taxa '+num(r.rate_per_1000)+' por 1.000; cobertura '+num(r.eligible_coverage_pct)+'%';}
  nodes.count.textContent=visible+' unidades municipais exibidas; '+masked+' com taxa sem cor pelos limites escolhidos. Contorno dourado: inversão de liderança entre finalistas.';
  nodes.scale.textContent=nodes.mode.value==='rate'?'Roxo: triagem original por 1.000 seções elegíveis; escala fixa 0–1.000. Branco = zero conhecido. Cinza = taxa sem exibição por denominador/cobertura. Não é risco de fraude.':nodes.mode.value==='margin'?'Azul: mudança relativa em favor de Flávio; vermelho: em favor de Lula. Escala simétrica fixa −200 a +200 pp; branco = mudança zero; cinza = margem indisponível. A cor não indica necessariamente quem lidera.':'Azul: liderança de Flávio; vermelho: liderança de Lula, entre os dois finalistas no turno escolhido. Tom indica tamanho da margem; cinza = empate ou ausência. Área não representa eleitores.';info(current);
 }
 function setView(v){view=v;nodes.svg.setAttribute('viewBox',v.join(' '))}
 function reset(){const selected=rows.filter(r=>nodes.uf.value==='BR'||r.uf===nodes.uf.value),xs=selected.flatMap(r=>[r.bounds[0],r.bounds[0]+r.bounds[2]]),ys=selected.flatMap(r=>[r.bounds[1],r.bounds[1]+r.bounds[3]]);const x=Math.min(...xs),y=Math.min(...ys),w=Math.max(...xs)-x,h=Math.max(...ys)-y,p=Math.max(w,h)*.04;setView([x-p,y-p,w+2*p,h+2*p])}
 for(const key of ['mode','turn','pattern','minimum','coverage'])nodes[key].addEventListener('change',render);
 nodes.uf.addEventListener('change',()=>{reset();render()});
 document.getElementById('national-reset').addEventListener('click',reset);
 document.getElementById('national-plus').addEventListener('click',()=>setView([view[0]+view[2]*.15,view[1]+view[3]*.15,view[2]*.7,view[3]*.7]));
 document.getElementById('national-minus').addEventListener('click',()=>setView([view[0]-view[2]*.2,view[1]-view[3]*.2,view[2]*1.4,view[3]*1.4]));
 function select(e){const shape=e.target.closest('[data-code]');if(shape){current=lookup.get(shape.getAttribute('data-code'));info(current)}}
 nodes.svg.addEventListener('click',e=>{if(!moved)select(e)});
 nodes.svg.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(e)}});
 nodes.svg.addEventListener('wheel',e=>{e.preventDefault();const point=nodes.svg.createSVGPoint();point.x=e.clientX;point.y=e.clientY;const pos=point.matrixTransform(nodes.svg.getScreenCTM().inverse()),f=e.deltaY<0?.85:1.18;setView([pos.x+(view[0]-pos.x)*f,pos.y+(view[1]-pos.y)*f,view[2]*f,view[3]*f])},{passive:false});
 nodes.svg.addEventListener('pointerdown',e=>{if(e.button!==0)return;moved=false;drag={x:e.clientX,y:e.clientY,v:[...view]};nodes.svg.setPointerCapture(e.pointerId)});
 nodes.svg.addEventListener('pointermove',e=>{if(!drag)return;const rect=nodes.svg.getBoundingClientRect(),scale=Math.max(view[2]/rect.width,view[3]/rect.height);if(Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>4)moved=true;setView([drag.v[0]-(e.clientX-drag.x)*scale,drag.v[1]-(e.clientY-drag.y)*scale,drag.v[2],drag.v[3]])});
 for(const event of ['pointerup','pointercancel'])nodes.svg.addEventListener(event,()=>{drag=null});reset();render();
})();
