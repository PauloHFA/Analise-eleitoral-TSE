import html
import json
from pathlib import Path

from reportlab.platypus import Image, PageBreak, Paragraph, Spacer

from .sources import sha256


def load_map(output):
    output=Path(output)
    path=output / "mapa_dados.json"
    if not path.exists():
        return None
    payload=json.loads(path.read_text(encoding="utf-8"))
    summary=payload["summary"]
    if sha256(output / "indicadores_municipio.parquet")!=summary["results_sha256"]:
        return None
    rows=payload["features"]
    shapes=[]
    for r in rows:
        code=html.escape(r["ibge_code"],quote=True)
        shapes.append(f"<path data-code='{code}' d='{r['path']}' fill='#c5cbd3' fill-rule='evenodd' vector-effect='non-scaling-stroke'><title>{html.escape(r['municipality_name_1'])}</title></path>")
    for r in rows:
        if r["zero_sections"]:
            x,y,w,h=r["bounds"]
            shapes.append(f"<circle data-code='{r['ibge_code']}' cx='{x+w/2:.4f}' cy='{y+h/2:.4f}' r='.15' fill='#111827' stroke='#f5bf36' stroke-width='1.1' vector-effect='non-scaling-stroke' style='display:none'><title>{html.escape(r['municipality_name_1'])}: {r['zero_sections']} seções</title></circle>")
    options="".join(f"<option value='{s}'>{s}</option>" for s in sorted({r["uf"] for r in rows}))
    lite=dict(summary=summary,features=[{k:v for k,v in r.items() if k!='path'} for r in rows])
    data=json.dumps(lite,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
    script=Path(__file__).with_name("map_ui.js").read_text(encoding="utf-8")
    excluded=summary["electoral_municipalities"]-summary["mapped"]
    fragment=f"""<section id='mapa-eleitoral'><h2>Mapa eleitoral — azul: Flávio · vermelho: Lula</h2>
    <p>Resultados por município nos dois turnos. Azul onde Flávio teve mais votos; vermelho onde Lula teve mais votos; cinza em empate ou ausência. Clique no território para consultar as quantidades e os percentuais.</p>
    <div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px'>
    <label>Turno <select id='map-turn'><option value='1'>1º turno</option><option value='2' selected>2º turno</option></select></label>
    <label>Visualização <select id='map-mode'><option value='winner'>Candidato com mais votos</option><option value='22'>Quantidade de votos — Flávio</option><option value='13'>Quantidade de votos — Lula</option></select></label>
    <label>UF <select id='map-uf'><option value='BR'>Brasil</option>{options}</select></label>
    <label><input id='map-flips' type='checkbox'> Somente municípios que mudaram de vencedor</label>
    <label><input id='map-zeros' type='checkbox'> Marcar municípios com passagens a zero</label></div>
    <p><span style='color:#165dcc;font-weight:bold'>■ Flávio</span> · <span style='color:#cf2639;font-weight:bold'>■ Lula</span> · <span style='color:#89939f'>■ empate/sem dados</span></p>
    <p id='map-scale'></p><p id='map-count' aria-live='polite'></p>
    <div><button id='map-go-BR' type='button'>Brasil</button> <button id='map-go-RJ' type='button'>Rio de Janeiro</button> <button id='map-go-MG' type='button'>Minas Gerais</button> <button id='map-zoom-in' type='button' aria-label='Aproximar mapa'>+</button> <button id='map-zoom-out' type='button' aria-label='Afastar mapa'>−</button> <button id='map-reset' type='button'>Restaurar enquadramento</button></div>
    <div style='display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start'><svg id='map-svg' viewBox='-74 -7 47 43' role='img' aria-label='Mapa municipal do Brasil com votação presidencial' style='flex:1 1 620px;width:100%;height:620px;background:#edf4f8;touch-action:none;cursor:grab'>{''.join(shapes)}</svg><aside id='map-info' aria-live='polite' style='flex:1 1 230px;max-width:340px;padding:12px;background:#f3f6f8'></aside></div>
    <p>A área do município não representa seu número de eleitores. O contorno dourado mostra mudança de vencedor, sem concluir irregularidade. Marcadores de passagens a zero representam o município, não a localização exata da seção.</p>
    <noscript><p>Ative JavaScript para interagir ou consulte o mapa estático:</p><img src='graficos/mapa_br.png' alt='Mapas estáticos com azul para Flávio e vermelho para Lula nos dois turnos' style='max-width:100%'></noscript>
    <p>Cobertura cartográfica: {summary['mapped']} de {summary['electoral_municipalities']} unidades municipais brasileiras; {excluded} sem polígono/vínculo nesta malha. Exterior apresentado nas tabelas. Malha simplificada e cadastro: <a href='https://servicodados.ibge.gov.br/api/docs/malhas?versao=3'>IBGE</a>; votos: TSE. O vínculo TSE–IBGE foi conferido por UF e nome, preservando os códigos distintos.</p>
    <p><a href='mapa_eleitoral.html'>Abrir mapa em página própria</a> · <a href='mapa_correspondencia_municipios.csv'>Correspondência e votos por município</a> · <a href='#investigacao-dirigida'>Consultar investigação das passagens a zero e viradas</a></p>
    <script id='map-data' type='application/json'>{data}</script><script>{script}</script></section>"""
    standalone="<!doctype html><html lang='pt-BR'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Mapa eleitoral 2026</title><style>body{font:16px/1.5 system-ui;background:#f0f4f7;color:#172c3d;margin:0}main{max-width:1400px;margin:auto;padding:24px;background:white}button,select{padding:7px}a{color:#165e83}</style><main><h1>Mapa presidencial 2026</h1><p><a href='relatorio.html'>Abrir o relatório completo com as fichas da investigação</a></p>"+fragment+"</main></html>"
    standalone=standalone.replace("href='#investigacao-dirigida'","href='relatorio.html#investigacao-dirigida'")
    (output / "mapa_eleitoral.html").write_text(standalone,encoding="utf-8")
    return dict(html=fragment,output=output,summary=summary)


def pdf_map(bundle,styles):
    if not bundle:
        return []
    story=[PageBreak(),Paragraph("Mapa eleitoral — azul: Flávio; vermelho: Lula",styles["Heading1"]),
        Paragraph("Cores indicam o candidato com mais votos em cada município; tons mais fortes indicam maior margem entre os finalistas. A área geográfica não representa a quantidade de eleitores. As imagens comparam primeiro e segundo turnos. A versão HTML tem filtros, aproximação e consulta de votos ao clicar.",styles["BodyText"])]
    for code in ("br","rj","mg"):
        story += [Spacer(1,8),Image(str(bundle["output"] / "graficos" / f"mapa_{code}.png"),width=440,height=240)]
    story += [Paragraph(f"Fonte: votos TSE; geografia IBGE. Cobertura: {bundle['summary']['mapped']} de {bundle['summary']['electoral_municipalities']} unidades brasileiras. Vínculo e ausências em mapa_correspondencia_municipios.csv. Exterior nas tabelas.",styles["BodyText"])]
    return story
