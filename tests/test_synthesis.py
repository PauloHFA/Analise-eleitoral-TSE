import pandas as pd

from eleicoes.synthesis import coverage_counts, persistence_status, executive_html, metric_table


def nominal_and_attendance():
    rows = []
    # 42 geografias, 83 unidades por turno, 576 linhas de candidatos.
    for geo in range(42):
        for turn in ((1, 2) if geo < 41 else (1,)):
            for candidate in range(7 if len(rows) < 546 else 6):
                rows.append(dict(year=2026, turn=turn, uf="ZZ", municipality=geo, zone=1,
                                 candidate=candidate, status="cobertura divergente", official_votes=0))
    nominal = pd.DataFrame(rows[:576])
    # Manter todas as 83 unidades mesmo com menos candidatos na última.
    while len(nominal) < 576:
        nominal = pd.concat([nominal, nominal.iloc[[-1]]], ignore_index=True)
    attendance = nominal[["year", "turn", "uf", "municipality", "zone"]].drop_duplicates()
    attendance = attendance.assign(attendance_sections=0, attendance_official=0)
    return nominal, attendance


def test_coverage_units_are_not_interchangeable():
    nominal, attendance = nominal_and_attendance()
    assert coverage_counts(nominal, attendance) == dict(geographic_units=42, turn_units=83,
        candidate_rows=576, compatible_zero_attendance_rows=576, unresolved_rows=0)


def test_missing_attendance_does_not_become_zero():
    nominal, attendance = nominal_and_attendance()
    missing = attendance.iloc[1:].copy()
    result = coverage_counts(nominal, missing)
    assert result["unresolved_rows"] == 7
    assert result["compatible_zero_attendance_rows"] == 569


def test_positive_official_votes_are_not_explained_by_zero_attendance():
    nominal, attendance = nominal_and_attendance()
    nominal.loc[0, "official_votes"] = 1
    result = coverage_counts(nominal, attendance)
    assert result["unresolved_rows"] == 1


def test_attendance_must_be_zero_in_both_sources():
    nominal, attendance = nominal_and_attendance()
    attendance.loc[attendance.index[0], "attendance_official"] = 1
    assert coverage_counts(nominal, attendance)["unresolved_rows"] == 7


def test_raw_zero_never_claims_persistence_was_audited():
    status = persistence_status(0)
    assert status["value"] is None
    assert status["status"] == "não investigado"
    assert status["raw_compatibility_value"] == 0
    assert "não foi realizada" in status["interpretation"]


def test_summary_keeps_territorial_and_statistical_universes_distinct():
    synthesis = {"metrics": [
        dict(id="comparable", label="Territorialmente comparáveis", value=3, unit="seções", source="a.parquet", status="realizado"),
        dict(id="eligible", label="Elegíveis para triagem", value=2, unit="seções", source="a.parquet", status="realizado")],
        "coverage_matrix": [], "recommendations": [], "persistence": persistence_status(0)}
    rendered = executive_html(synthesis)
    assert "Territorialmente comparáveis</td><td>3" in rendered
    assert "Elegíveis para triagem</td><td>2" in rendered
    assert metric_table(synthesis, {"eligible"})[0]["value"] == 2
    assert "Persistência: não investigada" in rendered


def test_readme_and_html_follow_the_same_numeric_source():
    from eleicoes.documentation import render_readme
    synthesis = dict(metrics=[dict(id="combined", label="Triagem combinada", value=63809,
        unit="seções", source="indicadores_secoes.parquet", status="realizado")],
        coverage_matrix=[], regional=[], exclusions=[], historical=[], directed_sensitivity=[],
        news=[], duplicate_groups={}, recommendations=[], states=[], persistence=persistence_status(0),
        source_versions=dict(years=[2026], retrieved_utc_min="data", retrieved_utc_max="data", generations=[], geography=[]),
        rio_de_janeiro={**{f"votes_{c}_{t}": 1 for c in (13,22) for t in (1,2)},
                        **{f"cohort_coverage_attendance_{t}_pct": 100 for t in (1,2)},
                        **{f"cohort_margin_{t}_votes": 0 for t in (1,2)}})
    for value in (63809, 123):
        synthesis["metrics"][0]["value"] = value
        pretty = "63.809" if value == 63809 else "123"
        assert pretty in render_readme(synthesis, "{{overview}}")
        assert pretty in executive_html(synthesis)
