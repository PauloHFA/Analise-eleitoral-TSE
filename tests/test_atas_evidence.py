import json

import duckdb
import pandas as pd
import pytest

from eleicoes.atas_evidence import prepare_evidence_revision
from eleicoes.sources import sha256, write_json


def identity(**changes):
    row = dict(year=2026, turn=2, uf="BA", municipality="34193", zone="53", section="274")
    row.update(changes)
    return row


def document(path, **changes):
    row = dict(
        case=identity(),
        indicator="nested_payloads",
        document_kind="ata_mrv",
        source_url="https://www.tre-ba.jus.br/documentos/ata.pdf",
        title="Ata da mesa — fixture",
        document_path=str(path),
        locator="página 2, anotação identificada",
        justification="Revisão controlada exclusivamente para teste",
        finding="corrobora_registro",
        review_status="revisao_documental_registrada",
    )
    row.update(changes)
    return row


def fixture(tmp_path):
    output = tmp_path / "outputs"
    current = output / "auditoria" / "atas_ampliacao"
    current.mkdir(parents=True)
    data = tmp_path / "data"
    previous = data / "auditoria" / "atas" / "v2"
    previous.mkdir(parents=True)
    write_json(previous / "pesquisa.json", dict(version=1, sources=[], queries=[], results=[]))
    write_json(previous / "evidencias.json", dict(version=1, evidence=[]))
    (previous / "context.md").write_text("captura preservada", encoding="utf-8")
    raw_manifest = {p.name: sha256(p) for p in previous.iterdir() if p.is_file()}
    write_json(previous / "manifesto.json", raw_manifest)

    con = duckdb.connect()
    try:
        con.from_df(pd.DataFrame([identity()])).write_parquet(str(current / "casos.parquet"))
        issue = dict(**identity(), indicator="nested_payloads")
        con.from_df(pd.DataFrame([issue])).write_parquet(str(current / "confronto.parquet"))
    finally:
        con.close()
    summary = dict(status="concluído", preservation_verified=True,
                   capture_manifest_sha256=sha256(previous / "manifesto.json"),
                   capture_hashes=raw_manifest)
    write_json(current / "resumo.json", summary)
    write_json(current / "manifesto.json", {
        p.name: sha256(p) for p in current.iterdir() if p.is_file()
    })
    source_document = tmp_path / "received.pdf"
    source_document.write_bytes(b"%PDF-1.7\nsynthetic-only\n")
    record = tmp_path / "review.json"
    write_json(record, dict(documents=[document(source_document)]))
    return output, data, previous, current, source_document, record


def test_revision_preserves_original_and_records_reviewed_document(tmp_path):
    output, data, previous, current, original, record = fixture(tmp_path)
    original_digest = sha256(original)
    previous_digest = sha256(previous / "manifesto.json")

    result = prepare_evidence_revision(output, data, record)

    version = data / "auditoria" / "atas" / "v3"
    research = json.loads((version / "pesquisa.json").read_text(encoding="utf-8"))
    registry = json.loads((version / "evidencias.json").read_text(encoding="utf-8"))
    item = registry["evidence"][0]
    source = research["sources"][0]
    assert result["evidence_entries"] == 1
    assert sha256(version / source["capture_file"]) == original_digest
    assert source["specific_document"] and source["kind"] == "ata_mrv"
    assert item["source_id"] == source["source_id"]
    assert item["review_status"] == "revisao_documental_registrada"
    assert item["registered_at"].endswith("+00:00")
    assert research["evidence_revision"]["based_on_capture_manifest_sha256"] == previous_digest
    assert sha256(previous / "manifesto.json") == previous_digest
    assert sha256(original) == original_digest
    assert all(sha256(version / name) == digest
               for name, digest in json.loads((version / "manifesto.json").read_text()).items())


@pytest.mark.parametrize("changes", [
    {"case": identity(section="999")},
    {"indicator": "not_an_issue"},
    {"source_url": "https://tre-ba.jus.br.attacker.test/ata.pdf"},
    {"review_status": "pendente"},
    {"finding": "corrobora_registro", "document_kind": "resposta_oficial"},
    {"document_kind": "resposta_oficial", "finding": "inconclusivo"},
])
def test_invalid_or_inconclusive_document_records_are_not_promoted(tmp_path, changes):
    output, data, _, _, source_document, record = fixture(tmp_path)
    write_json(record, dict(documents=[document(source_document, **changes)]))
    if changes.get("document_kind") == "resposta_oficial" and changes.get("finding") == "inconclusivo":
        result = prepare_evidence_revision(output, data, record)
        assert result["evidence_entries"] == 1
        stored = json.loads((data / "auditoria" / "atas" / "v3" / "evidencias.json").read_text())
        assert stored["evidence"][0]["finding"] == "inconclusivo"
    else:
        with pytest.raises((ValueError, KeyError)):
            prepare_evidence_revision(output, data, record)
        assert not (data / "auditoria" / "atas" / "v3").exists()


def test_document_must_be_local_supported_and_nonempty(tmp_path):
    output, data, _, _, source_document, record = fixture(tmp_path)
    source_document.write_bytes(b"")
    with pytest.raises(ValueError, match="Tamanho"):
        prepare_evidence_revision(output, data, record)
    assert not (data / "auditoria" / "atas" / "v3").exists()


def test_current_output_and_previous_capture_hashes_are_required(tmp_path):
    output, data, previous, current, _, record = fixture(tmp_path)
    (current / "casos.parquet").write_bytes(b"modified")
    with pytest.raises(ValueError, match="alterado"):
        prepare_evidence_revision(output, data, record)

    output, data, previous, _, _, record = fixture(tmp_path / "other")
    (previous / "context.md").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="alterado"):
        prepare_evidence_revision(output, data, record)
