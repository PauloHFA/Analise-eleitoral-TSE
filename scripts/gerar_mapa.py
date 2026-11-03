import argparse
import json

from eleicoes.electoral_map import prepare_map
from eleicoes.map_report import load_map

parser = argparse.ArgumentParser()
parser.add_argument("--output",default="outputs/2026")
parser.add_argument("--data",default="data/geografia")
parser.add_argument("--offline",action="store_true")
args = parser.parse_args()
summary=prepare_map(args.output,args.data,args.offline)
load_map(args.output)
print(json.dumps(summary,ensure_ascii=False,indent=2))
