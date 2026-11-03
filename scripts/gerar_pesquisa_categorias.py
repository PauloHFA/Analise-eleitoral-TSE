"""Gera relatórios da pesquisa revisada, sem consultas automáticas à rede."""
import argparse
import json
from eleicoes.research import run_research

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='outputs/2026')
    parser.add_argument('--evidencias',default='docs/pesquisa_categorias_2026.json')
    parser.add_argument('--candidatura',default='docs/candidatura28_evidencia.json')
    parser.add_argument('--dest')
    args=parser.parse_args()
    print(json.dumps(run_research(args.output,args.evidencias,args.candidatura,args.dest),ensure_ascii=False,indent=2))
