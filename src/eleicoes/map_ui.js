(()=>{
 const data=JSON.parse(document.getElementById('map-data').textContent), rows=data.features;
 const svg=document.getElementById('map-svg'), panel=document.getElementById('map-info');
 const turn=document.getElementById('map-turn'), mode=document.getElementById('map-mode'), uf=document.getElementById('map-uf');
 const flips=document.getElementById('map-flips'), zeros=document.getElementById('map-zeros');
 const paths=Array.from(svg.querySelectorAll('path[data-code]')), circles=Array.from(svg.querySelectorAll('circle[data-code]'));
 const lookup=new Map(rows.map(r=>[r.ibge_code,r])); let current=null,view=[],drag=null,moved=false;
 function tint(base,strength){return '#'+[1,3,5].map(i=>Math.round(255+(parseInt(base.slice(i,i+2),16)-255)*strength).toString(16).padStart(2,'0')).join('')}
 function color(r,t,m,max){const f=r['votes_22_'+t],l=r['votes_13_'+t];if(f===null||l===null||f+l<=0)return '#c5cbd3';
  if(m==='winner')return f===l?'#c5cbd3':tint(f>l?'#165dcc':'#cf2639',.32+.68*Math.abs(f-l)/(f+l));
  const value=m==='22'?f:l;return tint(m==='22'?'#165dcc':'#cf2639',value<=0?0:.12+.88*Math.sqrt(value/max));}
 function bounds(rs){const xs=rs.flatMap(r=>[r.bounds[0],r.bounds[0]+r.bounds[2]]),ys=rs.flatMap(r=>[r.bounds[1],r.bounds[1]+r.bounds[3]]);
  const x=Math.min(...xs),y=Math.min(...ys),w=Math.max(...xs)-x,h=Math.max(...ys)-y,p=Math.max(w,h)*.04;return [x-p,y-p,w+2*p,h+2*p]}
 function setView(v){view=v;svg.setAttribute('viewBox',v.join(' '));circles.forEach(p=>p.setAttribute('r',v[2]*.004))}
 function reset(){const rs=rows.filter(r=>uf.value==='BR'||r.uf===uf.value);setView(bounds(rs.length?rs:rows))}
 function info(r){panel.replaceChildren();if(!r){panel.textContent='Clique em um município para consultar os votos dos dois turnos e os casos investigados.';return}
  const heading=document.createElement('h3');heading.textContent=r.municipality_name_1+' — '+r.uf;panel.append(heading);
  for(const t of [1,2]){const p=document.createElement('p'),f=r['votes_22_'+t],l=r['votes_13_'+t],valid=r['valid_'+t];
   const percent=v=>valid>0?(100*v/valid).toFixed(2).replace('.',',')+'%':'—';
   p.textContent=t+'º turno: Flávio '+Number(f).toLocaleString('pt-BR')+' ('+percent(f)+'); Lula '+Number(l).toLocaleString('pt-BR')+' ('+percent(l)+').';panel.append(p)}
  const note=document.createElement('p');note.textContent=(r.flipped?'O vencedor mudou entre turnos. ':'')+'Comparação territorial: '+(r.comparable?'compatível':r.comparison_reason)+'.';panel.append(note);
  if(r.zero_sections){const p=document.createElement('p');p.textContent=r.zero_sections+' seção(ões) com passagem de votos positivos para zero. O marcador identifica o município, não o endereço da seção.';panel.append(p)}
  if(r.case_file){const a=document.createElement('a');a.href=r.case_file;a.textContent='Abrir ficha da virada municipal';panel.append(a)}
 }
 function render(){const t=turn.value,m=mode.value,max=m==='winner'?1:Math.max(1,...rows.map(r=>r['votes_'+m+'_'+t]||0));let visible=0;
  paths.forEach(p=>{const r=lookup.get(p.getAttribute('data-code')),show=(uf.value==='BR'||r.uf===uf.value)&&(!flips.checked||r.flipped);p.style.display=show?'':'none';if(show)visible++;
   p.setAttribute('fill',color(r,t,m,max));p.setAttribute('stroke',r.flipped?'#e5a000':'#ffffff');p.setAttribute('stroke-width',r.flipped?'1.4':'.35');
   p.querySelector('title').textContent=r.municipality_name_1+' / '+r.uf+' — '+t+'º turno: Flávio '+r['votes_22_'+t]+', Lula '+r['votes_13_'+t];});
  circles.forEach(p=>{const r=lookup.get(p.getAttribute('data-code'));p.style.display=zeros.checked&&(uf.value==='BR'||uf.value===r.uf)&&(!flips.checked||r.flipped)?'':'none'});
  document.getElementById('map-count').textContent=visible+' municípios exibidos. Contorno dourado: vencedor mudou entre os turnos.';
  document.getElementById('map-scale').textContent=m==='winner'?'Tom mais forte = maior margem entre os finalistas.':'Tom mais forte = mais votos para o candidato selecionado. Escala nacional por turno.';info(current)}
 turn.addEventListener('change',render);mode.addEventListener('change',render);flips.addEventListener('change',render);zeros.addEventListener('change',render);
 uf.addEventListener('change',()=>{reset();render()});
 for(const s of ['BR','RJ','MG'])document.getElementById('map-go-'+s).addEventListener('click',()=>{uf.value=s;reset();render()});
 document.getElementById('map-zoom-in').addEventListener('click',()=>setView([view[0]+view[2]*.15,view[1]+view[3]*.15,view[2]*.7,view[3]*.7]));
 document.getElementById('map-zoom-out').addEventListener('click',()=>setView([view[0]-view[2]*.2,view[1]-view[3]*.2,view[2]*1.4,view[3]*1.4]));
 document.getElementById('map-reset').addEventListener('click',reset);
 svg.addEventListener('click',e=>{if(moved)return;const shape=e.target.closest('[data-code]');if(shape){current=lookup.get(shape.getAttribute('data-code'));info(current)}});
 function point(e){const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse())}
 svg.addEventListener('wheel',e=>{e.preventDefault();const p=point(e),factor=e.deltaY<0?.85:1.18;setView([p.x+(view[0]-p.x)*factor,p.y+(view[1]-p.y)*factor,view[2]*factor,view[3]*factor])},{passive:false});
 svg.addEventListener('pointerdown',e=>{if(e.button!==0)return;moved=false;drag={x:e.clientX,y:e.clientY,v:[...view]};svg.setPointerCapture(e.pointerId)});
 svg.addEventListener('pointermove',e=>{if(!drag)return;const rect=svg.getBoundingClientRect(),scale=Math.max(view[2]/rect.width,view[3]/rect.height);if(Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>4)moved=true;setView([drag.v[0]-(e.clientX-drag.x)*scale,drag.v[1]-(e.clientY-drag.y)*scale,drag.v[2],drag.v[3]])});
 svg.addEventListener('pointerup',()=>{drag=null});svg.addEventListener('pointercancel',()=>{drag=null});reset();render();
})();
