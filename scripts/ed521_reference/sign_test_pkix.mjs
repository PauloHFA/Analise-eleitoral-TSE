// Somente geração de material público sintético de teste. Nunca usado em produção.
import { edwards, eddsa } from '@noble/curves/abstract/edwards.js';
import { Field } from '@noble/curves/abstract/modular.js';
import { shake256 } from '@noble/hashes/sha3.js';
import { concatBytes } from '@noble/hashes/utils.js';
import fs from 'node:fs';
const p=(1n<<521n)-1n,n=BigInt('1716199415032652428745475199770348304317358825035826352348615864796385795849413675475876651663657849636693659065234142604319282948702542317993421293670108523');
const Gx=BigInt('1571054894184995387535939749894317568645297350402905821437625181152304994381188529632591196067604100772673927915114267193389905003276673749012051148356041324');
const Point=edwards({p,n,h:4n,a:1n,d:p-376014n,Gx,Gy:12n},{Fp:Field(p,{BITS:528,isLE:true}),Fn:Field(n,{BITS:528,isLE:true})});
const hash=Object.assign(b=>shake256(b,{dkLen:132}),{outputLen:132});
const domain=(data,ctx,ph)=>{if(ph||ctx.length)throw Error('somente puro sem contexto');return concatBytes(new TextEncoder().encode('SigEd521'),Uint8Array.of(0,0),data)};
const sigs=eddsa(Point,hash,{adjustScalarBytes:b=>{b[0]&=252;b[65]=1;return b},domain,zip215:false});
const seed=Uint8Array.from({length:66},(_,j)=>(j*3)&255); // Semente pública exclusivamente sintética.
const messages=JSON.parse(fs.readFileSync(0,'utf8'));
const signatures=messages.map(m=>Buffer.from(sigs.sign(Buffer.from(m,'hex'),seed)).toString('hex'));
process.stdout.write(JSON.stringify({public_key:Buffer.from(sigs.getPublicKey(seed)).toString('hex'),signatures}));
