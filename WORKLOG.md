# Execução entregue — 3 de novembro de 2026

O pipeline foi implementado e executado com fontes oficiais de 2018, 2022 e 2026. Os 56 arquivos de boletins de 2026 foram obtidos e integrados com hashes validados. O estado consolidado está em `outputs/2026/estado_execucao.json`; os arquivos utilizados e suas versões estão em `fontes_utilizadas.json` e `data/manifest.json`.

Foram gerados HTML, PDF, gráficos, tabelas CSV/Parquet, dicionário, 100 fichas estatísticas prioritárias e 41 fichas de revisão documental ou aritmética. O exterior está identificado separadamente. Os dados simulados ficam exclusivamente em `outputs/demo`.

## Resultados de 2026

- 499.248 unidades observadas: 497.897 no Brasil e 1.351 no exterior.
- 429.166 comparáveis; 70.082 sem comparação válida pelos critérios documentados.
- 63.809 unidades na triagem combinada; esse número inclui limites absolutos e desvios robustos.
- 5.731.614 registros de votação concordantes entre boletins e resultados por seção.
- 2.148 diferenças nominais, somando 5.246 votos do candidato 28, correspondem aritmeticamente aos nulos técnicos nas mesmas zonas. Brancos e totais coincidem; a razão jurídica ou operacional não foi estabelecida.
- Cobertura nominal: 42 combinações UF/município/zona, 83 combinações por turno e 576 linhas por candidato. Todas têm comparecimento zero publicado nas duas fontes e votos oficiais zero; a ausência nominal é compatível com esse contexto. Os apontamentos brutos permanecem preservados.
- 82 apontamentos aritméticos brutos, correspondentes a 41 seções no exterior. A revisão verificou que todas estão declaradas não instaladas, sem votação e com comparecimento e abstenções zerados. O alerta de soma foi explicado como regra aplicada fora de contexto. Os originais estão preservados e a avaliação está em `revisao_documental` e nas fichas. O motivo da não instalação e o destino dos eleitores não foram estabelecidos.

## Validação

A validação nacional confere links, JSON, PDF com fonte incorporada, fichas na prioridade correta e contagens CSV/Parquet dos três anos; também verifica elegibilidade dos alertas, escores finitos, sensibilidade e composição das agregações. A validação dirigida confere os hashes das fontes e das 100 fichas originais, as provas de BU e a seleção de 50 seções por UF, e executa os filtros/paginação JavaScript offline com Node. O mapa tem validação de cores dos dois turnos, controles, reconciliação dos votos e orientação norte–sul dos mapas estáticos. As contagens atuais de testes, páginas, links e registros estão no README gerado e nos registros finais em `outputs/logs/`.

## Mapa municipal

Mapa interativo incorporado ao início do relatório e gerado também em `mapa_eleitoral.html`, com azul para Flávio e vermelho para Lula, alternância de turno, quantidades de votos, filtros de UF/viradas, marcadores municipais de passagens a zero, zoom e consulta dos municípios. O PDF inclui os dois turnos do Brasil, RJ e MG. O vínculo cobre 5.571 de 5.571 unidades, sem omissão ou duplicação dos votos dos finalistas. Treze variantes de nome foram conferidas explicitamente e Mato Grosso usa a malha oficial de 2025 para representar Boa Esperança do Norte e seus municípios de origem. As fontes e hashes da geografia estão preservados em `data/geografia`.

## Investigação de zeros e viradas

O comando `eleicoes investigar --output outputs/2026 --ufs RJ MG` foi implementado e executado sobre os Parquets locais. Foram geradas 297 fichas dirigidas: 110 unanimidades nacionais no segundo turno, 85 municípios com inversão em RJ/MG, 100 seções priorizadas (50 por UF) e os dois estados. As fichas originais foram preservadas por hash.

As contagens coincidiram com a consulta preliminar: 106 seções sem votos para Flávio no segundo turno, das quais 56 tinham votos para ele no primeiro e 50 já estavam zeradas. As 56 somavam 118 votos anteriores, com máximo de 16 por seção; ele não liderava nenhuma delas. Dessas, 44 são comparáveis e 12 têm limitação territorial. Há também quatro seções com Lula zerado. A unanimidade de todos os votos depositados ocorreu em 29 das 106 seções de Lula.

As inversões de Flávio para Lula ocorreram em nove municípios do RJ e 76 de MG. O inventário inclui todos os registros das UFs por seção, local, município e estado, as sensibilidades de 5/10/15 pp e as coortes municipais com cobertura explícita. Na capital fluminense, a coorte cobre aproximadamente 80% do comparecimento e também apresenta a inversão. Uma notícia atribui à cidade margem de aproximadamente 644 mil para Lula; a versão analisada indica 113.193, registrando-se o relato como não confirmado, sem confundir isso com erro nos votos.

Tabelas, fontes, provas e metadados estão nos arquivos `investigacao_*`; o HTML tem filtros locais paginados, e o PDF inclui as listas completas de unanimidades e municípios com inversão. As causas das mudanças individuais de voto não são inferidas.

## Limitações registradas

A exportação completa do painel Capilaridade/SIG-TSE não foi incorporada porque a consulta retornou HTTP 403. As gerações dos arquivos por seção e da totalização diferem; a reconciliação integral com uma mesma versão oficial e a razão das reclassificações dependem de esclarecimento das fontes. As pendências permanecem rastreáveis, e nenhum alerta foi classificado automaticamente como fraude ou divergência persistente confirmada.

Para reproduzir, usar os comandos do `README.md`. Para regenerar apenas os relatórios: `python scripts/gerar_relatorio.py outputs/2026`. Para verificar a entrega: `python scripts/validar_entrega.py outputs/2026`.

## Revisão de documentação e síntese comum — 03/11/2026

- Criado `sintese_analise.json`, derivado dos artefatos locais, com valores, unidades, fontes, situações interpretativas, cobertura, sensibilidade, notícias e propostas não executadas.
- README reorganizado em nove etapas, com perguntas, fontes, métodos, resultados, interpretação, limitações e links; modelo em `docs/README.template.md` e gerador em `scripts/gerar_documentacao.py`.
- Resumo executivo e matriz de cobertura comuns ao HTML/PDF, antes do mapa. Comparabilidade territorial distinguida de elegibilidade estatística; união dos critérios e sobreposição explicitadas.
- Corrigida a leitura de 42/83/576. Os apontamentos originais de cobertura não foram apagados ou preenchidos com zeros artificiais.
- Confirmação de persistência explicitamente não investigada. O zero legado de `resumo.json` foi mantido por compatibilidade, sem interpretação de ausência de irregularidades.
- Registrada a distinção entre fichas automáticas, contagens conferidas e causas investigadas; as quantidades de arquivos não representam ocorrências únicas.
- Recomendações registradas como não executadas: versões e causas jurídicas, remanejamentos/representatividade, RDV/assinaturas/logs/BU físico e estabilidade ao variar pares. Sensibilidade de 5/10/15 pp já realizada.
- Não houve nova ingestão nacional. Inventário SHA256 anterior à regeneração registrado para 578 artefatos, incluindo tabelas, fichas e mapas, em `outputs/logs/preservacao-documentacao.json`.
- Novos testes para unidades de cobertura, zeros publicados versus ausências, elegibilidade e persistência, além da atualização conjunta dos valores em README/HTML. Validador `scripts/validar_sintese.py` confere fontes, relações entre contagens, números nos documentos, texto do PDF e links do README. Resultados finais nos logs da revisão.
- Validação final desta revisão: 70 testes aprovados; PDF de 119 páginas; 297 referências de links/imagens inventariadas no HTML, com destinos locais conferidos; 129 links locais do README conferidos; 41 métricas coerentes entre fontes, síntese e documentos. Filtros: 35 combinações; mapa: 11.150 verificações. Os 578 artefatos do inventário foram preservados por SHA256. Não houve nova ingestão nacional.

## Preparação para publicação no GitHub

O repositório `PauloHFA/Analise-eleitoral-TSE` versiona código, documentação e os artefatos de leitura: relatórios, mapas, fichas, sínteses e tabelas pequenas. Os CSV/Parquet completos são distribuídos pela release `resultados-2026-v1`, em três pacotes: resultados de 2026 e referências de 2018/2022. Os pacotes contêm 596 arquivos, incluindo a geografia utilizada; as cópias eleitorais originais e o banco DuckDB permanecem fora dessa distribuição.

Os pacotes passaram por conferência CRC; o manifesto em `docs/resultados-publicados.json` registra tamanho e SHA256 dos pacotes e de cada arquivo. Atributos Git preservam os bytes das cópias e suas quebras de linha. O commit inclui a atribuição `Co-authored-by: Codex <noreply@openai.com>`, conforme solicitado.

## Licenciamento — 03/11/2026

Adicionada licença MIT para código e documentação de autoria própria, com copyright de PauloHFA. `DATA_LICENSE.md` registra o escopo dos materiais do TSE, do IBGE e de outros terceiros, preservando suas condições e atribuições. README e modelo de geração incluem a seção de licença. O pacote Python declara o identificador SPDX MIT e inclui os dois avisos de licença em sua distribuição, usando os metadados suportados pelo setuptools a partir da versão 77. Os artefatos analíticos e os pacotes publicados permanecem com os mesmos bytes e hashes.

## Revisão editorial do PDF — 03/11/2026

O PDF foi reorganizado em perguntas, evidências, interpretação, metodologia e anexos. Foram substituídas as listas de campos e os blocos de JSON por tabelas com unidades e explicações, acrescentados sumário clicável, marcadores e numeração, preservadas as proporções das imagens e compactadas as fichas em comparações entre os dois turnos com explicação do indicador de maior afastamento. A edição mantém os inventários completos e as 100 fichas estatísticas, sem alteração das bases analíticas.

`scripts/gerar_pdf.py` usa apenas os artefatos existentes e não regrava HTML, síntese, tabelas, gráficos ou fichas. A mesma apresentação é utilizada no processamento normal. `pdf_edicao.json` registra páginas, posições dos capítulos e hashes. `scripts/validar_pdf.py` verifica conteúdo e geometria com PyMuPDF; a inspeção visual usa PNGs renderizados. A documentação pode ser atualizada com `--reuse-synthesis`, preservando a cópia da síntese.

Os pacotes `resultados-2026-v1` permanecem como snapshot original, incluindo seu PDF anterior. A edição explicativa é disponibilizada separadamente em `pdf-revisado-v2`. A validação dos pacotes confere seus conteúdos independentemente de revisões editoriais na pasta de trabalho; `--workspace` permite comparar também o snapshot com essa pasta.

Validação da edição explicativa: 79 páginas, sendo 17 antes dos anexos; 15 marcadores; 100 fichas estatísticas; 41 métricas consolidadas; seis imagens com proporções preservadas. Os 76 testes passaram e a demonstração completa também gerou HTML/PDF. Houve inspeção visual de páginas renderizadas e conferência automatizada de sumário, texto, margens e contagens. Os 578 artefatos do inventário de preservação mantiveram seus hashes, e os três pacotes originais foram novamente conferidos por conteúdo e SHA256.

## Primeira rodada incremental — 03/11/2026

O roteiro das cinco frentes foi publicado em `e4b7222`, seguido das implementações de estabilidade (`6ff5db4`) e cobertura (`fa0392a`). As duas foram executadas sobre os arquivos locais, em subpastas separadas, com conferência de hashes de entrada e validação independente.

A referência de 30 pares foi reproduzida nas 28 UFs. O universo comum às configurações de 15/30/50 contém 428.521 seções; as 50 elegíveis do exterior não dispõem de 50 outros pares. Nesse universo, as triagens contêm 83.983, 63.796 e 59.045 seções. Os primeiros 100 de 15/30 compartilham oito casos; 30/50 compartilham 18. Isso expressa sensibilidade da ordem, não eliminação automática dos demais alertas.

A cobertura fecha 499.248 unidades: 428.571 elegíveis, 595 comparáveis pequenas e 70.082 não comparáveis. Foram calculados perfis do primeiro turno, cobertura municipal/UF e qualidade de cada medida, sem assumir seleção aleatória. Os detalhes e limites constam em `docs/RESULTADOS_INCREMENTAIS.md`.

Os CSV/Parquet novos foram lidos com esquema e aspas explícitos, preservando a distinção entre strings vazias e ausências, e comparados por contagem e dois checksums agregados de linhas. Pares, universo comum, ranking e fechamento dos grupos também foram auditados. As frentes 3–5 continuam pendentes conforme o roteiro; nenhuma explicação causal ou auditoria de RDV foi anunciada como realizada.

A rodada terminou com 92 testes aprovados. A validação geral passou incluindo as tabelas novas e manteve o PDF de 79 páginas. A correção da leitura estrita e os validadores foram publicados em `7428437`. Os pacotes incrementais preservam os arquivos por SHA256 e são distribuídos separadamente das releases anteriores.

## Dossiê de categorias — implementação local

Implementado o primeiro passo da frente 3, solicitado pelo usuário: comando `eleicoes dossie`, inventário por município/zona/turno e por candidato, leitura do detalhe oficial original, datas de geração, partições, hashes e HTML com filtros locais. A correspondência aritmética é recalculada por unidade e confrontada com o detalhe original. A classificação publicada permanece preservada. Compensações entre candidatos, dados ausentes e partições duplicadas não encerram apontamentos silenciosamente.

Foram adicionados 12 testes controlados e o validador independente `scripts/validar_dossie.py`, com comparação tipada completa de CSV/Parquet por `EXCEPT ALL` nos dois sentidos. A execução nacional é registrada em incremento posterior. A explicação documental das causas e a persistência não são investigadas pelo comando; não houve pesquisa externa ou contato com terceiros.
