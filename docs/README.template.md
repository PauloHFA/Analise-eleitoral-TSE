# Análise presidencial — eleições de 2026

Projeto local em Python, DuckDB e Parquet para investigar mudanças entre turnos e consistência dos arquivos abertos do TSE. Brasil e exterior têm contagens separadas. A entrega reúne o processamento nacional, as referências históricas, a investigação de passagens a zero e viradas, as fichas e o mapa municipal.

As próximas implementações estão organizadas no [roteiro de etapas e commits](docs/PROXIMAS_ETAPAS.md), com critérios de conclusão, fontes e pendências de cada frente.

**Primeira rodada implementada:** [estabilidade dos pares e perfil das exclusões](docs/RESULTADOS_INCREMENTAIS.md). A referência de 30 pares foi reproduzida, mas o topo do ranking depende da configuração; esses resultados complementares devem acompanhar a interpretação das prioridades originais.

**Frente 3 — primeiro passo:** [dossiê local de categorias e versões](docs/DOSSIE_CATEGORIAS.md), com parcelas por município/zona/turno, conferência do detalhe oficial original e preservação das classificações anteriores. A explicação documental da causa continua pendente.

**Os padrões pedidos foram pesquisados; a investigação de todas as incongruências não está encerrada.** Há mudanças confirmadas nos arquivos, apontamentos explicados quanto à sua regra aritmética, comparações limitadas e procedimentos ainda não realizados. Alertas exploratórios não demonstram fraude, nem permitem saber como pessoas específicas mudaram de voto.

## Sumário

- [Leitura rápida e resultados consolidados](#leitura-rápida-e-resultados-consolidados)
- [Baixar os resultados completos](#baixar-os-resultados-completos)
- [PDF: leitura guiada e reprodução](#pdf-leitura-guiada-e-reprodução)
- [Avaliação de cobertura](#avaliação-de-cobertura)
- [1. Obtenção e preservação](#1-obtenção-e-preservação)
- [2. Preparação das bases](#2-preparação-das-bases)
- [3. Comparabilidade e exclusões](#3-comparabilidade-e-exclusões)
- [4. Indicadores e denominadores](#4-indicadores-e-denominadores)
- [5. Triagem estatística](#5-triagem-estatística)
- [6. Referência histórica e sensibilidade](#6-referência-histórica-e-sensibilidade)
- [7. Conferência documental e totalização](#7-conferência-documental-e-totalização)
- [8. Investigação dirigida](#8-investigação-dirigida)
- [9. Mapas e validação](#9-mapas-e-validação)
- [Reprodução passo a passo](#reprodução-passo-a-passo)
- [Análises adicionais propostas](#análises-adicionais-propostas)
- [Inventário de entregas](#inventário-de-entregas)
- [Licença](#licença)

## Leitura rápida e resultados consolidados

Abra o [relatório HTML com resumo executivo e filtros](outputs/2026/relatorio.html), o [PDF](outputs/2026/relatorio.pdf) ou o [mapa independente](outputs/2026/mapa_eleitoral.html). O resumo vem antes do mapa e responde às perguntas originais. Os números deste documento e desse resumo derivam da mesma [síntese estruturada](outputs/2026/sintese_analise.json), que registra valor, unidade, fonte e situação interpretativa.

{{overview}}

As seções sem comparação válida continuam no inventário, com os motivos de exclusão. Comparabilidade territorial e elegibilidade estatística são conceitos diferentes: uma seção pequena pode ser territorialmente comparável e não participar da triagem estatística.

As passagens a zero encontradas tinham votação anterior pequena para Flávio e nenhuma liderança anterior dele. As viradas territoriais não implicam necessariamente perda de votos absolutos. A conferência BU × resultado confirma consistência entre representações do resultado, sem explicar as escolhas dos eleitores.

**A confirmação de persistência de divergências não foi realizada.** O campo legado `divergencias_persistentes_confirmadas: 0`, preservado em `resumo.json` por compatibilidade, não demonstra ausência de irregularidades. Na síntese, esse resultado tem valor `null` e situação `não investigado`. Não houve auditoria de RDV, assinaturas digitais, logs ou documentos físicos das urnas.

## Avaliação de cobertura

{{matrix}}

Os relatórios reúnem fontes e evidências verificáveis, mas não encerram a explicação de todas as causas. O resumo comum agora apresenta logo no início os achados, as explicações restritas ao apontamento, as limitações e o que não foi investigado. Mapas ajudam a localizar casos; o inventário completo e as provas por registro são necessários para verificá-los.

## Baixar os resultados completos

O Git versiona código, documentação, relatórios HTML/PDF, mapas, fichas, sínteses, dicionários e tabelas pequenas de referência. As tabelas CSV/Parquet completas, que somam vários gigabytes, estão nos pacotes da [release resultados-2026-v1](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/resultados-2026-v1). Os links para tabelas maiores neste documento e nos relatórios ficam disponíveis localmente após a extração.

- [Resultados de 2026 e geografia](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/download/resultados-2026-v1/resultados-2026.zip)
- [Referência de 2018](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/download/resultados-2026-v1/referencia-2018.zip)
- [Referência de 2022](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/download/resultados-2026-v1/referencia-2022.zip)
- [Hashes dos pacotes](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/download/resultados-2026-v1/SHA256SUMS.txt) e [manifesto por arquivo](docs/resultados-publicados.json)

Extrair os três ZIPs **na raiz do clone**, preservando os caminhos `outputs/2026` e `data/geografia`. Os pacotes contêm resultados processados; para uma nova ingestão, obter os ZIPs eleitorais originais do TSE pelos comandos abaixo.

```powershell
gh release download resultados-2026-v1 --repo PauloHFA/Analise-eleitoral-TSE --dir outputs/publicacao
Get-FileHash outputs/publicacao/*.zip -Algorithm SHA256
# Comparar com SHA256SUMS.txt antes de extrair os pacotes oficiais desta release
Expand-Archive outputs/publicacao/resultados-2026.zip -DestinationPath . -Force
Expand-Archive outputs/publicacao/referencia-2018.zip -DestinationPath . -Force
Expand-Archive outputs/publicacao/referencia-2022.zip -DestinationPath . -Force
# Atualizar o PDF após extrair o snapshot original, preservando as tabelas
gh release download pdf-revisado-v2 --repo PauloHFA/Analise-eleitoral-TSE --pattern relatorio.pdf --pattern pdf_edicao.json --dir outputs/2026 --clobber
```

Os ZIPs da release `resultados-2026-v1` preservam a edição original do PDF. A [edição explicativa atualizada](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/pdf-revisado-v2) é distribuída separadamente, mantendo os hashes dos pacotes originais. `scripts/validar_publicacao.py` confere os conteúdos do snapshot compactado; `--workspace` compara também a pasta local, que pode conter revisões posteriores do PDF.

## PDF: leitura guiada e reprodução

{{pdf_edition}}

O corpo principal responde às perguntas originais antes de apresentar as listas extensas. Cada tema distingue pergunta, resultado, interpretação e limite: comparabilidade, critérios de triagem, concordância entre arquivos, seções não instaladas, diferença nominal/nulos técnicos, passagens a zero, viradas, coortes e referência histórica. O exemplo da cidade do Rio separa perda de vantagem de perda de votos absolutos. O histórico é apresentado em tabelas, sem blocos de JSON.

Os anexos mantêm todas as unanimidades, os municípios com inversão em RJ/MG, os indicadores consolidados e as fichas estatísticas originais. Os percentuais das fichas têm denominadores explicados; cada ficha identifica o indicador mais afastado dos pares e seu MAD. A geração editorial utiliza os dados já processados.

```powershell
# Apenas o PDF: preserva HTML, síntese, tabelas, gráficos e fichas JSON
.\.venv\Scripts\python.exe scripts/gerar_pdf.py outputs/2026
# Inspeção de texto, sumário, margens, imagens e fichas (ferramenta opcional)
.\.venv\Scripts\python.exe -m pip install pymupdf
.\.venv\Scripts\python.exe scripts/validar_pdf.py outputs/2026 --render outputs/publicacao/pdf-preview
# Atualizar o README mantendo o hash da síntese
.\.venv\Scripts\python.exe scripts/gerar_documentacao.py --output outputs/2026 --reuse-synthesis --validation outputs/logs/validacao-entrega.log --tests outputs/logs/testes-documentacao.log
```

O processamento nacional e `gerar_relatorio.py` também utilizam essa apresentação do PDF. A validação vigente é descrita na seção de mapas e validação; os detalhes da inspeção editorial estão em [validacao-pdf.log](outputs/logs/validacao-pdf.log).

## 1. Obtenção e preservação

**Pergunta:** quais arquivos sustentam a análise e como reproduzir a mesma versão?

**Fontes e universo:** arquivos de votação por seção, detalhe de seção, votação nominal por município/zona e detalhe de totalização nos anos analisados; BU dos dois turnos de 2026, por UF e exterior. Os BU históricos não foram incorporados. Os [dados eleitorais são abertos](https://dadosabertos.tse.jus.br/dataset/resultados-2026), com os [BU em conjunto próprio](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna).

{{sources}}

{{dates}}

{{generations}}

**Método:** baixar e preservar ZIPs em `data/raw/<prefixo-do-hash>/`, verificar tamanho e SHA256, registrar URL, identificador do recurso, ano, tipo, obtenção UTC e cabeçalhos HTTP disponíveis. Novas cópias não sobrescrevem versões antigas. O [manifesto geral](data/manifest.json) e o [manifesto da entrega](outputs/2026/fontes_utilizadas.json) permitem rastrear os arquivos utilizados. Há cópias locais e metadados dos catálogos para reprodução offline.

**Resultado e limite:** a entrega tem rastreabilidade da cópia processada. Hash identifica integridade dessa cópia; não equivale a verificar assinatura digital da urna. Datas de geração e de obtenção diferem. A votação por seção e a totalização nominal analisadas não têm a mesma geração, o que limita conclusões sobre persistência de divergências.

## 2. Preparação das bases

**Pergunta:** como evitar somas repetidas, mistura de cargos e zeros inventados?

**Fontes:** ZIPs preservados, esquemas definidos em [ingest.py](src/eleicoes/ingest.py) e exportações `secoes_por_turno`, `candidatos`, `duplicidades_*`.

**Método:** selecionar Presidente (`CD_CARGO=1` ou `CD_CARGO_PERGUNTA=1`), conferir ano/turno e normalizar a chave `ano/turno/UF/município TSE/zona/seção`. Preferir o CSV nacional `BR` quando disponível no arquivo, sem somá-lo novamente aos arquivos de UF. Ler os CSVs originais com separador ponto e vírgula e codificação Latin-1, em blocos de 60 mil linhas, usando DuckDB e Parquet. Partições de trânsito e destinação dos votos na totalização são preservadas para somar corretamente.

Duplicatas idênticas são registradas e reduzidas a uma observação. Medidas conflitantes são colocadas em quarentena e invalidam a fonte para triagem; não são somadas nem tomadas como zero. Um candidato omitido pode ter zero implícito apenas quando o contexto completo da seção/turno permite essa interpretação. A ausência da unidade inteira continua ausente.

**Resultado — duplicidades em 2026:**

{{duplicates}}

**Interpretação e limite:** essas tabelas registram duplicidades detectáveis nas chaves e medidas importadas; sua ausência não certifica todas as etapas do processo eleitoral. Em `section_base`, `valid` soma os códigos nominais 1–94 antes de eventual tratamento jurídico na totalização. Branco é 95, nulo é 96 e outros códigos são separados. Portanto, o rótulo analítico de válidos não deve ser confundido com a destinação jurídica final de todos os votos.

Dados completos: [seções por turno](outputs/2026/secoes_por_turno.parquet), [candidatos](outputs/2026/candidatos.csv), [indicadores](outputs/2026/indicadores_secoes.parquet).

## 3. Comparabilidade e exclusões

**Pergunta:** estamos comparando unidades territoriais compatíveis entre os turnos?

**Método:** exigir presença nos dois turnos, fonte completa, ausência de conflitos aritméticos relevantes, aptos iguais e composição compatível. Seções com agregações declaradas saem da comparação individual. Nas agregações por local, município e UF, comparar também as listas de membros, incluindo agregações declaradas nos BU quando disponíveis. Igualdade de aptos isoladamente não basta. Mudanças de local/endereço permanecem como contexto.

**Resultado nacional, incluindo exterior:**

{{comparability}}

{{regional}}

**Motivos principais de cobertura** — mutuamente exclusivos nesta classificação, com as comparáveis incluídas para fechar o universo:

{{exclusions}}

**Elegibilidade estatística:** `comparable AND NOT small`, sendo `small` menos de 50 comparecentes em qualquer turno. A categoria pequena se sobrepõe a outras; não deve ser somada às exclusões territoriais. Seções pequenas comparáveis podem integrar descrições e coortes agregadas, com cobertura explícita, sem receber alerta estatístico individual.

**Limitações:** códigos e composição publicados não estabelecem identidade das pessoas votantes. A exportação completa do painel Capilaridade/SIG-TSE não foi incorporada, pois a consulta automatizada retornou HTTP 403. Remanejamentos sem correspondência oficial completa permanecem limitados; igualdade de códigos não descarta mudança física de endereço.

Dados: [cobertura por motivo](outputs/2026/cobertura_por_motivo.csv), [sem comparação](outputs/2026/secoes_sem_comparacao.parquet), [indicadores por local](outputs/2026/indicadores_local.parquet), [município](outputs/2026/indicadores_municipio.parquet), [UF](outputs/2026/indicadores_uf.parquet), [exterior](outputs/2026/indicadores_exterior.parquet).

## 4. Indicadores e denominadores

**Pergunta:** mudou a quantidade de votos, a participação ou apenas o denominador?

**Fontes/universo:** seções observadas e agregações territoriais; indicadores brutos são preservados mesmo quando a comparação é limitada. Elegibilidade é exigida para alertas estatísticos.

| Indicador | Fórmula e denominador |
| --- | --- |
| Diferença absoluta | `quantidade_2 − quantidade_1`, em votos ou eleitores |
| Variação percentual | `100 × (quantidade_2 − quantidade_1) / quantidade_1`; ausente se a base for zero |
| Participação de candidato | `votos do candidato / soma nominal 1–94` em cada turno |
| Comparecimento | `comparecentes / aptos` em cada turno |
| Brancos e nulos | Cada categoria dividida por comparecentes, em cada turno |
| Mudança em pontos percentuais | `100 × (taxa_2 − taxa_1)` |
| Passagem a zero | Candidato com votos positivos no primeiro e zero no segundo, com presença dos dados conferida |
| Margem dirigida entre finalistas | `100 × (Flávio − Lula) / (Flávio + Lula)` |

**Método:** denominador zero gera ausência, não infinito. Guardar taxas por turno, diferenças absolutas, percentuais e pontos percentuais separadamente. Além dos finalistas, manter eliminados, aptos, comparecimento, abstenção, brancos, nulos e outros códigos. A identidade contábil `ΔLula + ΔFlávio = votos dos eliminados no primeiro turno + Δsoma nominal` é uma soma agregada, não uma reconstrução de transferências individuais.

**Resultado/interpretação:** as tabelas permitem separar perda de vantagem de perda efetiva de votos. O exemplo simulado `2.000/2.000 → 4.000/zero` é detectado nos testes; ele não é apresentado como caso real encontrado. Uma perda de 10 pp na margem entre finalistas equivale a outra medida que uma perda de 10 pp na participação sobre todos os válidos.

**Limites e documentação:** não estimamos quem mudou de voto ou os motivos. O [dicionário principal](outputs/2026/dicionario.csv) e o [dicionário da investigação](outputs/2026/investigacao_dicionario.csv) definem os campos efetivamente exportados.

## 5. Triagem estatística

**Pergunta:** quais mudanças são grandes em valor absoluto ou incomuns entre seções semelhantes?

**Universo:** somente seções territorialmente comparáveis e com pelo menos 50 comparecentes em ambos os turnos. O exterior é tratado separadamente por UF `ZZ`.

**Método dos pares:** selecionar 30 vizinhos, priorizando o mesmo município e completando na mesma UF. As características do primeiro turno são `ln(1 + aptos)`, comparecimento e participação de todos os candidatos. Centralizar cada variável pela mediana da UF e dividir pelo desvio padrão da UF; escalas ≤ `1e-12` são substituídas por 1. A distância é euclidiana, calculada com `cKDTree`. Excluir a própria seção. O resultado de segundo turno não seleciona vizinhos; os pares são referências descritivas, não controles causais.

Para cada mudança, calcular `z_robusto = |mudança − mediana(mudanças dos pares)| / (1,4826 × MAD)`. `MAD` é a mediana das distâncias absolutas à mediana. Se `MAD ≤ 1e-9`, o indicador é inconclusivo e fica ausente, sem infinito; outros indicadores informativos continuam disponíveis. `robust_max` é o máximo disponível entre comparecimento, brancos, nulos e participações dos finalistas.

O limite robusto é **acima de 3,5**. O critério absoluto é mudança de pelo menos 10 pp em algum indicador **ou passagem de positivo para zero**. A triagem combinada é a **união** dos critérios, não sua soma. Não são p-valores nem probabilidades de fraude; múltiplas comparações e MAD pequeno exigem revisão.

**Resultados e sobreposições:**

{{screening}}

**Interpretação/limites:** mudanças grandes podem ser frequentes quando os votos antes distribuídos entre candidatos se concentram nos finalistas. A ordenação prioriza maior desvio robusto, maior mudança em pp e chave geográfica. As fichas estatísticas são uma seleção para revisão; não representam todos os alertas nem investigação concluída das causas.

Dados e código: [alertas completos](outputs/2026/alertas_secoes.parquet), [indicadores e pares](outputs/2026/indicadores_secoes.parquet), [analysis.py](src/eleicoes/analysis.py).

## 6. Referência histórica e sensibilidade

**Pergunta:** esses critérios selecionam que proporção de seções em eleições diferentes e com outros limites?

**Fontes/universo:** processamento separado de 2018, 2022 e 2026. O quadro abaixo usa **somente Brasil**, enquanto o quadro consolidado inicial inclui o exterior. As frequências usam as seções elegíveis de cada ano como denominador.

{{historical}}

**Método:** repetir os critérios de 5/10/15 pp, sempre incluindo a passagem a zero, além do desvio robusto. Não parear identidades de seções entre anos, nem presumir continuidade de candidaturas, eleitores ou regras jurídicas.

**Interpretação:** as frequências mostram a sensibilidade da triagem, não a frequência de irregularidades. A alta frequência do critério absoluto em 2018, por exemplo, não autoriza inferência de fraude. Os BU históricos não foram auditados e os apontamentos aritméticos históricos não receberam a mesma revisão específica das seções não instaladas de 2026. A comparação histórica não é uma auditoria documental equivalente nos três anos.

Dados completos: [histórico 2018](outputs/2026/historico/2018/analise_concluida.json), [histórico 2022](outputs/2026/historico/2022/analise_concluida.json), [quadro histórico consolidado](outputs/2026/resumo.json). Os arquivos `indicadores_secoes` de cada pasta histórica contêm o resultado linha a linha em CSV/Parquet.

## 7. Conferência documental e totalização

**Pergunta:** os números de votação concordam entre BU, seção e totalização? Os alertas aritméticos têm contexto documental?

**Método/universo:** confrontar seção/cargo/código de voto/turno, conferindo presença dos registros, zeros implícitos, duplicidades, eleição, geração, instalação e metadados. Comparar também somas por município/zona com a totalização oficial e suas categorias. As linhas concordantes não são pessoas ou urnas distintas.

{{documentary}}

**Seções não instaladas:** todos os apontamentos revisados desse grupo têm `ST_SECAO_INSTALADA=Não`, ausência de votação e comparecimento/abstenções zerados. Aplicar universalmente `comparecimento + abstenções = aptos` gerou o alerta fora de contexto. O apontamento foi explicado, e as seções continuam fora da comparação entre turnos. Não foi estabelecido por que não foram instaladas ou o destino dos eleitores. [Apontamentos originais](outputs/2026/pendencias_documentais.parquet) e [revisão com evidências](outputs/2026/revisao_documental.csv) coexistem; não apagamos os registros iniciais.

**Diferença nominal e nulos técnicos:** as diferenças nominais são do candidato 28 no primeiro turno e coincidem com os nulos técnicos nas mesmas combinações município/zona. A diferença nominal é compensada nos nulos, com brancos e total de votos iguais. A explicação é aritmética, compatível com reclassificação; sua razão jurídica e operacional não foi estabelecida. As versões dos arquivos diferem, portanto não se declara reconciliação integral com uma mesma versão oficial.

**Cobertura nominal:** as três contagens do quadro representam unidades diferentes: geografia sem turno, geografia por turno e linhas por candidato. Todas as linhas desse grupo têm comparecimento publicado zero nas duas fontes e votos oficiais zero. A ausência nominal é compatível com esse contexto, sem indicar votos perdidos. O `status` bruto de cobertura permanece preservado; a síntese acrescenta a interpretação, sem preencher arbitrariamente valores ausentes na tabela original. O motivo administrativo dos zeros ainda não foi investigado.

**Aptos:** a nota do TSE informa 39 registros duplicados por transferência temporária. Os denominadores por seção são mantidos como publicados, sem subtrair registros arbitrariamente. Essa ressalva não é uma duplicidade de votos demonstrada pelo processamento.

**Limites:** BU e resultados por seção são representações do resultado da urna, não auditorias independentes do equipamento. Concordância entre eles não resolve versões e tratamento jurídico na totalização. A confirmação de persistência **não foi realizada**; zero no campo legado não é evidência de inexistência.

Dados: [conferência BU](outputs/2026/conferencia_bu.parquet), [município/zona](outputs/2026/reconciliacao_municipio_zona.parquet), [categorias](outputs/2026/reconciliacao_categorias.csv), [comparecimento](outputs/2026/reconciliacao_comparecimento.csv), [totais municipais, estaduais e nacionais](outputs/2026/reconciliacao_totais.csv).

## 8. Investigação dirigida

**Perguntas:** onde há votos válidos exclusivos para um finalista, passagens a zero ou grandes reduções de vantagem? As notícias correspondem à cópia dos dados analisada?

### Zeros nacionais

**Método/universo:** procurar nacionalmente unanimidades nos válidos do segundo turno nos dois sentidos. Distinguir candidato já zerado, passagem de positivo para zero, unanimidade só nos válidos e unanimidade de todos os votos depositados (sem brancos/nulos/outros). Conferir os dois turnos, situação, presença, duplicidades e composição; em comparação limitada, apresentar contexto agregado apenas quando compatível.

{{zeros}}

**Interpretação:** as passagens a zero confirmadas nos arquivos não eram seções anteriormente lideradas por Flávio. Os casos limitados permanecem no inventário. Concordância documental não explica por que eleitores escolheram determinado candidato.

Dados completos: [unanimidades e zeros](outputs/2026/investigacao_zeros.csv), [provas por seção/turno](outputs/2026/investigacao_conferencia_bu.parquet), [classificações, parâmetros e hashes](outputs/2026/investigacao_resumo.json).

### Viradas e perda de vantagem em RJ/MG

**Método/universo:** inventário completo dos dois estados por seção, local, município e UF. Margem `100 × (Flávio − Lula)/(Flávio + Lula)`; perda é margem do primeiro menos a do segundo turno. Incluir toda inversão estrita, identificar empates e reduções ≥5/10/15 pp. Os contadores abaixo são **observações territoriais brutas**, incluindo unidades com comparação limitada; não são alertas estatísticos elegíveis. As reduções indicadas se referem à vantagem inicial de Flávio.

{{directed_sensitivity}}

Resultados estaduais completos dos finalistas, em votos absolutos:

{{states}}

**Coortes municipais:** apresentar resultado territorial completo e, em paralelo, soma das mesmas seções territorialmente comparáveis, incluindo pequenas para descrição. Informar cobertura de aptos, comparecimento e votos em cada turno. Essa amostra não substitui o resultado municipal; a representatividade dos excluídos não foi demonstrada.

Exemplo verificável da capital fluminense:

{{rio}}

Nesse exemplo Flávio ganhou votos absolutos, mas Lula cresceu mais e a liderança municipal mudou. A inversão também aparece na coorte; isso não prova equivalência de perfil entre seções incluídas e excluídas nem explica escolhas individuais. Coberturas completas de todos os municípios estão no [inventário dirigido](outputs/2026/investigacao_viradas.parquet).

**Pares e seleção das fichas:** reutilizar os mesmos 30 pares do processamento nacional para medir o desvio robusto da mudança de margem. MAD insuficiente é inconclusivo. Selecionar 50 seções elegíveis de cada UF entre os padrões investigados, por desvio robusto decrescente, redução de margem e chave geográfica. Manter os casos não comparáveis no inventário.

### Notícias e classificações

As afirmações e fontes foram registradas na consulta de 03/11/2026 e são reproduzidas offline. A comparação é com a versão local e com a abrangência de cada notícia; relato não confirmado não equivale a erro na votação.

{{news}}

As classificações distinguem observação/mudança confirmada nos arquivos, comparação territorial limitada, divergência documental e relato não confirmado. Confirmar valores não determina a causa nem uma transferência individual. Uma notícia com margem municipal diferente é marcada como relato não confirmado nessa versão.

### Fichas e ocorrências

{{cases}}

As fichas dirigidas cobrem todas as unanimidades nacionais, todos os municípios com inversão em RJ/MG, as seções selecionadas por estado e os dois estados. A mesma seção pode aparecer em uma ficha estatística e outra dirigida. A quantidade de arquivos não é o número de ocorrências únicas, de urnas com irregularidades ou de casos com causa investigada. As fichas são geradas automaticamente a partir das evidências computadas. As fichas estatísticas originais têm hashes preservados na investigação.

**Limites:** o inventário nacional de zeros e o territorial de RJ/MG respondem a perguntas distintas. Não se extrapola a todos os municípios brasileiros o estudo detalhado de viradas dos dois estados. Documentos originais da urna e causas jurídicas não foram auditados nesta etapa.

## 9. Mapas e validação

**Pergunta:** onde estão os padrões e os artefatos os representam corretamente?

**Fontes e método geográfico:** relacionar códigos TSE e IBGE por UF/nome, mantendo ambos. Treze variantes foram vinculadas explicitamente e conferidas, sem aproximação difusa. Usar a malha simplificada do IBGE e substituir Mato Grosso pela malha oficial de 2025, incluindo Boa Esperança do Norte e limites vizinhos. Arquivos, URLs, obtenção e hashes permanecem em `data/geografia` e em `mapa_dados.json`.

{{geography}}

**Visualização:** azul indica mais votos para Flávio, vermelho para Lula e cinza empate/ausência. Na visualização por vencedor, intensidade `.32 + .68 × |Flávio − Lula|/(Flávio + Lula)`; na visualização por quantidade do candidato, intensidade `.12 + .88 × sqrt(votos/máximo nacional do turno)`, com zero branco. Contorno dourado marca mudança estrita de vencedor. A projeção é equirretangular, com longitude multiplicada por `cos(15°)` e orientação norte acima do sul, conferida também nos PNGs.

O mapa permite alternar turno, filtrar UF/viradas, mudar escala, ampliar, arrastar e consultar os valores. Os marcadores de passagens a zero representam o centro aproximado da caixa do **município**, não o endereço da seção. Área do polígono não é quantidade de eleitores. Exterior está em tabelas separadas.

**Resultado:** a correspondência cobre todas as unidades municipais brasileiras da base, incluindo unidades especiais como DF; a contagem não deve ser apresentada como municípios convencionais apenas. Os valores dos finalistas por município e suas somas nacionais foram comparados às tabelas de origem. O mapa HTML funciona offline; o PDF inclui os dois turnos de Brasil, RJ e MG.

**Validação vigente:**

{{validation}}

A suíte cobre passagem a zero, exemplo extremo simulado, comparecimento, duplicidades, agregações, denominadores, instalação, unanimidade de válidos/todos os votos e perda de vantagem com ganho absoluto. Os testes desta documentação acrescentam distinção de unidades de cobertura, comparabilidade/elegibilidade e persistência não avaliada. Os validadores conferem fichas, hashes, seleção, provas de BU, links locais, JSON estrito, PDF, contagens CSV/Parquet e executam os controles JavaScript com Node. O mapa foi inspecionado visualmente em navegador na preparação anterior; esta revisão preserva sua geografia e os PNGs.

**Limites:** validação do software e dos artefatos não é auditoria integral da eleição. Testes simulados demonstram comportamento do programa nos cenários testados; não demonstram ocorrência real desses cenários.

## Reprodução passo a passo

O pacote declara Python ≥3.11; esta entrega e seu arquivo de versões foram executados com **Python 3.12.10**. Node é usado nos validadores de filtros/mapa, mas não para abrir os HTMLs. `requirements-lock.txt` registra as versões usadas. Windows/PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps

# 1. Processamento nacional: dados, indicadores, histórico e BU de 2026
.\.venv\Scripts\python.exe -m eleicoes run
# Alternativa com todas as fontes e catálogos já locais: run --offline

# 2. Investigação dirigida, reutilizando os Parquets da etapa anterior
.\.venv\Scripts\python.exe -m eleicoes investigar --output outputs/2026 --ufs RJ MG

# 3. Preparação do mapa; --offline reutiliza a geografia já preservada
.\.venv\Scripts\python.exe scripts/gerar_mapa.py --offline --output outputs/2026

# 4. Relatórios e síntese comuns; depois, README
.\.venv\Scripts\python.exe scripts/gerar_relatorio.py outputs/2026
.\.venv\Scripts\python.exe scripts/gerar_documentacao.py --output outputs/2026

# 5. Testes e validação final dos artefatos
.\.venv\Scripts\python.exe -X utf8 -m pytest -q | Out-File -Encoding utf8 outputs/logs/testes-documentacao.log
.\.venv\Scripts\python.exe -X utf8 scripts/validar_entrega.py outputs/2026 | Out-File -Encoding utf8 outputs/logs/validacao-entrega.log
.\.venv\Scripts\python.exe scripts/validar_sintese.py outputs/2026

# 6. Incorporar somente os registros finais de validação ao README
.\.venv\Scripts\python.exe scripts/gerar_documentacao.py --output outputs/2026 --validation outputs/logs/validacao-entrega.log --tests outputs/logs/testes-documentacao.log
.\.venv\Scripts\python.exe scripts/validar_sintese.py outputs/2026
```

Na primeira preparação do mapa, omitir `--offline` para obter a geografia. A execução nacional padrão processa 2018/2022/2026 e BU de 2026; `--years 2026` omite o histórico, `--no-bu` não oferece conferência documental completa. Não misturar uma entrega parcial com esta entrega consolidada. Os diretórios de logs são criados pelo processamento; ao executar etapas isoladas em uma pasta nova, criá-los previamente.

Para a revisão documental desta entrega, **não foi feita nova ingestão nacional**: reutilizar as etapas 4–6. O gerador do relatório também deriva `sintese_analise.json` quando a investigação e o mapa completos estão presentes. O gerador do README lê [este modelo](docs/README.template.md) e deriva seus quadros da mesma síntese. Alterar o modelo e os renderizadores, evitando editar manualmente números que serão regenerados.

Operações alternativas disponíveis:

```powershell
# Somente baixar dados e BU
.\.venv\Scripts\python.exe -m eleicoes fetch --years 2026 --bu
# Recalcular sobre o banco carregado, sem repetir ingestão
.\.venv\Scripts\python.exe -m eleicoes run --reuse-db
# Retomar ingestão interrompida, com código e arquivos compatíveis
.\.venv\Scripts\python.exe -m eleicoes run --resume
# Dados simulados em entrega separada
.\.venv\Scripts\python.exe -m eleicoes demo --output outputs/demo
# Validadores especializados
.\.venv\Scripts\python.exe scripts/validar_investigacao.py outputs/2026
.\.venv\Scripts\python.exe scripts/validar_mapa.py outputs/2026
```

Reserve espaço para ZIPs, banco DuckDB, CSV e Parquet. A ingestão usa blocos de 60 mil linhas e DuckDB com limite de 1 GB; Python também usa memória para tabelas e arrays de pares por UF. Parquet usa grupos de 8.192 linhas e dicionários limitados. CSVs de composição por UF podem ter linhas acima de 2 MB: preferir Parquet ou usar DuckDB `read_csv(..., header=true, max_line_size=16777216)`.

## Análises adicionais propostas

**Ainda não executadas nesta entrega:**

{{recommendations}}

A conferência ampliada pode seguir as possibilidades de [auditoria descritas pelo TSE](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria). Isso não significa que esses procedimentos já tenham sido feitos. Recontagem do RDV e comparação com BU, verificação de assinaturas e inspeção de logs/documentos exigem fontes e procedimentos próprios. Os dados agregados não identificam votos de pessoas.

Os limites de 5/10/15 pp **já foram executados** e documentados; a proposta nova é variar pares e examinar a estabilidade dos rankings, além de aprofundar fontes e causas.

## Inventário de entregas

| Artefato | Conteúdo e uso |
| --- | --- |
| [HTML](outputs/2026/relatorio.html) / [PDF](outputs/2026/relatorio.pdf) | Resumo comum, cobertura, gráficos, mapas, fichas e referências |
| [Síntese](outputs/2026/sintese_analise.json) | Valores, unidades, fontes e situações interpretativas compartilhados |
| [Resumo original](outputs/2026/resumo.json) | Estado do processamento e histórico; campo legado de persistência sem conclusão |
| [Fontes utilizadas](outputs/2026/fontes_utilizadas.json) | Origem, obtenção e SHA256 dos arquivos eleitorais |
| [Indicadores de seção](outputs/2026/indicadores_secoes.parquet) | Universo completo, taxas, diferenças, pares e elegibilidade |
| [Alertas](outputs/2026/alertas_secoes.parquet) / [excluídas](outputs/2026/secoes_sem_comparacao.parquet) | Triagem completa e motivos de não comparação |
| [Revisão documental](outputs/2026/revisao_documental.csv) | Evidências e avaliação dos apontamentos originais |
| [Conferência BU](outputs/2026/conferencia_bu.parquet) / [totalização](outputs/2026/reconciliacao_municipio_zona.parquet) | Consistência entre arquivos e diferenças originais |
| [Categorias](outputs/2026/reconciliacao_categorias.parquet) / [comparecimento](outputs/2026/reconciliacao_comparecimento.parquet) | Contexto da reclassificação e da cobertura nominal |
| [Zeros](outputs/2026/investigacao_zeros.parquet) / [viradas](outputs/2026/investigacao_viradas.parquet) | Inventários completos, cobertura, pares, classificação e links de fichas |
| [Provas dirigidas](outputs/2026/investigacao_conferencia_bu.parquet) / [notícias](outputs/2026/investigacao_noticias.csv) | Registros conferidos e comparação dos relatos |
| [Dicionário](outputs/2026/dicionario.csv) / [dicionário dirigido](outputs/2026/investigacao_dicionario.csv) | Definição de campos e denominadores |
| [Correspondência municipal](outputs/2026/mapa_correspondencia_municipios.csv) / [dados do mapa](outputs/2026/mapa_dados.json) | Chaves TSE–IBGE, votos e fontes geográficas |
| `outputs/2026/fichas/` / `investigacao_fichas/` | Conjuntos separados de fichas; sobreposição de ocorrências possível |
| `outputs/2026/historico/2018/` / `historico/2022/` | Referências separadas por eleição, com CSV e Parquet |
| [WORKLOG](WORKLOG.md) / [logs](outputs/logs/README.md) | Registro técnico e execuções |

As tabelas analíticas têm versões CSV UTF-8 e Parquet quando aplicável. O README apresenta resultados consolidados e aponta para os registros completos; não reproduz centenas de milhares de linhas.

## Licença

O código e a documentação de autoria própria estão disponíveis sob a [licença MIT](LICENSE), com copyright de 2026 atribuído a PauloHFA.

Dados eleitorais do TSE, geografia do IBGE, dependências e outros materiais de terceiros preservam suas licenças e atribuições originais. O escopo e as fontes estão descritos em [DATA_LICENSE.md](DATA_LICENSE.md), inclusive para os dados incorporados aos relatórios, mapas e pacotes da release.
