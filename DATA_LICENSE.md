# Dados, materiais de terceiros e atribuições

A [licença MIT](LICENSE) deste projeto aplica-se ao código e à documentação de autoria própria. Os dados eleitorais, a geografia e os componentes de terceiros preservam suas licenças e atribuições originais. Tabelas, mapas, fichas e relatórios podem incorporar esses materiais; a licença do software não substitui as condições das fontes incorporadas.

## Dados eleitorais — Tribunal Superior Eleitoral

Fonte: **Tribunal Superior Eleitoral (TSE), Portal de Dados Abertos**. Os catálogos de [resultados de 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026) e [boletins de urna de 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna), consultados em 3 de novembro de 2026, indicam **Creative Commons Attribution / Atribuição (CC BY)**. Consulte a licença vinculada pelo próprio catálogo para os termos aplicáveis; este aviso não presume uma versão da CC BY que não esteja especificada na fonte.

As referências históricas provêm dos conjuntos de [2018](https://dadosabertos.tse.jus.br/dataset/resultados-2018) e [2022](https://dadosabertos.tse.jus.br/dataset/resultados-2022). Devem ser preservadas as condições indicadas em cada conjunto e a atribuição ao TSE.

Na reutilização, identifique a fonte, mantenha a referência ao conjunto e à licença aplicável e informe os tratamentos realizados. Neste projeto, os tratamentos incluem seleção do cargo, normalização de chaves, conversão de formatos, agregações, cálculo de indicadores, conferências entre arquivos e visualizações. Os relatórios são análises deste projeto, sem indicação de endosso institucional pelo TSE.

A origem, as versões e os hashes estão em [data/manifest.json](data/manifest.json) e [fontes_utilizadas.json](outputs/2026/fontes_utilizadas.json). Os números oficiais, apontamentos originais e limitações documentados devem acompanhar a interpretação dos resultados.

## Geografia — Instituto Brasileiro de Geografia e Estatística

Fonte: **Instituto Brasileiro de Geografia e Estatística (IBGE)**. O projeto utiliza:

- [API de localidades — municípios](https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado).
- [API de malhas — municípios do Brasil](https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application%2Fvnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio).
- [Malha municipal de Mato Grosso de 2025](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/MT/MT_Municipios_2025.zip).

Esses materiais preservam os termos de suas fontes e a atribuição ao IBGE. Este projeto não atribui licença MIT aos arquivos geográficos de origem. As visualizações aplicam simplificação, projeção e associação com os códigos eleitorais; não são produtos cartográficos oficiais do IBGE.

URLs, datas de obtenção e hashes geográficos são registrados em [mapa_dados.json](outputs/2026/mapa_dados.json) e nos metadados de [localidades](data/geografia/municipios_ibge.json), [malhas simplificadas](data/geografia/malha_municipal_ibge.json) e [Mato Grosso](data/geografia/mt_2025.json).

## Dependências, fontes tipográficas e conteúdos externos

Na extensão Ed521, o PDF técnico do ITI é obtido separadamente da fonte oficial e preserva seus termos; o pacote de resultados informa URL, versão e hash, sem relicenciar ou redistribuir o PDF. Os vetores sintéticos são gerados pelo projeto com o genérico Noble configurado para o perfil e têm sua origem explicitada em [ED521.md](docs/ED521.md); não são vetores oficiais. As dependências npm de referência permanecem sob suas licenças MIT originais e são instaladas por lockfile, sem incluir `node_modules` no repositório ou nos resultados.

Na conferência amostral, os RDV, BUs, imagens digitais, assinaturas e logs provêm do [catálogo de arquivos transmitidos para totalização do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026-arquivos-transmitidos-para-totalizacao). O pacote público desta etapa distribui resultados agregados e inventário de fontes/hashes; os originais ficam preservados localmente. Os esquemas ASN.1 consultados são obtidos separadamente de [espelho de terceiros](https://github.com/doccaz/urnas-br/tree/main/docv2), com origem e hashes explícitos em [AUDITORIA.md](docs/AUDITORIA.md). Não são relicenciados como código de autoria própria nem incluídos no pacote público. Nenhum código desse espelho é executado.

O backend pyhanko-certvalidator 0.33.0 e suas dependências preservam suas licenças originais; o backend é distribuído sob MIT pelo mantenedor. A fixture PKIX/Ed521 do projeto contém apenas certificados e LCR sintéticos, gerados com chaves públicas de teste, sem relação com urnas. Seu gerador declara essa origem; certificados reais completos não integram o pacote deste incremento.

A análise de logs publica somente contagens agregadas, regras locais e metadados de origem. Mensagens brutas, nomes, identificações pessoais e sequências/horários individuais de votação não integram os pacotes. As capturas das páginas oficiais são preservadas separadamente com URL e hash; seus textos integrais não são redistribuídos.

Bibliotecas, fontes tipográficas incorporadas e eventuais conteúdos de terceiros mantêm suas respectivas licenças e avisos de copyright. A licença MIT do projeto não os relicencia. Links e registros de afirmações de notícias identificam as fontes consultadas; não concedem direitos sobre o conteúdo integral dos veículos.

## Pacotes de resultados

Os pacotes da release distribuem resultados processados e cópias geográficas com a proveniência registrada em [docs/resultados-publicados.json](docs/resultados-publicados.json). A aplicação da MIT ao software não altera as condições originais dos materiais contidos nesses pacotes. Os hashes continuam identificando as cópias publicadas.
