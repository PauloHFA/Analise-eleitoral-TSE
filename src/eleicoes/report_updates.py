"""Leitura validada dos relatórios incrementais incluídos na edição principal."""
import csv
import json
from collections import Counter
from pathlib import Path

from .sources import sha256


def _read_report(folder):
    summary_path = folder / "resumo.json"
    if not summary_path.exists():
        if any((folder / name).exists() for name in ("manifesto.json", "relatorio.html", "relatorio.pdf")):
            raise FileNotFoundError(f"Resumo do relatório incremental ausente: {summary_path}")
        return None

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest_path = folder / "manifesto.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name in ("resumo.json", "relatorio.html", "relatorio.pdf"):
            path = folder / name
            expected = manifest.get(name)
            if expected and (not path.is_file() or sha256(path) != expected):
                raise ValueError(f"Relatório incremental desatualizado: {path}")
    return summary


def load_incremental_updates(output):
    """Lê resumos posteriores e confirma que suas saídas declaradas não mudaram."""
    output = Path(output)
    crosswalk_dir = output / "auditoria" / "cruzamento_integrado"
    crosswalk = _read_report(crosswalk_dir)
    ata_search = _read_report(output / "auditoria" / "atas_ampliacao")

    unmatched_categories = Counter()
    if crosswalk is not None:
        if crosswalk.get("status") != "concluído":
            raise ValueError(f"O cruzamento integrado não está concluído: {crosswalk_dir}")
        unmatched_path = crosswalk_dir / "sem_correspondencia.csv"
        manifest_path = crosswalk_dir / "manifesto.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected = manifest.get("sem_correspondencia.csv")
            if expected and (not unmatched_path.is_file() or sha256(unmatched_path) != expected):
                raise ValueError(f"Lacunas do cruzamento integradas desatualizadas: {unmatched_path}")
        with unmatched_path.open(encoding="utf-8-sig", newline="") as source:
            unmatched_categories.update(row["candidate"] for row in csv.DictReader(source))
        total = crosswalk["candidate_rows_without_national_match"]
        if (sum(unmatched_categories.values()) != total
                or set(unmatched_categories) - {"95", "96"}):
            raise ValueError("O resumo do cruzamento não corresponde às chaves sem linha nacional.")

    if ata_search is not None and ata_search.get("status") != "concluído":
        raise ValueError("A pesquisa documental ampliada não está concluída.")

    if crosswalk is None and ata_search is None:
        return None

    return {
        "crosswalk": crosswalk,
        "unmatched_categories": dict(unmatched_categories),
        "crosswalk_html": "auditoria/cruzamento_integrado/relatorio.html",
        "crosswalk_pdf": "auditoria/cruzamento_integrado/relatorio.pdf",
        "ata_search": ata_search,
        "ata_html": "auditoria/atas_ampliacao/relatorio.html",
        "ata_pdf": "auditoria/atas_ampliacao/relatorio.pdf",
    }
