"""Saídas incrementais nacionais separadas e protegidas por hash."""
from datetime import datetime, timezone
import json
from pathlib import Path

from .sources import sha256,write_json


def begin(source,destination,names):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination==source or source.is_relative_to(destination):raise ValueError('Saída deve ser separada da referência')
    if destination.exists() and any(destination.iterdir()):raise FileExistsError('Saída preenchida; escolha outra pasta')
    inputs={name:sha256(source/name) for name in names}
    for name in ('relatorio.html','relatorio.pdf','sintese_analise.json','investigacao_resumo.json','mapa_dados.json'):
        if (source/name).exists():inputs[name]=sha256(source/name)
    destination.mkdir(parents=True,exist_ok=True)
    state=dict(status='em execução',started=datetime.now(timezone.utc).isoformat(),input_hashes=inputs)
    write_json(destination/'estado_execucao.json',state)
    return source,destination,state


def finish(source,destination,state,summary,code_files):
    for name,digest in state['input_hashes'].items():
        if sha256(source/name)!=digest:raise ValueError('Entrada alterada: '+name)
    summary.update(status='concluído',input_hashes=state['input_hashes'],preservation_verified=True,
                   code_hashes={Path(p).name:sha256(p) for p in code_files})
    write_json(destination/'resumo.json',summary)
    write_json(destination/'manifesto.json',{p.name:sha256(p) for p in sorted(destination.iterdir()) if p.is_file() and p.name not in ('manifesto.json','estado_execucao.json')})
    write_json(destination/'estado_execucao.json',dict(state,status='concluído',finished=datetime.now(timezone.utc).isoformat()))
    return summary


def failed(destination,state,exc):
    write_json(destination/'estado_execucao.json',dict(state,status='incompleto',error=f'{type(exc).__name__}: {exc}'))


def records(frame):return json.loads(frame.to_json(orient='records',force_ascii=False))
