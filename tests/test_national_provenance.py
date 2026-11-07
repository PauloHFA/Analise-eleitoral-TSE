import json

import pytest

from eleicoes.national_provenance import PHASES, refresh_report_provenance
from eleicoes.sources import sha256, write_json


def _setup_output(root, *, changed_analytic_input=False):
    root.mkdir()
    (root / "relatorio.html").write_text("<h1>Atualizado</h1>", encoding="utf-8")
    (root / "relatorio.pdf").write_bytes(b"pdf atualizado")
    (root / "sintese_analise.json").write_text('{"metric": 10}', encoding="utf-8")

    for phase in PHASES:
        folder = root / "nacional" / phase
        folder.mkdir(parents=True)
        payload = folder / "dados.csv"
        payload.write_text(f"phase,{phase}\n", encoding="utf-8")
        summary_inputs = {
            "relatorio.html": "old-html-hash",
            "relatorio.pdf": "old-pdf-hash",
            "sintese_analise.json": "old-synthesis-hash",
        }
        if changed_analytic_input:
            summary_inputs["indicadores.parquet"] = "old-analytic-hash"
            (root / "indicadores.parquet").write_bytes(b"changed")
        else:
            summary_inputs["sintese_analise.json"] = sha256(root / "sintese_analise.json")
        if phase == "taxas":
            summary_inputs["nacional/inventario/resumo.json"] = sha256(
                root / "nacional" / "inventario" / "resumo.json")
        if phase == "mapas":
            summary_inputs["nacional/taxas/resumo.json"] = sha256(
                root / "nacional" / "taxas" / "resumo.json")
        summary = {
            "status": "concluído",
            "input_hashes": summary_inputs,
            "results": [1, 2, 3],
        }
        write_json(folder / "resumo.json", summary)
        write_json(folder / "estado_execucao.json", {
            "status": "concluído",
            "input_hashes": summary_inputs,
        })
        write_json(folder / "manifesto.json", {"dados.csv": sha256(payload)})


def test_refresh_updates_only_report_hashes_and_preserves_old_hashes(tmp_path):
    root = tmp_path / "outputs"
    _setup_output(root)

    result = refresh_report_provenance(root)

    assert result["phases_updated"] == list(PHASES)
    assert result["recalculated"] is False
    for phase in PHASES:
        folder = root / "nacional" / phase
        summary = json.loads((folder / "resumo.json").read_text(encoding="utf-8"))
        state = json.loads((folder / "estado_execucao.json").read_text(encoding="utf-8"))
        manifest = json.loads((folder / "manifesto.json").read_text(encoding="utf-8"))
        provenance = summary["provenance_refresh"]
        assert summary["results"] == [1, 2, 3]
        assert provenance["recalculated"] is False
        assert provenance["previous_report_hashes"] == {
            "relatorio.html": "old-html-hash",
            "relatorio.pdf": "old-pdf-hash",
        }
        assert summary["input_hashes"] == state["input_hashes"]
        assert summary["input_hashes"]["relatorio.html"] == sha256(root / "relatorio.html")
        assert summary["input_hashes"]["relatorio.pdf"] == sha256(root / "relatorio.pdf")
        assert manifest["resumo.json"] == sha256(folder / "resumo.json")
        assert manifest["dados.csv"] == sha256(folder / "dados.csv")
    taxas = json.loads((root / "nacional" / "taxas" / "resumo.json").read_text(encoding="utf-8"))
    assert taxas["input_hashes"]["nacional/inventario/resumo.json"] == sha256(
        root / "nacional" / "inventario" / "resumo.json")
    assert taxas["provenance_refresh"]["previous_upstream_summary_hashes"][
        "nacional/inventario/resumo.json"] != taxas["input_hashes"]["nacional/inventario/resumo.json"]
    mapas = json.loads((root / "nacional" / "mapas" / "resumo.json").read_text(encoding="utf-8"))
    assert mapas["input_hashes"]["nacional/taxas/resumo.json"] == sha256(
        root / "nacional" / "taxas" / "resumo.json")


def test_refresh_refuses_changed_analytical_inputs_without_partial_writes(tmp_path):
    root = tmp_path / "outputs"
    _setup_output(root, changed_analytic_input=True)
    before = {
        phase: (root / "nacional" / phase / "resumo.json").read_bytes()
        for phase in PHASES
    }

    with pytest.raises(ValueError, match="Entrada analítica mudou"):
        refresh_report_provenance(root)

    after = {
        phase: (root / "nacional" / phase / "resumo.json").read_bytes()
        for phase in PHASES
    }
    assert after == before


def test_refresh_is_idempotent(tmp_path):
    root = tmp_path / "outputs"
    _setup_output(root)
    refresh_report_provenance(root)

    result = refresh_report_provenance(root)

    assert result["status"] == "já atualizado"
    assert result["phases_updated"] == []
