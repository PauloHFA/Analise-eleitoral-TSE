"""Gera o confronto v3 sem modificar a pesquisa ampliada v2."""
from pathlib import Path
import json

import duckdb
import pandas as pd

from .analysis import export_frame
from .audit_atas import GEO, SPECIFIC_TYPES, case_id, key, official_source, request_text
from .atas_evidence import RESPONSE_TYPES
from .national_common import begin, failed, finish, records
from .sources import sha256, write_json


def evaluate(case, indicator, source, evidence):
    if not official_source(source.get("url", "")):
        return "origem_nao_verificada"
    if source.get("kind") not in SPECIFIC_TYPES | RESPONSE_TYPES:
        return "fonte_geral_sem_confronto"
    try:
        identity = source.get("identity")
        if identity is None:
            identity = {name: source[name] for name in GEO if name in source and source[name] is not None}
        if key(identity) != key(case):
            return "documento_de_outra_unidade_ou_turno"
    except (KeyError, ValueError):
        return "identificacao_documental_insuficiente"
    if evidence.get("indicator") != indicator:
        return "apontamento_diferente"
    if (evidence.get("review_status") != "revisao_documental_registrada"
            or not str(evidence.get("locator", "")).strip()
            or not str(evidence.get("justification", "")).strip()):
        return "revisao_incompleta"
    if source.get("kind") in RESPONSE_TYPES:
        return "evidencia_inconclusiva"
    return {
        "corrobora_registro": "registro_corrobora_no_escopo",
        "contradiz_registro": "divergencia_documental_a_revisar",
        "inconclusivo": "evidencia_inconclusiva",
    }.get(evidence.get("finding"), "evidencia_inconclusiva")


def run_atas_confronto(source, data="data", destination=None):
    source, data = Path(source).resolve(), Path(data).resolve()
    raw = data / "auditoria" / "atas" / "v3"
    destination = Path(destination).resolve() if destination else source / "auditoria" / "atas_confronto"
    names = [
        "auditoria/logs/unidades.parquet",
        "auditoria/logs/pendencias.parquet",
        "auditoria/logs/manifesto.json",
        "auditoria/atas_ampliacao/resumo.json",
        "auditoria/atas_ampliacao/manifesto.json",
        "auditoria/atas_ampliacao/manifesto_fichas.json",
    ]
    source, destination, state = begin(source, destination, names)
    con = duckdb.connect()
    try:
        raw_manifest = json.loads((raw / "manifesto.json").read_text(encoding="utf-8"))
        for name, digest in raw_manifest.items():
            path = (raw / name).resolve()
            if not path.is_relative_to(raw) or sha256(path) != digest:
                raise ValueError(f"Captura ausente, fora da pasta ou alterada: {name}")
        log_manifest = json.loads((source / names[2]).read_text(encoding="utf-8"))
        for name, digest in log_manifest.items():
            if sha256(source / "auditoria" / "logs" / name) != digest:
                raise ValueError(f"Etapa dos logs alterada: {name}")
        expansion = source / "auditoria" / "atas_ampliacao"
        expansion_summary = json.loads((expansion / "resumo.json").read_text(encoding="utf-8"))
        if expansion_summary.get("status") != "concluído" or not expansion_summary.get(
                "preservation_verified"):
            raise ValueError("A pesquisa ampliada não está validada")
        for manifest_name in ("manifesto.json", "manifesto_fichas.json"):
            manifest = json.loads((expansion / manifest_name).read_text(encoding="utf-8"))
            for name, digest in manifest.items():
                path = (expansion / name).resolve()
                if not path.is_relative_to(expansion.resolve()) or sha256(path) != digest:
                    raise ValueError(f"Arquivo da pesquisa ampliada ausente ou alterado: {name}")
        research = json.loads((raw / "pesquisa.json").read_text(encoding="utf-8"))
        registry = json.loads((raw / "evidencias.json").read_text(encoding="utf-8"))
        if research.get("version") != 1 or registry.get("version") != 1:
            raise ValueError("Versão de registro não suportada")
        revision = research.get("evidence_revision")
        if not revision or revision.get("based_on_capture_manifest_sha256") != sha256(
                data / "auditoria" / "atas" / "v2" / "manifesto.json"):
            raise ValueError("Revisão v3 não deriva da captura v2 registrada")
        if not registry.get("evidence"):
            raise ValueError("A captura v3 não contém evidência revisada")

        units = con.read_parquet(str(source / names[0])).df()
        issues = con.read_parquet(str(source / names[1])).df()
        if units.duplicated(GEO).any():
            raise ValueError("Unidade de log duplicada")
        cases = issues[GEO].drop_duplicates().merge(
            units, on=GEO, how="left", validate="one_to_one", indicator=True)
        if not cases["_merge"].eq("both").all():
            raise ValueError("Apontamento sem unidade de origem")
        cases = cases.drop(columns="_merge")
        sources = research["sources"]
        source_map = {item["source_id"]: item for item in sources}
        if len(source_map) != len(sources):
            raise ValueError("Fonte com identificador repetido")
        for item in sources:
            capture = (raw / item["capture_file"]).resolve()
            if not capture.is_relative_to(raw) or sha256(capture) != item["capture_sha256"]:
                raise ValueError("Fonte não corresponde ao arquivo preservado")
        case_keys = {key(row) for row in cases.to_dict("records")}
        search_map = {}
        searches = research["queries"]
        for search in searches:
            search_key = key(search)
            if search_key not in case_keys:
                raise ValueError("Busca não pertence a caso do inventário")
            search_map.setdefault(search_key, []).append(search["search_id"])

        evidence = registry["evidence"]
        evidence_ids = [item["evidence_id"] for item in evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidência repetida")
        matched_evidence = set()
        confrontation, requests, case_rows = [], [], []
        for case in cases.sort_values(GEO).to_dict("records"):
            selected = issues
            for name in GEO:
                selected = selected.loc[selected[name].eq(case[name])]
            indicators = selected.indicator.tolist()
            identifier = case_id(case)
            initial = any(value != "target_error_records" for value in indicators) or case["opensession_erro"] > 0
            statuses = []
            for issue in selected.to_dict("records"):
                rows = [item for item in evidence
                        if key(item["case"]) == key(case) and item.get("indicator") == issue["indicator"]]
                outcomes = []
                for item in rows:
                    if item["source_id"] not in source_map:
                        raise ValueError("Evidência sem fonte registrada")
                    outcome = evaluate(case, issue["indicator"], source_map[item["source_id"]], item)
                    if outcome not in {
                            "registro_corrobora_no_escopo",
                            "divergencia_documental_a_revisar",
                            "evidencia_inconclusiva"}:
                        raise ValueError(
                            f"Evidência {item['evidence_id']} não pode ser confrontada: {outcome}")
                    outcomes.append(outcome)
                    matched_evidence.add(item["evidence_id"])
                status = (
                    "divergencia_documental_a_revisar" if "divergencia_documental_a_revisar" in outcomes else
                    "registro_corrobora_no_escopo" if "registro_corrobora_no_escopo" in outcomes else
                    "evidencia_insuficiente" if outcomes else "sem_documento_especifico")
                statuses.append(status)
                confrontation.append(dict(
                    **issue, case_id=identifier, document_status=status,
                    evidence_ids=";".join(item["evidence_id"] for item in rows) or None,
                    cause_status="nao_confirmada_por_esta_rotina"))
            case_row = {name: case[name] for name in GEO + [
                "municipality_name_1", "group", "region", "target_date", "opensession_erro"]}
            case_row.update(
                case_id=identifier, priority="inicial" if initial else "acompanhamento",
                issues=len(selected), indicators=";".join(sorted(set(indicators))),
                individual_searches=len(search_map.get(key(case), [])),
                research_status="busca_individual_registrada" if key(case) in search_map
                else "busca_individual_nao_realizada",
                document_status="confronto_com_evidencia_especifica"
                if any(value in ("registro_corrobora_no_escopo", "divergencia_documental_a_revisar")
                       for value in statuses) else "sem_confronto_especifico_concluido",
                cause_status="nao_confirmada_por_esta_rotina",
                card=f"fichas/{identifier}.html", request_draft=f"minutas/{identifier}.txt")
            case_rows.append(case_row)
            (destination / "minutas").mkdir(exist_ok=True)
            (destination / case_row["request_draft"]).write_text(
                request_text(case, indicators), encoding="utf-8")
            for document_kind in ("ata_mrv", "registro_atendimento_substituicao"):
                requests.append(dict(
                    **{name: case[name] for name in GEO}, case_id=identifier,
                    document_kind=document_kind, status="a_localizar",
                    note="Tipo documental a procurar; não é comprovação de existência ou pedido enviado"))
        if set(evidence_ids) != matched_evidence:
            raise ValueError("Evidência não corresponde a apontamento existente")

        case_frame = pd.DataFrame(case_rows)
        confrontation_frame = pd.DataFrame(confrontation)
        frames = dict(
            casos=case_frame, confronto=confrontation_frame, buscas=pd.DataFrame(searches),
            resultados_busca=pd.DataFrame(research["results"]), fontes=pd.DataFrame(sources),
            documentos_necessarios=pd.DataFrame(requests),
            tentativas_busca=pd.DataFrame(json.loads(
                (raw / "novas" / "tentativas.json").read_text(encoding="utf-8"))))
        for name, frame in frames.items():
            export_frame(con, frame, destination / name)
        write_json(destination / "evidencias_registradas.json", registry)
        summary = dict(
            sections=len(case_frame[[name for name in GEO if name != "turn"]].drop_duplicates()),
            section_turns=len(case_frame), issue_rows=len(confrontation_frame),
            initial_units=int(case_frame.priority.eq("inicial").sum()),
            individual_searches=len(searches),
            units_with_individual_search=int(case_frame.individual_searches.gt(0).sum()),
            units_without_individual_search=int(case_frame.individual_searches.eq(0).sum()),
            search_results=len(research["results"]),
            reviewed_context_sources=expansion_summary["reviewed_context_sources"],
            context_sources_unique_urls=expansion_summary["context_sources_unique_urls"],
            limited_context_captures=expansion_summary["limited_context_captures"],
            registered_evidence_entries=len(evidence),
            specific_evidence_entries=sum(source_map[item["source_id"]]["kind"] in SPECIFIC_TYPES
                                          for item in evidence),
            official_response_entries=sum(source_map[item["source_id"]]["kind"] in RESPONSE_TYPES
                                          for item in evidence),
            issues_corrobated=int(confrontation_frame.document_status.eq(
                "registro_corrobora_no_escopo").sum()),
            documentary_differences_for_review=int(confrontation_frame.document_status.eq(
                "divergencia_documental_a_revisar").sum()),
            causes_confirmed=None,
            cause_interpretation="A confirmação causal não é automatizada; evidência zero ou limitada não prova inexistência",
            document_requirements=len(requests), cards=len(case_frame), local_request_drafts=len(case_frame),
            requests_sent=0, capture_version="v3", research_round="ampliacao",
            capture_manifest_sha256=sha256(raw / "manifesto.json"), capture_hashes=raw_manifest,
            previous_capture_manifest_sha256=research["previous_capture_manifest_sha256"],
            evidence_revision_manifest_sha256=sha256(data / "auditoria" / "atas" / "v2" / "manifesto.json"),
            status_counts=records(case_frame.groupby(
                ["priority", "research_status", "document_status"]).size().reset_index(name="units")),
            interpretation="Confronto documental limitado ao conteúdo, unidade e apontamento revisados; nenhuma causa é confirmada automaticamente")
        from .audit_atas_report_v3 import render
        render(destination, summary, case_frame, confrontation_frame,
               pd.DataFrame(sources), pd.DataFrame(searches), evidence, source_map)
        write_json(destination / "manifesto_fichas.json", {
            path.relative_to(destination).as_posix(): sha256(path)
            for folder in ("fichas", "minutas")
            for path in sorted((destination / folder).glob("*")) if path.is_file()})
        code_files = [
            Path(__file__), Path(__file__).with_name("audit_atas_report_v3.py"),
            Path(__file__).with_name("atas_evidence.py"),
            Path(__file__).with_name("audit_atas.py"),
            Path(__file__).with_name("pdf_layout.py"),
            Path(__file__).with_name("analysis.py"),
            Path(__file__).with_name("national_common.py"),
            Path(__file__).with_name("sources.py")]
        return finish(source, destination, state, summary, code_files)
    except Exception as exc:
        failed(destination, state, exc)
        raise
    finally:
        con.close()
