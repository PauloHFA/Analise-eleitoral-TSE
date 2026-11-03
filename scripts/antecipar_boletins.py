"""Obtém BUs em pasta isolada enquanto as referências históricas são calculadas."""
import json
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from eleicoes.sources import download, resources, sha256, write_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
project = Path.cwd().resolve()
main = project / "data"
stage = project / "data_bu_prefetch"
stage.mkdir(exist_ok=True)
original = json.loads((main / "manifest.json").read_text(encoding="utf-8"))
cached = []
for item in original:
    if item.get("year") == 2026 and item.get("kind") == "bu":
        cached.append(dict(item, path=str((main / item["path"]).resolve())))
if not (stage / "manifest.json").exists():
    write_json(stage / "manifest.json", cached)
packs = json.loads((main / "catalog" / "2026-latest.json").read_text(encoding="utf-8"))
items = [x for x in resources(packs, 2026) if x["kind"] == "bu"]
with ThreadPoolExecutor(max_workers=4) as pool:
    jobs = [pool.submit(download, stage, item) for item in items]
    for i, job in enumerate(as_completed(jobs), 1):
        job.result()
        logging.info("Boletins obtidos: %d/%d", i, len(items))

state = json.loads((project / "outputs/2026/estado_execucao.json").read_text(encoding="utf-8"))
if state["status"] == "em execução" and 2022 in state["completed"]:
    logging.info("Arquivos prontos em %s; integração adiada porque o pipeline já chegou a 2026", stage)
else:
    records = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    merged = json.loads((main / "manifest.json").read_text(encoding="utf-8"))
    for item in records:
        src = (stage / item["path"]).resolve()
        dest = (main / "raw" / src.parent.name / src.name).resolve()
        if not src.is_relative_to(project) or not dest.is_relative_to(main):
            raise ValueError("Caminho de integração fora da área esperada")
        if sha256(src) != item["sha256"]:
            raise ValueError("Hash inválido antes de integrar BU")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.move(str(src), str(dest))
        elif sha256(dest) != item["sha256"]:
            raise ValueError("Versão conflitante na integração")
        record = dict(item, path=str(dest.relative_to(main)))
        if not any(m["url"] == record["url"] and m["sha256"] == record["sha256"] for m in merged):
            merged.append(record)
    write_json(main / "manifest.json", merged)
    logging.info("Todos os boletins integrados com hash validado")
