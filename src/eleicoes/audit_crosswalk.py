"""Cruzamento local e descritivo dos logs com votação, indicadores e assinaturas."""
from pathlib import Path
import json

import duckdb
import pandas as pd

from .analysis import export_frame
from .national_common import begin, failed, finish
from .sources import sha256

GEO = ["year", "turn", "uf", "municipality", "zone", "section"]
CANDIDATE_KEY = GEO + ["candidate"]
VOTE_FIELDS = ["rdv_votes", "binary_bu_votes", "image_votes", "result_votes", "csv_bu_votes"]
INDICATOR_FIELDS = [
    "coverage", "comparable", "small", "comparison_reason",
    "generation_1", "generation_2", "vote_generation_1", "vote_generation_2",
    "turnout_1", "turnout_2", "delta_turnout_pp", "delta_null_pp",
    "delta_share_13_pp", "delta_share_22_pp", "delta_votes_13", "delta_votes_22",
]


def _validate_keys(frame, columns, label):
    if frame[columns].isna().any().any():
        raise ValueError(f"Chave incompleta em {label}")
    for column in columns:
        if frame[column].astype("string").str.strip().eq("").any():
            raise ValueError(f"Chave vazia em {label}: {column}")
    if frame.duplicated(columns).any():
        raise ValueError(f"Chave repetida em {label}")


def _verify_stage(source, stage, artifacts):
    folder = source / "auditoria" / stage
    summary = json.loads((folder / "resumo.json").read_text(encoding="utf-8"))
    if summary.get("status") != "concluído" or not summary.get("preservation_verified"):
        raise ValueError(f"Etapa {stage} não está concluída e preservada")
    manifest = json.loads((folder / "manifesto.json").read_text(encoding="utf-8"))
    for name in artifacts:
        path = folder / name
        if manifest.get(name) != sha256(path):
            raise ValueError(f"Artefato de {stage} diverge do manifesto: {name}")


def _status_for_sample(row):
    if pd.isna(row.get("sample_vote_rows")):
        return "sem_correspondencia"
    if row["sample_incomplete_rows"] > 0:
        return "incompleta"
    if row["sample_discordant_rows"] > 0:
        return "discordante_nos_valores"
    if row["sample_nonconcordant_status_rows"] > 0:
        return "status_fonte_nao_concordante"
    return "concordante_nas_fontes_amostrais"


def _status_for_national(row):
    if pd.isna(row.get("national_vote_rows")):
        return "sem_correspondencia"
    if row["national_incomplete_rows"] > 0:
        return "incompleta"
    if row["national_discordant_rows"] > 0 or row["national_nonconcordant_status_rows"] > 0:
        return "divergente_nas_fontes"
    if row["national_candidate_rows_missing"] > 0 or row["national_only_candidate_rows"] > 0:
        return "lacuna_de_correspondencia_candidato"
    return "concordante_nas_fontes_nacionais"


def build_crosswalk(logs, issues, signatures, sample_votes, national_votes, indicators):
    """Constrói três níveis: unidade, apontamento e candidato; ausências ficam explícitas."""
    logs = logs.copy()
    issues = issues.copy()
    signatures = signatures.loc[
        signatures.kind.eq("log") & signatures.role.eq("hw")].copy()
    indicators = indicators.loc[indicators.year.eq(2026)].copy()

    _validate_keys(logs, GEO, "logs")
    _validate_keys(signatures, GEO, "assinaturas de hardware dos logs")
    _validate_keys(indicators, ["year", "uf", "municipality", "zone", "section"], "indicadores 2026")
    _validate_keys(sample_votes, CANDIDATE_KEY, "conferência amostral por candidato")

    if set(logs.year) != {2026}:
        raise ValueError("O cruzamento foi delimitado aos logs de 2026")
    if not set(issues.columns).issuperset(GEO + ["indicator", "count", "status", "reason"]):
        raise ValueError("Esquema de apontamentos incompatível")
    _validate_keys(issues, GEO + ["indicator"], "apontamentos")
    if not set(sample_votes.columns).issuperset(CANDIDATE_KEY + VOTE_FIELDS + [
            "comparison_complete", "status"]):
        raise ValueError("Esquema da conferência amostral incompatível")
    if not set(national_votes.columns).issuperset(CANDIDATE_KEY + [
            "votes_result", "votes_bu", "difference", "status"]):
        raise ValueError("Esquema da comparação nacional incompatível")

    log_keys = logs[GEO].drop_duplicates()
    national_scope = national_votes.merge(
        log_keys, on=GEO, how="inner", validate="many_to_one")
    _validate_keys(national_scope, CANDIDATE_KEY, "comparação nacional nas unidades dos logs")

    sample_votes["sample_values_complete"] = (
        sample_votes[VOTE_FIELDS].notna().all(axis=1)
        & sample_votes.comparison_complete.fillna(False))
    sample_votes["sample_value_disagreement"] = (
        sample_votes[VOTE_FIELDS].nunique(axis=1, dropna=True).gt(1)
        & sample_votes["sample_values_complete"])
    sample_votes["sample_status_nonconcordant"] = sample_votes.status.ne("concordante")

    national_scope["national_values_complete"] = national_scope[
        ["votes_result", "votes_bu", "difference"]].notna().all(axis=1)
    national_scope["national_value_disagreement"] = (
        national_scope.votes_result.notna() & national_scope.votes_bu.notna()
        & national_scope.votes_result.ne(national_scope.votes_bu))
    national_scope["national_difference_nonzero"] = (
        national_scope.difference.notna() & national_scope.difference.ne(0))
    national_scope["national_status_nonconcordant"] = national_scope.status.ne("concordante")

    sample_group = sample_votes.groupby(GEO, dropna=False).agg(
        sample_vote_rows=("candidate", "size"),
        sample_candidate_count=("candidate", "nunique"),
        sample_complete_rows=("sample_values_complete", "sum"),
        sample_incomplete_rows=("sample_values_complete", lambda values: int((~values).sum())),
        sample_discordant_rows=("sample_value_disagreement", "sum"),
        sample_nonconcordant_status_rows=("sample_status_nonconcordant", "sum"),
    ).reset_index()
    national_group = national_scope.groupby(GEO, dropna=False).agg(
        national_vote_rows=("candidate", "size"),
        national_candidate_count=("candidate", "nunique"),
        national_incomplete_rows=("national_values_complete", lambda values: int((~values).sum())),
        national_discordant_rows=("national_value_disagreement", "sum"),
        national_nonzero_difference_rows=("national_difference_nonzero", "sum"),
        national_nonconcordant_status_rows=("national_status_nonconcordant", "sum"),
    ).reset_index()

    sample_columns = GEO + ["candidate"] + VOTE_FIELDS + [
        "comparison_complete", "status", "result_source", "bu_source",
        "sample_values_complete", "sample_value_disagreement"]
    sample_detail = sample_votes[sample_columns].rename(columns={
        "comparison_complete": "sample_comparison_complete",
        "status": "sample_status",
        "result_source": "sample_result_source",
        "bu_source": "sample_bu_source",
    })
    national_columns = CANDIDATE_KEY + [
        "votes_result", "votes_bu", "difference", "result_generation", "bu_generation",
        "result_source", "bu_source", "status", "national_values_complete",
        "national_value_disagreement", "national_difference_nonzero"]
    national_detail = national_scope[national_columns].rename(columns={
        "votes_result": "national_votes_result",
        "votes_bu": "national_votes_bu",
        "difference": "national_difference",
        "result_generation": "national_result_generation",
        "bu_generation": "national_bu_generation",
        "result_source": "national_result_source",
        "bu_source": "national_bu_source",
        "status": "national_status",
    })
    candidate_detail = sample_detail.merge(
        national_detail, on=CANDIDATE_KEY, how="outer", validate="one_to_one",
        indicator="_candidate_merge")
    candidate_detail["candidate_match_status"] = candidate_detail["_candidate_merge"].map({
        "both": "correspondente",
        "left_only": "sem_linha_correspondente_na_conferencia_nacional",
        "right_only": "somente_na_conferencia_nacional",
    })
    candidate_detail["national_record_present"] = candidate_detail["_candidate_merge"].ne("left_only")
    candidate_detail = candidate_detail.drop(columns="_candidate_merge")

    gap_counts = candidate_detail.assign(
        national_candidate_rows_missing=candidate_detail.candidate_match_status.eq(
            "sem_linha_correspondente_na_conferencia_nacional"),
        national_only_candidate_rows=candidate_detail.candidate_match_status.eq(
            "somente_na_conferencia_nacional"),
    ).groupby(GEO, dropna=False).agg(
        national_candidate_rows_missing=("national_candidate_rows_missing", "sum"),
        national_only_candidate_rows=("national_only_candidate_rows", "sum"),
    ).reset_index()

    signature_columns = GEO + [
        "member", "hash_status", "crypto_status", "crypto_reason", "algorithm",
        "local_sha256", "signed_sha512"]
    signature_view = signatures[signature_columns].rename(columns={
        name: "signature_" + name for name in signature_columns if name not in GEO})

    indicator_columns = ["year", "uf", "municipality", "zone", "section"] + INDICATOR_FIELDS
    indicator_view = indicators[indicator_columns].rename(columns={
        name: "indicator_" + name for name in INDICATOR_FIELDS})

    units = logs.merge(indicator_view, on=["year", "uf", "municipality", "zone", "section"],
                       how="left", validate="many_to_one", indicator="_indicator_merge")
    units["indicator_join_status"] = units["_indicator_merge"].map({
        "both": "correspondente", "left_only": "sem_correspondencia"})
    units = units.drop(columns="_indicator_merge")
    units = units.merge(signature_view, on=GEO, how="left", validate="one_to_one",
                        indicator="_signature_merge")
    units["signature_join_status"] = units["_signature_merge"].map({
        "both": "correspondente", "left_only": "sem_correspondencia"})
    units = units.drop(columns="_signature_merge")
    units["signature_local_hash_matches_log"] = (
        units.source_sha256.notna() & units.signature_local_sha256.notna()
        & units.source_sha256.eq(units.signature_local_sha256))
    units["signature_assessment"] = "assinatura_nao_confirmada"
    signature_valid = (
        units.signature_join_status.eq("correspondente")
        & units.signature_hash_status.eq("concordante")
        & units.signature_crypto_status.eq("valida_com_chave_embutida")
        & units.signature_local_hash_matches_log)
    units.loc[signature_valid, "signature_assessment"] = (
        "hash_concordante_e_assinatura_valida_com_chave_embutida")

    units = units.merge(sample_group, on=GEO, how="left", validate="one_to_one")
    units = units.merge(national_group, on=GEO, how="left", validate="one_to_one")
    units = units.merge(gap_counts, on=GEO, how="left", validate="one_to_one")
    units["sample_vote_status"] = units.apply(_status_for_sample, axis=1)
    units["national_vote_status"] = units.apply(_status_for_national, axis=1)
    units["has_target_error_message"] = units.target_error_records.gt(0)
    issue_units = set(map(tuple, issues[GEO].drop_duplicates().itertuples(index=False, name=None)))
    units["has_documented_log_issue"] = [
        tuple(row) in issue_units for row in units[GEO].itertuples(index=False, name=None)]

    unit_keys = set(map(tuple, units[GEO].itertuples(index=False, name=None)))
    unmatched = []

    def add_unmatched(source_name, relation, records, detail=None):
        for row in records:
            unmatched.append(dict(
                source=source_name, relation=relation,
                **{name: row.get(name) for name in GEO},
                candidate=row.get("candidate"), indicator=row.get("indicator"),
                detail=detail))

    for source_name, frame in (
            ("indicadores_2026", indicators),
            ("assinaturas_logs_hw", signatures),
            ("conferencia_amostral", sample_votes),
            ("conferencia_nacional", national_scope)):
        if source_name == "indicadores_2026":
            keys = set(map(tuple, frame[["year", "uf", "municipality", "zone", "section"]]
                           .itertuples(index=False, name=None)))
            for row in logs.to_dict("records"):
                identity = tuple(row[name] for name in ("year", "uf", "municipality", "zone", "section"))
                if identity not in keys:
                    add_unmatched(source_name, "unidade de log sem indicador 2026", [row])
        else:
            keys = set(map(tuple, frame[GEO].drop_duplicates().itertuples(index=False, name=None)))
            for row in logs.to_dict("records"):
                identity = tuple(row[name] for name in GEO)
                if identity not in keys:
                    add_unmatched(source_name, "unidade de log sem linha correspondente", [row])

    for row in issues.to_dict("records"):
        if tuple(row[name] for name in GEO) not in unit_keys:
            add_unmatched("apontamentos_logs", "apontamento sem unidade de log", [row], row["reason"])
    for row in candidate_detail.loc[
            candidate_detail.candidate_match_status.ne("correspondente")].to_dict("records"):
        add_unmatched(
            "conferencia_nacional" if row["candidate_match_status"].startswith("sem_linha")
            else "conferencia_amostral",
            "chave candidato sem correspondência entre tabelas", [row],
            row["candidate_match_status"])

    issue_context_columns = GEO + ["indicator", "count", "status", "reason"]
    unit_context = units[GEO + [
        "group", "region", "target_error_records", "sample_vote_status",
        "national_vote_status", "signature_assessment", "indicator_join_status"]]
    issue_detail = issues[issue_context_columns].merge(
        unit_context, on=GEO, how="left", validate="many_to_one", indicator="_unit_merge")
    issue_detail["unit_join_status"] = issue_detail["_unit_merge"].map({
        "both": "correspondente", "left_only": "sem_correspondencia"})
    issue_detail = issue_detail.drop(columns="_unit_merge")

    contingency = units.groupby([
        "group", "region", "has_target_error_message", "sample_vote_status",
        "national_vote_status"], dropna=False).size().reset_index(name="section_turns")
    unmatched_frame = pd.DataFrame(unmatched, columns=[
        "source", "relation", *GEO, "candidate", "indicator", "detail"])
    return units, issue_detail, candidate_detail, unmatched_frame, contingency


def run_crosswalk(source, destination=None):
    source = Path(source).resolve()
    destination = Path(destination).resolve() if destination else (
        source / "auditoria" / "cruzamento_integrado")
    names = [
        "auditoria/logs/resumo.json", "auditoria/logs/manifesto.json",
        "auditoria/logs/unidades.parquet", "auditoria/logs/pendencias.parquet",
        "auditoria/ed521/resumo.json", "auditoria/ed521/manifesto.json",
        "auditoria/ed521/arquivos_assinados.parquet",
        "auditoria/conferencia/resumo.json", "auditoria/conferencia/manifesto.json",
        "auditoria/conferencia/votacao.parquet",
        "indicadores_secoes.parquet", "conferencia_bu.parquet",
    ]
    source, destination, state = begin(source, destination, names)
    con = duckdb.connect()
    try:
        _verify_stage(source, "logs", ["unidades.parquet", "pendencias.parquet"])
        _verify_stage(source, "ed521", ["arquivos_assinados.parquet"])
        _verify_stage(source, "conferencia", ["votacao.parquet"])
        paths = {
            "logs": source / names[2],
            "issues": source / names[3],
            "signatures": source / names[6],
            "sample_votes": source / names[9],
            "indicators": source / names[10],
            "national_votes": source / names[11],
        }
        frames = {name: con.read_parquet(str(path)).df() for name, path in paths.items()}
        units, issues, candidates, unmatched, contingency = build_crosswalk(**frames)
        for name, frame in (
                ("unidades", units), ("apontamentos", issues),
                ("conferencia_candidatos", candidates),
                ("sem_correspondencia", unmatched), ("contingencias", contingency)):
            export_frame(con, frame, destination / name)

        national_rows = candidates.loc[candidates.national_status.notna()]
        summary = dict(
            section_turns=len(units),
            sections=units[["year", "uf", "municipality", "zone", "section"]].drop_duplicates().shape[0],
            log_issue_rows=len(issues),
            log_issue_section_turns=issues[GEO].drop_duplicates().shape[0],
            units_with_target_errors=int(units.has_target_error_message.sum()),
            indicator_matches=int(units.indicator_join_status.eq("correspondente").sum()),
            signature_matches=int(units.signature_join_status.eq("correspondente").sum()),
            signature_hash_matches=int(units.signature_local_hash_matches_log.sum()),
            signature_hash_concordant=int(units.signature_hash_status.eq("concordante").sum()),
            signature_crypto_valid_with_embedded_key=int(
                units.signature_crypto_status.eq("valida_com_chave_embutida").sum()),
            signature_chain_validated=0,
            sample_vote_candidate_rows=len(frames["sample_votes"]),
            sample_vote_complete_rows=int(units.sample_complete_rows.sum()),
            sample_vote_discordant_rows=int(units.sample_discordant_rows.sum()),
            sample_vote_status_nonconcordant_rows=int(
                units.sample_nonconcordant_status_rows.sum()),
            national_vote_candidate_rows=len(national_rows),
            national_vote_nonzero_difference_rows=int(
                national_rows.national_difference_nonzero.fillna(False).sum()),
            national_vote_value_disagreement_rows=int(
                national_rows.national_value_disagreement.fillna(False).sum()),
            error_units_sample_vote_concordant=int((
                units.has_target_error_message
                & units.sample_vote_status.eq("concordante_nas_fontes_amostrais")).sum()),
            error_units_sample_vote_discordant=int((
                units.has_target_error_message
                & units.sample_vote_status.eq("discordante_nos_valores")).sum()),
            error_units_national_nonzero_difference=int((
                units.has_target_error_message
                & units.national_nonzero_difference_rows.fillna(0).gt(0)).sum()),
            candidate_rows_without_national_match=int(
                candidates.candidate_match_status.eq(
                    "sem_linha_correspondente_na_conferencia_nacional").sum()),
            candidate_rows_only_in_national=int(
                candidates.candidate_match_status.eq(
                    "somente_na_conferencia_nacional").sum()),
            unmatched_rows=len(unmatched),
            causes_confirmed=None,
            external_contact_made=False,
            interpretation=(
                "Cruzamento descritivo de bases locais por chaves de unidade e candidato. "
                "Ausência de linha não é zero; concordância não prova causa, autenticidade institucional "
                "ou independência das fontes. A amostra dirigida não estima frequências nacionais."),
            notes=[
                "A validação criptográfica informada é com chave embutida; cadeia institucional e revogação não são validadas por este cruzamento.",
                "Assinatura se vincula ao arquivo de log selecionado; não certifica cada membro extraído nem a completude temporal do log.",
                "Conferencia amostral compara RDV, BU binário, imagem e arquivos de resultado/BU da seção; não é fonte independente em papel.",
                "Linhas de candidato ausentes na comparação nacional permanecem sem valor imputado.",
            ],
        )
        from .audit_crosswalk_report import render
        render(destination, summary, units, issues, candidates, unmatched, contingency)
        code_files = [
            Path(__file__), Path(__file__).with_name("audit_crosswalk_report.py"),
            Path(__file__).with_name("national_common.py"),
            Path(__file__).with_name("analysis.py"),
            Path(__file__).with_name("pdf_layout.py"),
            Path(__file__).with_name("sources.py"),
        ]
        return finish(source, destination, state, summary, code_files)
    except Exception as exc:
        failed(destination, state, exc)
        raise
    finally:
        con.close()
