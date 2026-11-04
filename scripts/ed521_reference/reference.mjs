import { edwards, eddsa } from '@noble/curves/abstract/edwards.js';
import { Field } from '@noble/curves/abstract/modular.js';
import { shake256 } from '@noble/hashes/sha3.js';
import { concatBytes } from '@noble/hashes/utils.js';
import fs from 'node:fs';
const p=(1n<<521n)-1n;
const n=BigInt('1716199415032652428745475199770348304317358825035826352348615864796385795849413675475876651663657849636693659065234142604319282948702542317993421293670108523');
const Gx=BigInt('1571054894184995387535939749894317568645297350402905821437625181152304994381188529632591196067604100772673927915114267193389905003276673749012051148356041324');
const Point=edwards({p,n,h:4n,a:1n,d:p-376014n,Gx,Gy:12n},{Fp:Field(p,{BITS:528,isLE:true}),Fn:Field(n,{BITS:528,isLE:true})});
const hash=Object.assign(b=>shake256(b,{dkLen:132}),{outputLen:132});
const domain=(data,ctx,ph)=>{if(ph||ctx.length>255)throw new Error('perfil não suportado');return concatBytes(new TextEncoder().encode('SigEd521'),Uint8Array.of(0,ctx.length),ctx,data)};
const sigs=eddsa(Point,hash,{adjustScalarBytes:b=>{b[0]&=252;b[65]=1;return b},domain,zip215:false});
const hex=b=>Buffer.from(b).toString('hex');
if(process.argv[2]==='generate'){
 const vectors=[];
 for(let i=0;i<12;i++){
  const seed=Uint8Array.from({length:66},(_,j)=>(i*17+j*3)&255);
  const message=i===0?new Uint8Array():Uint8Array.from({length:[1,64,132,255,1024][i%5]},(_,j)=>(i+j*7)&255);
  const context=i%3===0?new Uint8Array():new TextEncoder().encode('teste-'+i);
  const key=sigs.getPublicKey(seed),sig=sigs.sign(message,seed,{context});
  if(!sigs.verify(sig,message,key,{context,zip215:false}))throw new Error('Autoverificação Noble falhou');
  vectors.push({id:'noble-'+i,public_key:hex(key),message:hex(message),context:hex(context),signature:hex(sig)});
 }
 console.log(JSON.stringify({profile:'ICP-Brasil DOC-ICP-01.01 v4.2 Ed521 puro; phflag=0',generator:'@noble/curves 2.4.0 + @noble/hashes 2.4.0, generic Edwards/EdDSA wrapper',authority:'Vetores gerados pelo projeto com referência independente; não são vetores oficiais publicados',vectors},null,2));
}else if(process.argv[2]==='verify'){
 const cases=JSON.parse(fs.readFileSync(0,'utf8'));
 console.log(JSON.stringify(cases.map(c=>{try{return sigs.verify(Buffer.from(c.signature,'hex'),Buffer.from(c.message,'hex'),Buffer.from(c.public_key,'hex'),{context:Buffer.from(c.context||'','hex'),zip215:false})}catch{return false}})));
}
