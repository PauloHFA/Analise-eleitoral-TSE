"""Confere conteúdo e geometria do PDF. Requer PyMuPDF para a inspeção visual."""
import argparse
import json
from pathlib import Path
import re
import sys

import duckdb

from eleicoes.sources import sha256
from eleicoes.synthesis import number


def validate(folder, *, render=None):
    try:
        import pymupdf
    except ImportError:
        cache = Path(__file__).resolve().parents[1] / "outputs/publicacao/pdfqa"
        if cache.exists():
            sys.path.insert(0,str(cache))
            import pymupdf
        else:
            raise SystemExit("Instale a ferramenta de inspeção: python -m pip install pymupdf")
    root = Path(folder)
    edition = json.loads((root / "pdf_edicao.json").read_text(encoding="utf-8"))
    synth = json.loads((root / "sintese_analise.json").read_text(encoding="utf-8"))
    assert sha256(root / "relatorio.pdf") == edition["pdf_sha256"]
    assert sha256(root / "sintese_analise.json") == edition["synthesis_sha256"]
    con = duckdb.connect()
    rows = con.execute("SELECT uf,municipality,zone,section,priority FROM read_parquet(?) WHERE statistical_alert ORDER BY priority LIMIT 100",[str(root / "indicadores_secoes.parquet")]).fetchall()
    con.close()
    with pymupdf.open(root / "relatorio.pdf") as doc:
        texts = [page.get_text() for page in doc]
        text = "\n".join(texts)
        assert len(doc) == edition["pages"]
        assert len(doc.get_toc()) == len(edition["sections"])
        assert doc[1].get_links(), "Sumário sem links internos"
        assert all(len(t.strip()) > 100 for t in texts), "Página sem conteúdo útil"
        for metric in synth["metrics"]:
            assert number(metric["value"]) in text, f"Contagem ausente: {metric['id']}"
        for uf,municipality,zone,section,priority in rows:
            assert f"fichas/{uf}-{municipality}-{zone}-{section}.json" in text
            assert len(re.findall(rf"Prioridade {int(priority)}\s*•",text)) == 1
        assert "secoes_observadas\"" not in text and "alertas_10pp\"" not in text
        assert "MAD" in text and "pontos percentuais" in text
        assert "Persistência: não investigada" in text
        image_count = 0
        for page in doc:
            assert len(re.findall(r"Prioridade \d+\s*•",page.get_text())) <= 2
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        x0,y0,x1,y1 = span["bbox"]
                        assert x0 >= 40 and x1 <= page.rect.width-40, f"Texto fora da margem horizontal: página {page.number+1}"
                        assert y0 >= 12 and y1 <= page.rect.height-12, f"Texto cortado: página {page.number+1}"
            for image in page.get_images(full=True):
                for rect in page.get_image_rects(image[0]):
                    assert abs(rect.width/rect.height - image[2]/image[3]) < .01, "Imagem distorcida"
                    image_count += 1
        assert image_count >= 6
        if render:
            target = Path(render)
            target.mkdir(parents=True,exist_ok=True)
            selected = {1,2,*edition["sections"].values(),edition["pages"]}
            for page in selected:
                doc[page-1].get_pixmap(matrix=pymupdf.Matrix(1.25,1.25)).save(target/f"pagina-{page:03}.png")
        result = dict(status="PDF revisado válido",pages=len(doc),bookmarks=len(doc.get_toc()),
            statistical_cases=len(rows),metrics=len(synth["metrics"]),images=image_count,
            geometry="texto dentro das margens; proporções das imagens preservadas",
            main_pages=edition["sections"]["anexo-zeros"]-1)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder",nargs="?",default="outputs/2026")
    parser.add_argument("--render",help="Pasta para renderizar as páginas de abertura dos capítulos")
    args = parser.parse_args()
    validate(args.folder,render=args.render)
