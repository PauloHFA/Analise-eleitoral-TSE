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

## Dossiê de categorias — execução nacional e conferência

A implementação inicial foi registrada em `efb3522`. A execução real identificou uma colisão entre a diferença de soma de votos/comparecimento e a diferença entre detalhes de comparecentes; os dois campos foram separados, documentados e incluídos no cenário de teste em `e253f71`. As execuções intermediárias foram preservadas fora das saídas publicadas. O HTML passou a identificar explicitamente os zeros esparsos já imputados na referência.

O dossiê fecha 12.584 unidades município/zona/turno e preserva 90.236 linhas nominais. Detalha 2.231 unidades por turno, em 2.190 localizações. Reproduz a correspondência de 5.246 votos com nulos técnicos em 2.148 unidades do primeiro turno, todas nas linhas nominais do candidato 28. O valor oficial zero nessas linhas é implícito na reconciliação anterior, não uma nova imputação ou um zero necessariamente presente em uma linha original. A compensação por categorias foi conferida no detalhe oficial original, sem explicação jurídica/operacional atribuída.

As lacunas nominais com comparecimento zero permanecem separadas em 42 unidades geográficas, 83 unidades por turno e 576 linhas por candidato. As cinco tabelas CSV/Parquet passaram por igualdade tipada completa nos dois sentidos. Houve conferência de todas as âncoras, hashes dos originais/entradas e preservação dos 578 artefatos do inventário anterior. A suíte final tem 104 testes aprovados. A pesquisa documental, causa e persistência continuam pendentes.

## Pesquisa documental — norma, cadastro e eficácia temporal

Foram consultados o guia oficial de destinação de votos de 2026, a Resolução-TSE 23.677/2021 compilada, o registro individual de candidatura 280002554479 e o painel de candidaturas. O guia identifica a categoria de nulos técnicos e sua presença na urna/BU; o art. 17 rege a totalização majoritária. O cadastro presidencial de Leonardo Alves de Araujo, número 28, registra Renúncia. O vínculo usa ID/cargo/ano/eleição para distinguir o registro de vice e outra candidatura de número 28.

A notícia da Agência Brasil de 30/09/2026 oferece contexto temporal e permanece classificada como jornalística. A atualização cadastral de 05/10/2026 não foi tomada como data da renúncia. A tentativa de consulta do processo 0602033-94.2026.6.00.0000 no PJe encontrou indisponibilidade e depois CAPTCHA; foi interrompida sem contorno. Documentos de outros anos foram excluídos. Nenhum ato individual foi obtido. A conclusão é compatibilidade com a renúncia, com aplicação temporal e causa jurídica individual ainda não confirmadas.

Seis capturas integrais Firecrawl foram preservadas localmente fora do Git. Os hashes identificam as extrações, não os bytes originais do servidor; o download binário do guia retornou HTTP 403. O catálogo público preserva metadados e a resposta individual é reduzida a campos eleitorais, sem dados pessoais adicionais nem URLs de sessão. Não houve nova ingestão nacional ou contato com terceiros. O relatório de pesquisa, separado da referência, tem HTML/PDF de três páginas e tabela das 2.148 unidades.

A suíte final tem 113 testes aprovados. A validação confirmou as seis capturas, 13 links, igualdade CSV/Parquet tipada completa e preservação das entradas. Houve inspeção do conteúdo, margens e marcadores do PDF e de páginas renderizadas. A confirmação de eficácia do ato e de persistência permanece pendente.

## Etapa 4 — inventário e mapas nacionais

Foram implementados os incrementos de inventário (`f192ab6`), taxas/coortes (`d41deb6`) e mapas/relatórios (`cae77ef`), com comandos separados e saídas em `outputs/2026/nacional/`. A expansão reutiliza os dados e os 30 pares publicados, com cálculo vetorizado da margem, sem nova seleção de pares ou ingestão nacional. Os critérios permanecem simétricos e a triagem original está preservada em campo próprio.

O inventário fecha 499.248 seções, 94.343 locais, 5.757 unidades municipais e 28 UFs. O resultado municipal completo registra 211 inversões para Lula e uma para Flávio no Brasil; no exterior, sete e três. As contagens de RJ/MG foram reproduzidas. Setenta e duas das 211 inversões brasileiras para Lula atendem à comparabilidade territorial estrita; os demais casos e as coberturas das coortes permanecem identificados. Uirapuru/GO é a inversão para Flávio.

As taxas usam numerador/denominador de elegíveis, separados de área, votos e eleitores. No limite operacional de 30 elegíveis/80% de cobertura, 2.397 unidades brasileiras recebem cor de taxa e 3.174 ficam identificadas sem cor, mantendo os valores brutos. A cartografia de 5.571 unidades foi reutilizada por código e hash. A interface distingue liderança, mudança relativa e taxa, com escalas fixas, filtros, consulta dos turnos/coortes e teclado. A lista de revisão contém 1.356 prioridades, sem classificação causal automática ou substituição das fichas anteriores.

A validação completa conferiu 12 pares CSV/Parquet tipados, somatórios disponíveis, cobertura, coortes, geografia, reprodução de 84 escores e 33.467 condições da interface. O PDF tem cinco páginas e dez marcadores e passou por inspeção de conteúdo, margens e páginas renderizadas. Os modos de margem e taxa foram visualizados no Chrome headless; a tentativa opcional com Edge não produziu captura e não foi usada como evidência de inspeção. Os 135 testes passaram e os 578 artefatos anteriores mantiveram seus hashes. A frente 3 continua com pendência de eficácia do ato e a frente 5 ainda não foi executada.


## Etapa 5 — seleção, documentos e primeira conferência amostral

Seleção congelada em `e1ed429`, antes dos documentos dos casos: 12 prioridades e 12 controles únicos, cinco regiões e exterior, nos dois turnos. O exterior usa as duas configurações disponíveis, sem chamar a frequência de 3/3. O pareamento dos controles usa exclusivamente características do primeiro turno. A seleção dirigida não permite inferência de frequência nacional de irregularidade.

Em `0ba50d7`, foram obtidos 240 documentos oficiais (48 de cada tipo: RDV, BU binário, imagem, assinatura e log), por leitura parcial de 22 ZIPs. Foram preservados ETags fortes, intervalos, hashes dos intervalos, CRC32/SHA256/tamanho dos membros e catálogo. Não se atribuiu hash ao ZIP completo. Os originais ficam fora do Git; o pacote público contém resultados agregados e inventário para reprodução, sem listar votos individuais ou conteúdo dos logs.

A recontagem presidencial concordou em 265 linhas por candidato/categoria nas 48 unidades seção/turno entre RDV, BU binário, texto da imagem e os CSV preservados de resultados e BU. Comparecimento e aptos coincidiram. Brasil tem 40 unidades seção/turno e exterior oito, repartidas igualmente entre prioritários e controles. Não foram inferidas escolhas individuais ou explicação causal para as mudanças.

O pacote de esquemas ASN.1 foi obtido de espelho de terceiros, fixado por SHA256; a tentativa direta no TSE retornou HTTP 403. Nenhum código do espelho foi executado. Os 48 arquivos de assinatura são incompatíveis com o esquema consultado: validação criptográfica e cadeia permanecem não realizadas. Logs foram preservados, sem análise de eventos; nenhum BU independente em papel foi obtido. A etapa 5 completa continua aberta, assim como a eficácia temporal do ato na frente 3.

O relatório complementar tem HTML com filtros por UF/grupo, 24 seções e PDF de nove páginas/dez marcadores, com conclusão, método, casos e pendências. Validação: 151 testes aprovados (181 avisos de depreciação da dependência ASN.1), seis pares CSV/Parquet completos, 240 originais por hash/tamanho/CRC32, 900 condições dos filtros, links locais e margens/conteúdo do PDF. HTML e páginas do PDF foram inspecionados renderizados. Os 578 artefatos anteriores mantiveram seus hashes. Não houve nova ingestão nacional nem contato com terceiros. Método e comandos em docs/AUDITORIA.md.


## Incremento de assinaturas — layout observado e ECDSA parcial

Leitor e verificadores implementados em `38f4302`. A estrutura observada nos 48 VSC traz SW/HW antes do modelo/algoritmo e tags opcionais diferentes do esquema consultado. Foi criado um esquema local nomeado, sem atribuição de homologação oficial, com consumo integral e recodificação idêntica, versão explícita, nomes seguros/únicos e vínculo exato com a seção/turno. Os esquemas e resultados anteriores permanecem preservados.

Conferiram 384 SHA512 de 192 documentos nas duas listas SW/HW e 96 hashes internos. Não houve diferença entre os hashes declarados em SW/HW. As listas totalizam 1.008 entradas; 624 são documentos não obtidos no escopo e não foram tratados como erros de hash. Não foram baixados arquivos adicionais de comparecimento ou biometria.

Conferiram 70 verificações ECDSA P-521 com a chave embutida: 14 listas de hardware e 56 documentos. As 34 unidades Ed521 e todas as listas SW/CEPESC permanecem sem verificação criptográfica. Foram extraídas 48 ocorrências de certificados de ponta; a validade é compatível com a data declarada em todos os fusos UTC−12 a UTC+14. A data não é carimbo de tempo autenticado. Não foram validadas cadeia, assinaturas dos emissores ou revogação; não se inferiu confiança institucional da concordância criptográfica.

Os resultados estão separados em auditoria/assinaturas, com quatro pares CSV/Parquet, esquema local, HTML e PDF de cinco páginas/cinco marcadores. A suíte tem 160 testes aprovados, incluindo nove novos com chaves/arquivos alterados, truncamento, campos extras, nomes inseguros e distinção entre algoritmo não verificado e assinatura inválida. A validação confere multiconjuntos tipados integrais, 48 unidades, escopo, 14 reconferências ECDSA, nove links locais e margens/conteúdo do PDF. HTML e páginas renderizadas foram inspecionados. Os 578 artefatos anteriores e os manifestos da primeira conferência mantiveram seus hashes. Há 362 avisos de depreciação da dependência ASN.1, sem falhas. A confirmação oficial do layout, Ed521, cadeia/revogação, eventos dos logs, BU independente e eficácia temporal do ato de nulos técnicos permanecem abertos.


## Incremento Ed521 — perfil técnico e referência independente

Implementação em `b23a26f`, mantendo a etapa ECDSA anterior sem habilitar o algoritmo por padrão. A etapa nova `auditoria --etapa ed521` usa Ed521 puro no perfil técnico do DOC-ICP-01.01 v4.2, página 12. O PDF foi obtido diretamente do ITI e preservado por hash, sem afirmação sobre vigência normativa atual. A produção verifica somente dados públicos, com codificação canônica, S < L, chave não neutra e A/R no subgrupo primo. Não gera chaves ou assinaturas, não faz buscas por combinações de hash e não depende de Node/Noble em produção.

Os 12 vetores foram gerados com o genérico Noble 2.4.0 configurado para o perfil, com script e lockfile versionados: não são vetores oficiais nem homologação do verificador. Python e Noble concordaram em 170 assinaturas reais e 170 mensagens alteradas. Um caso sintético com torção foi documentado separadamente: a equação cofatada da referência aceita e a política estrita rejeita, conforme esperado; o caso não pertence à amostra.

Conferiram 170 verificações Ed521 com chaves embutidas (34 listas e 136 documentos), além das 70 ECDSA reconferidas. Os 384 hashes dos documentos e 96 internos continuaram concordantes. Há 240 verificações de assinatura de hardware, não 240 urnas. CEPESC, cadeia, assinatura dos emissores e revogação permanecem não verificados; a data do VSC não é carimbo de tempo autenticado.

Foram gerados quatro pares CSV/Parquet em auditoria/ed521 e um par independente em ed521_referencia, com sínteses e manifestos separados. O relatório HTML e PDF de cinco páginas/cinco marcadores foi validado e inspecionado renderizado. A suíte tem 176 testes aprovados, incluindo 16 novos Ed521, com 362 avisos de depreciação da dependência ASN.1. A validação confere os cinco pares tipados integrais, escopo/contagens, dez links locais, o PDF e o hash do documento técnico. Os cinco manifestos amostrais anteriores e seus arquivos, além dos 578 artefatos originais, mantiveram seus hashes. Não houve nova ingestão eleitoral. Próximo incremento: cadeia/revogação com âncoras oficiais, mantendo CEPESC, layout oficial, eventos dos logs, BU independente e eficácia temporal do ato da frente 3 como pendências distintas.


## Certificados — vínculo, vigência e revogação indeterminada

Leitores e execução implementados em `ff14eb6`. Três intermediários candidatos foram extraídos como dados do pacote técnico já preservado, sem executar seu código nem promover candidatos a âncoras. Foram feitas 21 tentativas públicas (13 HTTP 403 e oito erros TLS), incluindo alternativas HTTPS dos pontos de LCR. TLS não foi desativado; nenhuma LCR, emissor ou raiz utilizável foi obtido. A cópia de hashes HOLOCRON em terceiros foi tratada somente como referência secundária, não como publicação oficial autenticada.

As 48 assinaturas de certificados de ponta conferem com as chaves candidatas; são 25 certificados distintos na amostra de 24 seções/dois turnos. Foram conferidos nome do emissor, AKI/SKI, indicação de CA, keyCertSign e assinatura sobre os bytes TBS, sem confundir com o wrapper do VSC. Em 34 ocorrências o período do intermediário é compatível; 14 usam o candidato disponível AC URNA, cujo certificado venceu em 18/07/2026, antes da data declarada. A causa permanece não esclarecida; não foi presumida renovação ou irregularidade nos votos. Os 48 certificados de ponta conservam sua verificação temporal separada.

O leitor de LCR completa/direta foi implementado com classificação indeterminada para ausência, período vencido, assinatura errada, escopo delta/indireto não suportado e extensões críticas não tratadas. Foi testado apenas com dados sintéticos; não há conclusão de revogação da amostra. A rotina não implementa validação integral RFC 5280, políticas, nomes ou toda a cadeia. OCSP não foi implementado; não há AIA nas 48 ocorrências. O caminho até âncora permanece incompleto em todas as unidades.

Resultados separados em auditoria/cadeia, com quatro pares CSV/Parquet, inventário de 48 vínculos, 14 pendências e 21 tentativas. PDF de seis páginas/seis marcadores e HTML foram validados e inspecionados renderizados. A suíte tem 185 testes aprovados, incluindo nove novos de vínculo/LCR, com 362 avisos de depreciação da dependência ASN.1. A validação reconferiu as 48 assinaturas, tabelas tipadas integrais, nove links locais, conteúdo/margens do PDF, sete manifestos amostrais anteriores e preservação dos 578 artefatos originais. Método e matriz de implementação/fontes em docs/CADEIA_CERTIFICADOS.md. Próxima frente executável com dados locais: eventos dos logs; confiança completa depende também de documentação oficial e implementação integral de caminho. Nenhum contato externo foi enviado.


## Caminho completo — backend PKIX e política de revogação

Implementação em `f5364fd`: pyhanko-certvalidator 0.33.0, adaptador Ed521 sobre TBS, normalização ECDSA P-521 e seleção explícita de âncoras por manifesto/fingerprint. A lista TLS do sistema não é carregada, intermediários não são promovidos a raízes e a rede do backend permanece desativada. A estrutura do caminho é conferida separadamente da passagem com LCR obrigatória para ponta e intermediários; falta de evidência não gera aprovação. Não se declara homologação TSE nem conformidade exaustiva com toda a RFC 5280.

A captura complementar registra 11 novas consultas HTTP 403 com TLS verificado, sem objeto utilizável. As 21 tentativas anteriores e as cópias dos três intermediários candidatos permanecem preservadas. Nenhuma raiz ICP-Brasil genérica foi adotada como substituta. As rotas candidatas não são prova de publicação dos arquivos; nenhum contato externo foi enviado.

A execução local cobriu 24 seções/48 unidades seção/turno e 144 hipóteses de horário. São três instantes por unidade, não prova de tempo autenticado ou continuidade de revogação. Todas as tentativas de caminho permanecem inconclusivas por falta de âncora; a passagem estrita de revogação não foi alcançada. Zero âncoras e zero LCR foram fornecidas. Os 14 apontamentos anteriores de vigência de AC URNA continuam sem causa esclarecida.

A suíte completa tem 194 testes aprovados, com 543 avisos de depreciação ASN.1. Os nove testes novos incluem caminhos completos ECDSA e Ed521, LCR Ed521, revogação, vencimento, assinatura errada, pathLen, NameConstraints, extensão crítica desconhecida, falta de âncora e prevenção de confiança implícita. A fixture é pública e sintética, gerada com Noble fixado por lockfile, sem caráter oficial; seu sucesso não é atribuído às urnas. O gerador anterior de referência foi preservado.

Saídas próprias em `auditoria/caminho_pkix/`: três pares CSV/Parquet com multiconjuntos tipados integrais conferidos, política executada, síntese e manifestos, HTML e PDF de cinco páginas/cinco marcadores. Oito links locais, conteúdo/margens e a renderização do HTML/três páginas do PDF foram conferidos. Oito manifestos amostrais anteriores e os 578 artefatos originais mantiveram seus hashes; README foi gerado reutilizando a síntese nacional. As versões anteriores não foram substituídas.

Método, comandos, pesquisa e pendências em `docs/CAMINHO_PKIX.md`. O item 1 continua aberto quanto à evidência real: emissores/raízes com proveniência oficial, seleção de confiança documentada, LCR históricas adequadas e confronto com o perfil TSE. Logs, CEPESC, BU independente e ato individual dos nulos técnicos são frentes distintas. Publicação em pacote separado `caminho-pkix-amostral-v1`, com hashes e sem certificados reais completos/VSC.
