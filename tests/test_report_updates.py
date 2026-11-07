import hashlib
import json

import pytest

from eleicoes.report_updates import load_incremental_updates


def _write_report(folder, summary, *, unmatched=None):
    folder.mkdir(parents=True)
    (folder / "resumo.json").write_text(json.dumps(summary), encoding="utf-8")
    (folder / "relatorio.html").write_text("<h1>Relatório</h1>", encoding="utf-8")
    (folder / "relatorio.pdf").write_bytes(b"pdf")
    files = ("resumo.json", "relatorio.html", "relatorio.pdf")
    if unmatched is not None:
        (folder / "sem_correspondencia.csv").write_text(
            "candidate\n" + "".join(f"{candidate}\n" for candidate in unmatched),
            encoding="utf-8")
        files += ("sem_correspondencia.csv",)
    manifest = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in files
    }
    (folder / "manifesto.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_incremental_reports_are_loaded_and_category_gaps_counted(tmp_path):
    root = tmp_path / "outputs"
    _write_report(root / "auditoria" / "cruzamento_integrado", {
        "status": "concluído",
        "candidate_rows_without_national_match": 3,
    }, unmatched=[95, 95, 96])
    _write_report(root / "auditoria" / "atas_ampliacao", {
        "status": "concluído",
        "section_turns": 2,
        "units_with_individual_search": 2,
    })

    updates = load_incremental_updates(root)

    assert updates["unmatched_categories"] == {"95": 2, "96": 1}
    assert updates["crosswalk_html"].endswith("cruzamento_integrado/relatorio.html")
    assert updates["ata_search"]["units_with_individual_search"] == 2


def test_stale_incremental_manifest_fails_explicitly(tmp_path):
    root = tmp_path / "outputs"
    folder = root / "auditoria" / "cruzamento_integrado"
    _write_report(folder, {
        "status": "concluído",
        "candidate_rows_without_national_match": 1,
    }, unmatched=[95])
    (folder / "resumo.json").write_text('{"candidate_rows_without_national_match": 2}', encoding="utf-8")

    with pytest.raises(ValueError, match="desatualizado"):
        load_incremental_updates(root)


def test_no_incremental_reports_is_supported(tmp_path):
    assert load_incremental_updates(tmp_path) is None


def test_missing_summary_with_report_artifacts_fails_explicitly(tmp_path):
    root = tmp_path / "outputs"
    folder = root / "auditoria" / "cruzamento_integrado"
    _write_report(folder, {
        "status": "concluído",
        "candidate_rows_without_national_match": 1,
    }, unmatched=[95])
    (folder / "resumo.json").unlink()

    with pytest.raises(FileNotFoundError, match="Resumo do relatório incremental ausente"):
        load_incremental_updates(root)
