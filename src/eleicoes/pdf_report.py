"""Relatório PDF narrativo: perguntas, evidências, interpretação e anexos completos."""
from __future__ import annotations

from datetime import datetime
import html
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
from reportlab.platypus import KeepTogether, PageBreak, Spacer

from .pdf_layout import AnalysisPDF, WIDTH, callout, contents, heading, p, pdf_styles, picture, table
from .sources import sha256, write_json


def n(value, decimals=0, *, signed=False):
    if value is None or pd.isna(value) or not math.isfinite(float(value)):
        return "não disponível"
    sign = "+" if signed and value > 0 else ""
    return sign + f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def candidate_label(candidate, names=None):
    name = str((names or {}).get(candidate, "")).strip()
    if candidate == 13 and "LULA" in name.upper():
        return "Lula"
    if candidate == 22 and any(token in name.upper() for token in ("FLAVIO", "FLÁVIO")):
        return "Flávio"
    return name.title() if name else f"Candidato {candidate}"


def case_explanation(row, finalists, names=None):
    """Descreve o indicador que motivou a prioridade sem inferir causa ou persistência."""
    metrics = {"delta_turnout_pp": "comparecimento sobre aptos", "delta_blank_pp": "brancos sobre comparecentes",
               "delta_null_pp": "nulos sobre comparecentes"}
    for candidate in finalists:
        name = candidate_label(candidate, names)
        metrics[f"delta_share_{candidate}_pp"] = f"participação de {name} na soma nominal"
    available = [(key, float(row.get("z_" + key))) for key in metrics
                 if pd.notna(row.get("z_" + key)) and math.isfinite(float(row.get("z_" + key)))]
    if not available:
        return "A seleção decorre de mudança absoluta ou passagem a zero. Não há escore robusto informativo disponível para explicar esta prioridade."
    key, score = max(available, key=lambda item: item[1])
    delta, median, mad = (row.get(key), row.get("peer_median_" + key), row.get("peer_mad_" + key))
    mad_text = n(mad, 4) if mad is not None and float(mad) >= .0001 else f"{float(mad):.2e}" if pd.notna(mad) else "não disponível"
    return (f"O maior afastamento está em {metrics[key]}: mudança de {n(delta, 2, signed=True)} pp, "
            f"contra mediana de {n(median, 2, signed=True)} pp nos pares (MAD {mad_text} pp; escore {n(score, 2)}). "
            "O escore mede distância aos pares; uma dispersão pequena pode elevar a prioridade.")


def _case_rows(row, finalists, names=None):
    rows = []
    for label, key, rate, suffix in [
        ("Eleitorado apto", "aptos", None, ""),
        ("Comparecimento", "attendance", "turnout", " dos aptos"),
        ("Soma nominal 1–94", "valid", None, ""),
        *[(f"{candidate_label(c, names)} — votos", f"votes_{c}", f"share_{c}", " dos nominais") for c in finalists],
        ("Brancos", "blank", "blank_share", " dos comparecentes"),
        ("Nulos", "null_votes", "null_share", " dos comparecentes"),
    ]:
        values = [row.get(f"{key}_{t}") for t in (1,2)]
        cells = [n(v) for v in values]
        change = n(values[1] - values[0], signed=True) if all(pd.notna(v) for v in values) else "não disponível"
        if rate:
            ratios = [row.get(f"{rate}_{t}") for t in (1,2)]
            cells = [f"{cell} ({n(r * 100, 1)}%)" if pd.notna(r) else cell for cell, r in zip(cells, ratios)]
            if all(pd.notna(r) for r in ratios):
                change += f"; {n(100 * (ratios[1]-ratios[0]), 1, signed=True)} pp"
        rows.append([label, *cells, change])
    return rows


def build_pdf_report(output, *, summary, history, priority, finalists, candidate_names=None,
                     manifest=None, synthesis=None, investigation=None, electoral_map=None,
                     demo=False, **unused):
    output = Path(output)
    styles = pdf_styles()
    synth = synthesis or {}
    metrics = {m["id"]: m for m in synth.get("metrics", [])}
    fallback = {"observed": "secoes_no_universo", "comparable": "comparaveis", "excluded": "sem_comparacao",
                "combined": "alertas_estatisticos", "bu_matching": "registros_bu_conferidos"}
    def value(key):
        return metrics.get(key, {}).get("value", summary.get(fallback.get(key, "")))
    def count(key):
        return n(value(key))
    story = []
    def text(body, style="Text"):
        story.append(p(body, styles, style))
    def chapter(title, key):
        story.extend([PageBreak(), heading(title, key, styles)])
    def sub(title):
        story.append(p(title, styles, "Subhead"))
    def source(body):
        story.extend([p("Fonte: " + body, styles, "Small"), Spacer(1, 8)])
    def grid(headers, rows, proportions):
        total = sum(proportions)
        story.append(table(headers, rows, [WIDTH * x / total for x in proportions], styles))
    def figure(name, explanation, *, height=255):
        path = output / "graficos" / name
        if path.exists():
            story.append(KeepTogether([picture(path, max_height=height), p(explanation, styles, "Small"), Spacer(1, 10)]))

    year = summary.get("ano", synth.get("year", 2026))
    text("RELATÓRIO DE ANÁLISE", "Small")
    text(f"Eleições presidenciais\n{year}", "Cover")
    text("Mudanças entre turnos e consistência dos arquivos", "Deck")
    text("Brasil, exterior e investigação dirigida em Rio de Janeiro e Minas Gerais. Leitura orientada por perguntas, com resultados, métodos e limites antes dos anexos.")
    if demo:
        story.append(callout("DEMONSTRAÇÃO — DADOS SIMULADOS", "Os valores deste documento demonstram o programa e não representam resultados eleitorais reais.", styles))
    grid(["Universo observado", "Unidades na triagem", "Linhas BU concordantes"],
         [[count("observed"), count("combined"), count("bu_matching")]], [1,1,1])
    text("As três contagens acima têm unidades distintas: seções observadas, seções selecionadas por critérios exploratórios e linhas de votação comparadas entre arquivos. Não são quantidades de irregularidades.")
    story.append(callout("Como interpretar este relatório", "Mudança observada, alerta estatístico e divergência documental são situações distintas. A confirmação dos valores nos arquivos não explica a escolha dos eleitores. A investigação de todas as incongruências não está encerrada.", styles))
    versions = synth.get("source_versions", {})
    if versions.get("retrieved_utc_min"):
        start = datetime.fromisoformat(versions['retrieved_utc_min']).strftime("%d/%m/%Y às %H:%M")
        end = datetime.fromisoformat(versions['retrieved_utc_max']).strftime("%d/%m/%Y às %H:%M")
        text(f"Cópias eleitorais obtidas de {start} a {end} (UTC). As datas de geração das fontes são detalhadas no capítulo de documentação.", "Small")
    text("Fontes: TSE e IBGE. Produção analítica: PauloHFA. Esta edição reorganiza a apresentação; os dados e os critérios analíticos são os documentados na síntese.", "Small")

    chapter("Sumário de leitura", "sumario")
    text("Para uma visão rápida, leia os achados e a conferência documental. Para avaliar um lugar, consulte a investigação dirigida e os anexos. Os marcadores do leitor de PDF e os números do sumário permitem navegar pelo documento.")
    story.append(contents(styles))

    chapter("1. O que foi encontrado", "achados")
    text("As perguntas originais eram localizar passagens a zero, grandes viradas e diferenças entre arquivos. Os resultados abaixo respondem a cada pergunta e indicam o limite da evidência.")
    sub("Há seções em que um finalista passa de votos positivos para zero?")
    if value("zero_flavio") is not None:
        leadership = "Ele não liderava nenhuma dessas seções." if value("previous_lead") == 0 else f"Ele liderava {count('previous_lead')} dessas seções."
        text(f"Sim. Em {count('zero_flavio')} seções, Flávio não recebeu votos no segundo turno e os votos válidos foram exclusivos para Lula. Em {count('positive_zero')} delas havia votos para Flávio no primeiro turno; em {count('already_zero')} ele já estava zerado. As passagens a zero somavam {count('previous_votes')} votos anteriores, com máximo de {count('previous_max')} por seção. {leadership}")
        text(f"A comparação territorial é válida em {count('zero_comparable')} dessas passagens e limitada em {count('zero_limited')}. O sentido inverso também foi examinado: Lula zerou em {count('zero_lula')} seções. A exclusividade nos válidos pode coexistir com votos brancos ou nulos.")
    else:
        text("A investigação nacional de unanimidades não está disponível nesta execução. As passagens a zero eventualmente presentes nas fichas devem ser interpretadas no universo processado.")
    sub("Houve viradas de liderança no Rio de Janeiro e em Minas Gerais?")
    if value("flips_RJ") is not None:
        text(f"Sim. O resultado municipal completo passou de vantagem de Flávio para vitória de Lula em {count('flips_RJ')} municípios do RJ e {count('flips_MG')} de MG. Perda de vantagem não significa necessariamente perda de votos absolutos: o adversário pode ter crescido mais. O capítulo 6 mostra esse efeito na cidade do Rio e informa quanto do comparecimento está coberto pela coorte comparável.")
    else:
        text("O estudo dirigido de viradas por estado não está disponível nesta execução.")
    sub("Os arquivos de votação concordam? E as diferenças de soma?")
    text(f"A conferência BU × resultado por seção encontrou {count('bu_matching')} linhas concordantes. Essa é uma checagem de consistência entre representações do resultado da urna, e não uma auditoria independente do equipamento.")
    if value("noninstalled") is not None:
        text(f"Os apontamentos de {count('noninstalled')} seções não instaladas foram explicados quanto à regra aritmética aplicada. A diferença nominal de {count('technical_votes')} votos coincide com nulos técnicos nas mesmas {count('technical_units')} unidades município/zona do primeiro turno. A razão jurídica ou operacional dessa classificação não foi estabelecida.")
    story.append(callout("O que permanece em aberto", "A confirmação de persistência de divergências não foi realizada. O zero do campo legado não é demonstração de ausência de irregularidades. Remanejamentos completos, causas jurídicas e administrativas, RDV, assinaturas, logs e documentos físicos exigem procedimentos adicionais.", styles))
    if synth.get("coverage_matrix"):
        story.append(PageBreak())
        sub("Cobertura: o que foi realizado e o que permanece limitado")
        text("As classificações abaixo delimitam o alcance de cada resultado. Explicar um apontamento de soma não equivale a investigar a causa administrativa; confirmar uma quantidade não equivale a explicar escolhas dos eleitores.")
        grid(["Tema", "Situação", "O que a evidência permite afirmar"],
             [[r["question"], r["status"], r["evidence"]] for r in synth["coverage_matrix"]], [1.1,.8,1.8])
        text("A leitura deve manter separadas a consistência entre arquivos, a compatibilidade da unidade territorial e a investigação das causas. Os capítulos seguintes apresentam as evidências e o procedimento de conferência de cada grupo.")

    chapter("2. O que pode ser comparado", "cobertura")
    text("A comparação começa pela unidade territorial. Uma seção precisa ter fontes completas, composição compatível e o mesmo eleitorado apto nos dois turnos. Se esses elementos mudam, uma diferença de votação pode refletir a mudança da unidade observada.")
    grid(["Etapa", "Unidades de seção", "Significado"], [
        ["Observadas", count("observed"), "Inventário de todas as unidades identificadas, incluindo exterior."],
        ["Territorialmente comparáveis", count("comparable"), "Composição e aptos compatíveis; fontes aptas à comparação."],
        ["Elegíveis para triagem", count("eligible"), "Comparáveis e com pelo menos 50 comparecentes em ambos os turnos."],
        ["Sem comparação territorial válida", count("excluded"), "Continuam no inventário, com motivo de exclusão."],
        ["Comparáveis, mas pequenas", count("comparable_small"), "Descrição permitida; sem alerta estatístico individual."],
        ["Pequenas no inventário total", count("small"), "Categoria sobreposta: não deve ser somada às exclusões."],
    ], [1.2,.65,1.8])
    source("indicadores_secoes.parquet e cobertura_por_motivo.csv. A elegibilidade estatística é um subconjunto da comparabilidade territorial.")
    if synth.get("regional"):
        grid(["Universo", "Observadas", "Comparáveis", "Elegíveis", "Triagem"],
             [["Exterior (ZZ)" if r["is_exterior"] else "Brasil"] + [n(r[k]) for k in ("observed","comparable","eligible","combined")] for r in synth["regional"]], [1.1,1,1,1,1])
    if synth.get("exclusions"):
        sub("Por que há unidades fora da comparação?")
        grid(["Universo", "Motivo principal", "Unidades"],
             [["Exterior" if r["is_exterior"] else "Brasil", r["comparison_reason"], n(r["sections"])] for r in synth["exclusions"] if r["comparison_reason"] != "comparável"], [.6,2.7,.7])
    text("Os motivos principais são mutuamente exclusivos nessa classificação. Igualdade de aptos não compensa uma composição diferente. Códigos iguais também não descartam mudança física de endereço: não foi obtida uma correspondência completa de remanejamentos.")

    chapter("3. Mudanças e triagem estatística", "triagem")
    text("A triagem pergunta quais mudanças são grandes em termos absolutos ou afastadas das mudanças de seções semelhantes. Uma seção pode atender aos dois critérios; por isso, os resultados são reunidos por união, sem somar duas vezes a mesma seção.")
    grid(["Critério", "Unidades", "Como interpretar"], [
        ["10 pp ou passagem a zero", count("cutoff10"), "Mudança de pelo menos 10 pontos percentuais em um indicador, ou candidato de positivo para zero."],
        ["Desvio robusto > 3,5", count("robust"), "Afastamento da mudança em relação à mediana dos 30 pares."],
        ["Atendem aos dois", count("overlap"), "Sobreposição descontada ao calcular a união."],
        ["Somente limite absoluto/zero", count("cutoff_only"), "Não atende ao limite robusto."],
        ["Somente desvio robusto", count("robust_only"), "Não atende ao limite absoluto/zero."],
        ["União dos critérios", count("combined"), "Inventário de prioridades para revisão; não é contagem de fraude."],
    ], [1.1,.65,2])
    source("indicadores_secoes.parquet. Limites aplicados somente às seções elegíveis. pp = pontos percentuais.")
    sub("Como ler os gráficos")
    text("O primeiro gráfico mostra a distribuição da mudança de comparecimento. O eixo horizontal mede a diferença da taxa sobre aptos; o vertical conta seções. As linhas em ±10 pp são referências de triagem, não fronteiras entre votação regular e irregular.")
    figure("comparecimento.png", "Brasil; somente seções comparáveis. Taxa de comparecimento = comparecentes ÷ aptos. Variação = taxa do segundo menos a do primeiro turno, em pp.")
    text("No gráfico de votação, cada ponto associa a participação de um finalista na mesma seção nos dois turnos. Pontos acima da diagonal representam aumento de participação; isso pode ocorrer pela concentração de votos antes distribuídos entre vários candidatos.")
    figure("votacao.png", "Amostra reproduzível de até 40 mil seções comparáveis do Brasil. O denominador é a soma nominal dos códigos 1–94 em cada turno; as tabelas contêm o universo completo.")

    chapter("4. Conferência documental: o que foi explicado", "documentos")
    text("Há três conferências diferentes: votação BU × seção, somas internas e resultado por seção × totalização. A concordância na primeira não resolve automaticamente as outras duas.")
    sub("4.1 Votação nos boletins e nos resultados por seção")
    text(f"Foram encontradas {count('bu_matching')} linhas concordantes por seção/código de voto/turno. Essas linhas não representam pessoas distintas nem urnas distintas. Duplicidades, ausências e zeros implícitos foram tratados conforme a presença e o contexto da unidade.")
    sub("4.2 Seções não instaladas: por que o alerta de soma foi explicado")
    if value("noninstalled") is not None:
        text(f"Os {count('documentary_rows')} apontamentos seção/turno correspondem a {count('noninstalled')} seções distintas no exterior. Todas foram declaradas não instaladas, sem votação e com comparecimento e abstenções zerados. A regra comparecimento + abstenções = aptos foi aplicada fora de contexto.")
    text("A revisão explica o apontamento aritmético e mantém a seção fora da comparação. Não determina por que a seção não foi instalada nem onde seus eleitores puderam votar. A tabela original foi preservada junto da revisão com evidências.")
    source("pendencias_documentais, revisao_documental e fichas documentais. Explicado quanto ao apontamento não significa investigação de todas as causas concluída.")
    sub("4.3 Diferença nominal compensada em nulos técnicos")
    if value("technical_votes") is not None:
        text(f"Nas mesmas {count('technical_units')} combinações município/zona do primeiro turno, a diferença de {count('technical_votes')} votos nominais do candidato 28 corresponde aos nulos técnicos. A diferença é compensada nos nulos; brancos e total de votos coincidem. É uma correspondência aritmética compatível com reclassificação.")
    text("Os arquivos têm gerações diferentes. A razão jurídica ou operacional da classificação e a reconciliação integral com uma mesma versão oficial ainda não foram estabelecidas. A constatação aritmética não deve ser ampliada para uma explicação jurídica.")
    if versions.get("generations"):
        grid(["Geração da votação por seção", "Geração da totalização nominal"],
             [[r["section_generation"], r["official_generation"]] for r in versions["generations"]], [1,1])
        if any(r["section_generation"] == "ausente" for r in versions["generations"]):
            text("Ausente na coluna de votação por seção identifica linhas sem registro nominal nessa fonte; não é uma data de geração desconhecida para todos os arquivos. Essas ausências são contextualizadas pela conferência de comparecimento abaixo.")
    sub("4.4 Ausência nominal com comparecimento zero: três contagens distintas")
    grid(["Contagem", "Valor", "Unidade correta"], [
        ["Geografia sem turno", count("coverage_geographic_units"), "Combinações UF/município/zona."],
        ["Geografia por turno", count("coverage_turn_units"), "Combinações ano/turno/UF/município/zona."],
        ["Linhas por candidato", count("coverage_candidate_rows"), "Registros da conferência nominal."],
        ["Compatíveis com comparecimento zero", count("coverage_compatible_zero_attendance_rows"), "Linhas com zero publicado nas duas fontes e votos oficiais zero."],
    ], [1.3,.55,1.8])
    text("Não se trata de zonas distintas em todas as linhas: a mesma geografia reaparece por turno e candidato. A ausência nominal é compatível com comparecimento zerado, sem preencher artificialmente a fonte ausente. O motivo administrativo do comparecimento zero permanece fora da investigação concluída.")
    source("reconciliacao_municipio_zona, reconciliacao_comparecimento e reconciliacao_categorias. Apontamentos originais mantidos.")
    story.append(callout("Persistência: não investigada", "O valor bruto zero no resumo legado não é resultado de uma confirmação de persistência. Este relatório não conclui inexistência de irregularidades a partir desse campo.", styles))

    if investigation and not investigation.get("stale"):
        chapter("5. Passagens a zero e unanimidades", "zeros")
        text("Unanimidade nos votos válidos significa que apenas um finalista recebeu votos nominais. Ainda pode haver brancos e nulos. Unanimidade de todos os votos depositados é um subconjunto mais restrito.")
        grid(["Situação", "Seções", "Leitura"], [
            ["Flávio zerado no segundo turno", count("zero_flavio"), "Válidos exclusivos para Lula."],
            ["Flávio positivo → zero", count("positive_zero"), f"{count('previous_votes')} votos anteriores somados; máximo de {count('previous_max')} por seção."],
            ["Flávio já zerado no primeiro", count("already_zero"), "Não constitui passagem de positivo para zero."],
            ["Passagens comparáveis / limitadas", f"{count('zero_comparable')} / {count('zero_limited')}", "Limitação de composição/aptos continua identificada."],
            ["Lula zerado no segundo turno", count("zero_lula"), "Sentido inverso examinado com os mesmos critérios."],
            ["Lula: todos os votos depositados", count("all_ballots"), "Subconjunto das seções com Flávio zerado."],
            ["Liderança anterior de Flávio nas passagens", count("previous_lead"), "As passagens observadas não eram seções que ele liderava."],
        ], [1.4,.6,1.7])
        figure("investigacao_zeros.png", "As barras distinguem mudança observada de situação já existente no primeiro turno.", height=230)
        text("Os dois turnos foram confrontados com os BU, incluindo presença de registros, instalação, duplicidades e composição. Confirmação nos arquivos descreve os números observados; não explica por que pessoas escolheram um candidato.")
        source("investigacao_zeros.parquet, investigacao_conferencia_bu.parquet e fichas dirigidas. Lista completa no anexo A.")

        chapter("6. Viradas e redução de vantagem em RJ/MG", "viradas")
        text("A margem entre finalistas é 100 × (Flávio − Lula) ÷ (Flávio + Lula). Valor positivo favorece Flávio e negativo favorece Lula. A redução da margem é a margem do primeiro menos a do segundo turno. O denominador usa os dois finalistas, e difere da participação sobre todos os nominais.")
        grid(["UF", "Municípios Flávio → Lula", "O que foi contado"],
             [[uf, count("flips_" + uf), "Resultado territorial completo, independentemente da elegibilidade estatística da seção."] for uf in ("RJ","MG")], [.4,.9,2])
        if synth.get("states"):
            grid(["UF", "Flávio 1º", "Lula 1º", "Flávio 2º", "Lula 2º"],
                 [[r["uf"]]+[n(r[f"votes_{c}_{t}"]) for t in (1,2) for c in (22,13)] for r in synth["states"]], [.4,1,1,1,1])
        sub("Exemplo: ganhar votos e, ainda assim, perder a liderança")
        rio = synth.get("rio_de_janeiro", {})
        if rio:
            f1,f2,l1,l2 = (rio[k] for k in ("votes_22_1","votes_22_2","votes_13_1","votes_13_2"))
            grid(["Cidade do Rio", "1º turno", "2º turno", "Variação absoluta"], [
                ["Flávio", n(f1), n(f2), n(f2-f1, signed=True)],
                ["Lula", n(l1), n(l2), n(l2-l1, signed=True)],
                ["Saldo Flávio − Lula", n(f1-l1, signed=True), n(f2-l2, signed=True), n((f2-l2)-(f1-l1), signed=True)],
            ], [1.1,1,1,1])
            text(f"Flávio ganhou {n(f2-f1)} votos absolutos, enquanto Lula ganhou {n(l2-l1)}. O saldo mudou de vantagem de {n(f1-l1)} para Flávio a vantagem de {n(l2-f2)} para Lula. Isso demonstra uma mudança agregada de liderança; não uma identificação de transferências individuais.")
            text(f"Na coorte das mesmas seções comparáveis, a cobertura do comparecimento é {n(rio['cohort_coverage_attendance_1_pct'],2)}% no primeiro turno e {n(rio['cohort_coverage_attendance_2_pct'],2)}% no segundo. O saldo da coorte também muda: {n(rio['cohort_margin_1_votes'],signed=True)} → {n(rio['cohort_margin_2_votes'],signed=True)}. A coorte não substitui o total municipal e sua representatividade não foi demonstrada.")
        sub("Quanto o resultado depende do limite escolhido?")
        text("As contagens abaixo são observações territoriais brutas, incluindo unidades com comparação limitada. As colunas de 5/10/15 pp medem redução da vantagem onde Flávio liderava no primeiro turno; não são quantidades de fraude. Toda inversão é incluída, mesmo abaixo desses limites.")
        levels = {"secao":"Seção", "local":"Local", "municipio":"Município", "uf":"Estado"}
        grid(["UF / nível", "Unidades", "≥5 pp", "≥10 pp", "≥15 pp", "Elegíveis ≥10 pp"],
             [[f"{r.uf} / {levels.get(r.level,r.level)}"] + [n(getattr(r,k)) for k in ("units","loss_5pp","loss_10pp","loss_15pp","eligible_loss_10pp")] for r in investigation["sensitivity"].itertuples()], [1.3,.8,.8,.8,.8,1])
        source("investigacao_viradas.parquet. As fichas selecionadas usam os mesmos 30 pares e desvio robusto da mudança de margem; o inventário completo inclui casos limitados.")
        sub("O que as notícias afirmaram e o que esta cópia confirma")
        grid(["Fonte / data", "Afirmação", "Noticiado", "Observado / situação"],
             [[f"{r.source}\n{r.published}", r.claim, n(r.reported), f"{n(r.observed)}\n{r.status}"] for r in investigation["news"].itertuples()], [1,2.1,.85,1.45])
        text("A conferência compara valor, data e abrangência com a versão local. Um relato jornalístico não confirmado não é, por si, divergência na votação. URLs e observações completas estão em investigacao_noticias.csv.")

    if electoral_map:
        chapter("7. Localização dos padrões no mapa", "mapas")
        text("Azul indica mais votos para Flávio e vermelho mais votos para Lula no município; cinza indica empate ou ausência. A intensidade representa a margem entre os finalistas. A área de um município não representa a quantidade de eleitores.")
        for code, title in (("br","Brasil"),("rj","Rio de Janeiro"),("mg","Minas Gerais")):
            sub(title)
            figure(f"mapa_{code}.png", f"{title}: primeiro e segundo turnos lado a lado. Fontes: votação TSE e geografia IBGE; a imagem preserva a proporção original.", height=300)
        text(f"A correspondência TSE–IBGE abrange {count('map_units')} unidades municipais brasileiras. O exterior é apresentado em tabelas. Variantes de nomes foram conferidas explicitamente; Mato Grosso usa a malha oficial de 2025. Marcadores do HTML representam o município, não o endereço da seção.")
        source("mapa_correspondencia_municipios.csv e mapa_dados.json. O HTML permite filtros, zoom e consulta das quantidades por município.")

    chapter("8. Referência histórica e sensibilidade", "historico")
    text("A referência histórica pergunta com que frequência os mesmos critérios selecionam seções em cada eleição. O quadro usa somente Brasil e tem as seções elegíveis de cada ano como denominador. Não há pareamento de eleitores, candidatos ou identidades de seção entre anos.")
    if history:
        grid(["Ano", "Elegíveis", "10 pp/zero", "Frequência", "Robusto", "Frequência"],
             [[str(r["ano"]),n(r["comparaveis_ge50"]),n(r["alertas_10pp"]),n(r["frequencia_10pp_pct"],2)+"%",n(r["alertas_robustos"]),n(r["frequencia_robusta_pct"],2)+"%"] for r in history], [.6,1,1,1,1,1])
        sub("Sensibilidade do critério absoluto, incluindo passagens a zero")
        grid(["Ano", "Limite 5 pp/zero", "Limite 10 pp/zero", "Limite 15 pp/zero"],
             [[str(r["ano"])] + [n(r[f"alertas_{t}pp"]) for t in (5,10,15)] for r in history], [.5,1,1,1])
        text("Os limites são cumulativos: reduzir o corte seleciona mais seções. A elevada frequência do critério absoluto em uma eleição pode refletir a concentração de votos entre finalistas. Frequência de triagem não é frequência de irregularidade. Os BU históricos não foram incorporados à conferência documental desta execução.")
    else:
        text("Não há referência histórica processada nesta execução.")
    source("resumo.json, histórico de 2018/2022 e tabelas de indicadores por eleição. O limiar de pontos percentuais inclui a exceção de passagem a zero.")

    chapter("9. Metodologia e limites da inferência", "metodologia")
    for title, body in [
        ("Preparação e preservação", "Selecionar Presidente, normalizar UF/município TSE/zona/seção, preferir o arquivo nacional sem somar novamente as UFs, registrar versões e hashes. Duplicatas idênticas são reduzidas a uma observação; conflitos são colocados em quarentena. Ausência de uma unidade inteira não é tomada como zero."),
        ("Denominadores", "Participação do candidato usa a soma nominal 1–94, anterior a eventual tratamento jurídico. Comparecimento usa aptos; brancos e nulos usam comparecentes. Diferença absoluta é quantidade do segundo menos a do primeiro turno. Variação percentual divide pela quantidade inicial; mudança em pp compara taxas. Base zero gera ausência, não infinito."),
        ("Seleção dos 30 pares", "Priorizar seções do mesmo município, completando na UF. Usar ln(1 + aptos), comparecimento e participações dos candidatos do primeiro turno. Centralizar pela mediana da UF e dividir pelo desvio padrão da UF; escala ≤1e-12 é substituída por 1. Distância euclidiana, com a própria seção excluída. O segundo turno não seleciona pares."),
        ("Desvio robusto", "Calcular |mudança − mediana das mudanças dos pares| ÷ (1,4826 × MAD). MAD é a mediana dos desvios absolutos à mediana. MAD ≤1e-9 torna o indicador inconclusivo; não gera infinito. O máximo disponível entre indicadores é comparado ao limite exploratório >3,5. Não é p-valor nem probabilidade de fraude."),
        ("União dos critérios e unidades pequenas", "Combinar mudança ≥10 pp ou passagem a zero com o critério robusto por união. A seção precisa ser comparável e ter ≥50 comparecentes nos dois turnos. Pequenas continuam em descrições e agregações apropriadas. Pares não são controles causais e comparações múltiplas podem gerar muitos alertas."),
        ("Composição, remanejamentos e aptos", "Comparar composição e aptos, incluindo agregações declaradas. Não foi incorporada a correspondência completa do painel Capilaridade/SIG-TSE, que retornou HTTP 403 na consulta automatizada. A nota do TSE informa 39 registros duplicados de aptos por transferência temporária; não houve desconto arbitrário nas seções."),
        ("O que o método não identifica", "Os totais agregados não revelam como uma pessoa votou ou por que mudou de escolha. BU e votação por seção não são auditorias independentes do equipamento. Confirmação documental dos valores, explicação do apontamento e investigação das causas são etapas diferentes."),
    ]:
        sub(title)
        text(body)

    chapter("10. Próximos passos e rastreabilidade", "fontes")
    text("Os procedimentos abaixo são propostas ainda não executadas nesta entrega. Os limites de 5/10/15 pp já foram calculados; a proposta estatística adicional é avaliar outras quantidades de pares e a estabilidade do ranking.")
    for index, proposal in enumerate(synth.get("recommendations", []), 1):
        text(f"{index}. {proposal}")
    sub("Como conferir um lugar do relatório")
    text("1. Identifique UF, município TSE, zona e seção. 2. Abra a ficha JSON correspondente. 3. Verifique quantidades dos dois turnos, presença de registros, composição e situação de instalação. 4. Consulte os pares e a razão da triagem. 5. Confronte as provas de BU e as categorias de totalização antes de investigar causas.")
    grid(["Material", "O que permite conferir"], [
        ["sintese_analise.json", "Valores consolidados, unidades, fontes e situações interpretativas."],
        ["indicadores_secoes / alertas_secoes", "Universo, denominadores, variações, elegibilidade e os 30 pares."],
        ["conferencia_bu / reconciliacao_*", "Comparação por registro, totais, comparecimento e categorias."],
        ["investigacao_* / investigacao_fichas", "Zeros, viradas, coortes, notícias e fichas dirigidas."],
        ["fontes_utilizadas.json / data/manifest.json", "URL, obtenção, geração quando disponível e SHA256 das cópias."],
    ], [1.3,2.2])
    text(f"Foram preservados {count('sources')} arquivos eleitorais, incluindo {count('bu_files')} arquivos de BU, quando essas contagens estão disponíveis na síntese. Fontes e versões completas estão nos manifestos, não em uma lista de números sem contexto.")
    text("Referência de auditoria: https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria. As possibilidades descritas nessa referência não significam que os procedimentos foram executados neste projeto.", "Small")
    text("Licenciamento: código e documentação próprios sob MIT; dados TSE, geografia IBGE e componentes de terceiros preservam suas condições e atribuições. Consulte LICENSE e DATA_LICENSE.md na raiz do projeto.", "Small")

    if investigation and not investigation.get("stale"):
        chapter("Anexo A. Todas as unanimidades", "anexo-zeros")
        text("A identificação é UF/município TSE/zona/seção. Zerou informa o candidato sem votos no segundo turno. Válidos admite brancos/nulos; depositados significa exclusividade também no total depositado. Comparação limitada permanece sinalizada. Os dados completos e as provas estão nas fichas dirigidas.")
        rows = []
        ordered_zeros = investigation["zeros"].sort_values(
            ["zero_candidate","positive_to_zero","previous_zero_candidate_votes","uf","municipality","zone","section"],
            ascending=[False,False,False,True,True,True,True],kind="stable")
        for r in ordered_zeros.itertuples():
            rows.append([f"{r.uf}/{r.municipality}/{r.zone}/{r.section}", {13:"Lula",22:"Flávio"}.get(r.zero_candidate,str(r.zero_candidate)),
                         *[n(getattr(r,f"votes_{c}_{t}")) for t in (1,2) for c in (22,13)],
                         "Depositados" if r.unanimity_all_ballots else "Válidos", "Válida" if r.comparable else "Limitada"])
        grid(["Seção", "Zerou", "Flávio 1º", "Lula 1º", "Flávio 2º", "Lula 2º", "Exclusivos", "Unidade"], rows, [126,48,48,48,48,48,73,68])
        chapter("Anexo B. Municípios com inversão", "anexo-municipios")
        text("Votos absolutos do resultado municipal completo. As duas últimas colunas informam a cobertura do comparecimento pela coorte das mesmas seções comparáveis; não são participação dos candidatos. A coorte complementa o território, sem substituí-lo.")
        rows = [[f"{r.uf} — {r.municipality_name_1}", *[n(getattr(r,f"votes_{c}_{t}")) for t in (1,2) for c in (22,13)],
                 n(r.cohort_coverage_attendance_1_pct,1)+"%",n(r.cohort_coverage_attendance_2_pct,1)+"%"] for r in investigation["cities"].itertuples()]
        grid(["Município", "Flávio 1º", "Lula 1º", "Flávio 2º", "Lula 2º", "Coorte 1º", "Coorte 2º"], rows, [129,63,63,63,63,63,63])

    chapter("Anexo C. Indicadores consolidados", "anexo-indicadores")
    text("Este inventário mantém as contagens consolidadas disponíveis para conferência, com suas unidades. Categorias podem se sobrepor; somente as relações de soma explicitadas no texto devem ser somadas. As contagens de fichas são arquivos, e não ocorrências únicas com causa investigada.")
    for title, ids in [
        ("Universo e elegibilidade", {"observed","comparable","eligible","excluded","small","comparable_small"}),
        ("Triagem e sobreposição", {"combined","robust","cutoff5","cutoff10","cutoff15","overlap","cutoff_only","robust_only"}),
        ("Conferência e cobertura nominal", {"bu_matching","documentary_rows","noninstalled","technical_units","technical_votes","coverage_geographic_units","coverage_turn_units","coverage_candidate_rows","coverage_compatible_zero_attendance_rows"}),
        ("Investigação dirigida, fichas e fontes", set(metrics) - {"observed","comparable","eligible","excluded","small","comparable_small","combined","robust","cutoff5","cutoff10","cutoff15","overlap","cutoff_only","robust_only","bu_matching","documentary_rows","noninstalled","technical_units","technical_votes","coverage_geographic_units","coverage_turn_units","coverage_candidate_rows","coverage_compatible_zero_attendance_rows"}),
    ]:
        selected = [m for m in metrics.values() if m["id"] in ids]
        if selected:
            sub(title)
            grid(["Indicador", "Valor", "Unidade"], [[m["label"],n(m["value"]),m["unit"]] for m in selected], [1.6,.65,1.75])
    source("sintese_analise.json. Valores originais, arquivos correspondentes e situação interpretativa estão disponíveis em cada métrica.")

    chapter("Anexo D. Fichas estatísticas para revisão", "anexo-fichas")
    text(f"{n(len(priority))} fichas selecionadas por prioridade. As fichas são geradas automaticamente; os dados foram conferidos conforme a cobertura indicada, e as causas não estão estabelecidas. As fichas dirigidas e documentais são conjuntos separados, podendo se referir à mesma ocorrência.")
    text("Cada ficha compara os dois turnos e explica o indicador que mais se afastou dos pares. Os percentuais de comparecimento usam aptos; os dos candidatos usam soma nominal; brancos/nulos usam comparecentes. A coluna variação mostra diferença absoluta e, quando aplicável, mudança em pontos percentuais.")
    ordered = priority.sort_values(["is_exterior","priority"], kind="stable") if not priority.empty else priority
    for position, (_, row) in enumerate(ordered.iterrows()):
        if position % 2 == 1:
            story.append(PageBreak())
        key = f"{row.uf}-{row.municipality}-{row.zone}-{row.section}"
        name = row.get("municipality_name_1", "Município não informado")
        card = [p(f"Prioridade {n(row.get('priority'))} • {row.uf} — {name}", styles, "Subhead"),
                p(f"Município TSE {row.municipality} • Zona {row.zone} • Seção {row.section}" + (" • Exterior" if row.get("is_exterior") else ""), styles, "Small"),
                p(f"Triagem: {str(row.get('reason','critérios na ficha')).replace('>=','≥')}. Maior mudança: {n(row.get('max_change_pp'),2)} pp.", styles, "Small"),
                Spacer(1,5), table(["Indicador", "1º turno", "2º turno", "Variação"], _case_rows(row, finalists, candidate_names),
                                   [WIDTH*x for x in (.29,.23,.23,.25)], styles, compact=True),
                p(case_explanation(row, finalists, candidate_names), styles, "Case"), Spacer(1,5),
                p(f"BU: {row.get('bu_check','não informado')}. Pares: {n(row.get('peer_count'))}. A triagem não confirma irregularidade nem investiga a causa.", styles, "Small"),
                p(f"Ficha e pares: fichas/{key}.json", styles, "Small"), Spacer(1,14)]
        story.append(KeepTogether(card))

    document = AnalysisPDF(output / "relatorio.pdf", title=f"Análise presidencial {year} — resultados e interpretação", styles=styles)
    document.multiBuild(story)
    edition = {"edition": 2, "generated": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
               "pages": document.page, "sections": document.section_pages, "statistical_cases": len(priority),
               "pdf_sha256": sha256(output / "relatorio.pdf"),
               "synthesis_sha256": sha256(output / "sintese_analise.json") if (output / "sintese_analise.json").exists() else None,
               "note": "Revisão editorial do PDF. Os pacotes da release resultados-2026-v1 preservam a edição anterior."}
    write_json(output / "pdf_edicao.json", edition)
    return edition


def load_pdf_inputs(output):
    """Lê apenas os dados usados na edição, preservando HTML, fichas, síntese e gráficos."""
    output = Path(output)
    summary = json.loads((output / "resumo.json").read_text(encoding="utf-8"))
    synthesis_path = output / "sintese_analise.json"
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8")) if synthesis_path.exists() else None
    manifest_path = output / "fontes_utilizadas.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    con = duckdb.connect(config={"threads":2,"memory_limit":"1GB"})
    con.execute("SET enable_progress_bar=false")
    try:
        def query(name, sql="SELECT * FROM read_parquet(?)"):
            return con.execute(sql, [str(output / (name + ".parquet"))]).df()
        priority = query("indicadores_secoes", "SELECT * FROM read_parquet(?) WHERE statistical_alert ORDER BY priority LIMIT 100")
        candidates = query("candidatos", "SELECT * FROM read_parquet(?) WHERE turn=2 AND candidate BETWEEN 1 AND 94")
        finalists = sorted(int(c) for c in candidates.candidate.unique())
        names = dict(zip(candidates.candidate, candidates.candidate_name))
        investigation = None
        if (output / "investigacao_resumo.json").exists():
            info = json.loads((output / "investigacao_resumo.json").read_text(encoding="utf-8"))
            for name, digest in info["input_hashes"].items():
                path = output / name
                fingerprint = info.get("input_fingerprints", {}).get(name)
                if fingerprint != [path.stat().st_size,path.stat().st_mtime_ns] and sha256(path) != digest:
                    raise ValueError(f"A investigação precisa ser atualizada: {name}")
            investigation = dict(info=info, zeros=query("investigacao_zeros"),
                cities=query("investigacao_viradas", "SELECT * FROM read_parquet(?) WHERE level='municipio' AND (flip_to_13 OR flip_to_22) ORDER BY uf,municipality_name_1"),
                news=query("investigacao_noticias"), sensitivity=query("investigacao_viradas", """SELECT uf,level,count(*) units,
                    count(*) FILTER(WHERE loss_22_5pp) loss_5pp,count(*) FILTER(WHERE loss_22_10pp) loss_10pp,
                    count(*) FILTER(WHERE loss_22_15pp) loss_15pp,
                    count(*) FILTER(WHERE loss_22_10pp AND comparable AND NOT small) eligible_loss_10pp
                    FROM read_parquet(?) GROUP BY uf,level ORDER BY uf,level"""), stale=False)
        map_path = output / "mapa_dados.json"
        electoral_map = json.loads(map_path.read_text(encoding="utf-8")) if map_path.exists() else None
        return dict(output=output, summary=summary, history=summary.get("historical",[]), priority=priority,
                    finalists=finalists,candidate_names=names,manifest=manifest,synthesis=synthesis,
                    investigation=investigation,electoral_map=electoral_map,demo=summary.get("demo",False))
    finally:
        con.close()
