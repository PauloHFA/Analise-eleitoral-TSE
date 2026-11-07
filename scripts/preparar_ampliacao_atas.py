import argparse
from eleicoes.atas_expansion import prepare_expansion

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--capturas',default='.firecrawl/atas-ampliacao-v1');p.add_argument('--data',default='data');a=p.parse_args()
    prepare_expansion(a.output,a.capturas,a.data)
