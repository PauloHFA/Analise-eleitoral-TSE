"""Verificação pública Ed521 puro, conforme parâmetros DOC-ICP-01.01 v4.2.

Somente dados públicos. Não contém geração de chaves nem assinatura.
Política estrita: codificações canônicas, A não neutro e A/R no subgrupo primo.
"""
from functools import lru_cache
import hashlib

P=2**521-1
D=-376014 % P
L=1716199415032652428745475199770348304317358825035826352348615864796385795849413675475876651663657849636693659065234142604319282948702542317993421293670108523
GX=1571054894184995387535939749894317568645297350402905821437625181152304994381188529632591196067604100772673927915114267193389905003276673749012051148356041324
BASE=(GX,12,1,GX*12%P)
IDENTITY=(0,1,1,0)
PUBLIC_KEY_BYTES=66
SIGNATURE_BYTES=132


def add(left,right):
    # Fórmula unificada de Edwards estendida, a=1; cada produto é módulo p.
    x,y,z,t=left;u,v,w,q=right
    a=x*u%P;b=y*v%P;c=D*t*q%P;d=z*w%P
    e=((x+y)*(u+v)-a-b)%P;f=(d-c)%P;g=(d+c)%P;h=(b-a)%P
    return e*f%P,g*h%P,f*g%P,e*h%P


def multiply(scalar,point):
    # Não reduzir pelo módulo L: a checagem [L]Q exige o escalar inteiro.
    if scalar<0:raise ValueError('Escalar negativo')
    result=IDENTITY
    while scalar:
        if scalar&1:result=add(result,point)
        point=add(point,point);scalar>>=1
    return result


def equal(left,right):
    x,y,z,_=left;u,v,w,_=right
    return z!=0 and w!=0 and (x*w-u*z)%P==0 and (y*w-v*z)%P==0


@lru_cache(maxsize=256)
def decode_point(encoded):
    if len(encoded)!=66:raise ValueError('Ponto Ed521 deve ter 66 bytes')
    value=int.from_bytes(encoded,'little');sign=value>>527;y=value&((1<<527)-1)
    if y>=P:raise ValueError('Coordenada y não canônica')
    denominator=(1-D*y*y)%P
    if denominator==0:raise ValueError('Denominador nulo')
    square=(1-y*y)*pow(denominator,P-2,P)%P
    x=pow(square,(P+1)//4,P)
    if x*x%P!=square:raise ValueError('Ponto fora da curva')
    if x==0 and sign:raise ValueError('Bit de sinal não canônico')
    if x&1!=sign:x=P-x
    return x,y,1,x*y%P


@lru_cache(maxsize=256)
def public_point(encoded):
    point=decode_point(encoded)
    if equal(point,IDENTITY):raise ValueError('Chave neutra não aceita')
    if not equal(multiply(L,point),IDENTITY):raise ValueError('Chave fora do subgrupo primo')
    return point


def verify(public_key,message,signature,context=b''):
    """True só para a equação não cofatada com pontos no subgrupo primo."""
    if not all(isinstance(x,bytes) for x in (public_key,message,signature,context)):raise TypeError('Entradas devem ser bytes')
    if len(context)>255:raise ValueError('Contexto com mais de 255 bytes')
    if len(public_key)!=66 or len(signature)!=132:return False
    scalar=int.from_bytes(signature[66:],'little')
    if scalar>=L:return False
    try:
        a=public_point(public_key);r=decode_point(signature[:66])
        if not equal(multiply(L,r),IDENTITY):return False
    except ValueError:return False
    domain=b'SigEd521'+bytes((0,len(context)))+context
    challenge=int.from_bytes(hashlib.shake_256(domain+signature[:66]+public_key+message).digest(132),'little')%L
    return equal(multiply(scalar,BASE),add(r,multiply(challenge,a)))


def public_key_from_certificate(cert):
    """Extrai os bytes SPKI, exigindo o OID Ed521 e BIT STRING sem bits sobrantes."""
    from cryptography.hazmat.primitives import serialization
    if cert.public_key_algorithm_oid.dotted_string!='1.3.6.1.4.1.44588.2.1':raise ValueError('OID da chave não corresponde a Ed521')
    data=cert.public_bytes(serialization.Encoding.DER)
    def children(start,end):
        out=[]
        while start<end:
            tag=data[start];pos=start+1
            if pos>=end:raise ValueError('DER truncado')
            size=data[pos];pos+=1
            if size&128:
                count=size&127
                if not 1<=count<=4 or pos+count>end:raise ValueError('DER com comprimento inválido')
                size=int.from_bytes(data[pos:pos+count],'big');pos+=count
            limit=pos+size
            if limit>end:raise ValueError('DER truncado')
            out.append((tag,pos,limit));start=limit
        return out
    root=children(0,len(data))
    if len(root)!=1 or root[0][0]!=0x30:raise ValueError('Certificado sem sequência única')
    cert_parts=children(root[0][1],root[0][2]);tbs=children(cert_parts[0][1],cert_parts[0][2])
    if tbs[0][0]==0xa0:tbs=tbs[1:]
    if len(tbs)<6 or tbs[5][0]!=0x30:raise ValueError('SPKI não identificado')
    spki=children(tbs[5][1],tbs[5][2])
    if len(spki)!=2 or spki[1][0]!=0x03:raise ValueError('BIT STRING de chave ausente')
    bits=data[spki[1][1]:spki[1][2]]
    if len(bits)!=67 or bits[0]!=0:raise ValueError('Tamanho ou bits não usados da chave incompatíveis')
    public_point(bits[1:])
    return bits[1:]
