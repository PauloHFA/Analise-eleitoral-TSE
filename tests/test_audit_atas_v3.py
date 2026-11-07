import pandas as pd
import sys
import types

from eleicoes.audit_atas_v3 import evaluate
from eleicoes.audit_atas_report_v3 import render
from eleicoes.cli import main


def identity():
    return dict(year=2026, turn=2, uf="BA", municipality="34193", zone="53", section="274")


def evidence(**changes):
    item = dict(
        evidence_id="E01",
        source_id="S01",
        case=identity(),
        indicator="nested_payloads",
        finding="corrobora_registro",
        locator="página 2, anotação identificada",
        justification="Fixture local sintética",
        review_status="revisao_documental_registrada",
    )
    item.update(changes)
    return item


def source(**changes):
    item = dict(
        source_id="S01",
        url="https://www.tre-ba.jus.br/documentos/ata.pdf",
        title="Documento sintético",
        kind="ata_mrv",
        identity=identity(),
        capture_sha256="a" * 64,
    )
    item.update(changes)
    return item


def test_v3_evaluation_keeps_official_responses_inconclusive():
    response = source(kind="resposta_oficial")
    assert evaluate(identity(), "nested_payloads", response, evidence()) == "evidencia_inconclusiva"
    assert evaluate(identity(), "nested_payloads", source(), evidence(finding="contradiz_registro")) \
        == "divergencia_documental_a_revisar"


def test_v3_report_renders_case_card_and_does_not_link_local_original(tmp_path):
    case = identity()
    case.update(
        case_id="2026-2-BA-34193-53-274",
        municipality_name_1="CAMPO FORMOSO",
        priority="inicial",
        issues=1,
        individual_searches=1,
        card="fichas/2026-2-BA-34193-53-274.html",
    )
    issue = dict(
        **identity(), indicator="nested_payloads", count=1,
        document_status="evidencia_insuficiente", evidence_ids="E01",
        cause_status="nao_confirmada_por_esta_rotina",
    )
    summary = dict(
        section_turns=1, issue_rows=1, registered_evidence_entries=1,
        individual_searches=1, specific_evidence_entries=0, official_response_entries=1,
    )
    official_response = source(kind="resposta_oficial")
    registered = evidence(finding="inconclusivo")

    render(
        tmp_path, summary, pd.DataFrame([case]), pd.DataFrame([issue]),
        pd.DataFrame([official_response]), pd.DataFrame(),
        [registered], {"S01": official_response},
    )

    report = (tmp_path / "relatorio.html").read_text(encoding="utf-8")
    card = (tmp_path / case["card"]).read_text(encoding="utf-8")
    assert "1 unidade seção/turno" in report
    assert "Escopo da consulta registrado; inconclusivo" in report
    assert "E01" in card and "não confirmada" in card
    assert str(tmp_path) not in report and "received.pdf" not in report
    assert (tmp_path / "relatorio.pdf").stat().st_size > 0


def test_cli_routes_documentary_confrontation_to_v3(monkeypatch, tmp_path):
    calls = []
    module = types.ModuleType("eleicoes.audit_atas_v3")
    module.run_atas_confronto = lambda *args: calls.append(args) or {
        "sections": 1, "section_turns": 1,
    }
    monkeypatch.setitem(sys.modules, "eleicoes.audit_atas_v3", module)
    monkeypatch.setattr(sys, "argv", [
        "eleicoes", "auditoria", "--etapa", "atas-confronto",
        "--output", str(tmp_path / "outputs"), "--data", str(tmp_path / "data"),
        "--dest", str(tmp_path / "result"),
    ])

    main()

    assert calls == [(
        str(tmp_path / "outputs"), str(tmp_path / "data"), str(tmp_path / "result"),
    )]
