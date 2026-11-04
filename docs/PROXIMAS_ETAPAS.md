# Próximas etapas — implementação por commits

Roteiro iniciado em **3 de novembro de 2026**. Cada incremento deve produzir código utilizável, testes pertinentes, resultados identificados por versão e um commit com coautoria do Codex. O estado de cada frente será atualizado somente após sua execução e conferência.

## Sequência e estado

| Ordem | Frente | Entrega | Estado inicial |
| --- | --- | --- | --- |
| 0 | Roteiro e preservação | Este documento, critérios de aceitação e convenções | Documentado |
| 1 | Estabilidade dos pares | Variações de 15/30/50 pares, sobreposição dos rankings e diagnóstico de MAD | Implementado, executado nacionalmente e validado |
| 2 | Cobertura e exclusões | Perfis incluídos/excluídos, cobertura municipal/UF e diferenças descritivas | Implementado, executado nacionalmente e validado |
| 3 | Categorias e versões | Dossiê verificável dos nulos técnicos e das diferenças de geração | Dossiê e pesquisa de norma/cadastro concluídos; ato individual e eficácia temporal pendentes |
| 4 | Investigação nacional e mapas | Viradas nos dois sentidos, inventário nacional e taxas de triagem com cobertura | Implementado, executado nacionalmente e validado; referência preservada |
| 5 | Conferência documental ampliada | Amostra prioritária e de comparação, RDV, assinaturas e BU impresso/imagem | Amostra registrada; obtenção e conferência dos documentos em andamento |

**Primeira rodada de implementação:** frentes 1 e 2, com execução sobre os arquivos locais e commits separados. Documentar uma frente não significa que ela foi executada. As frentes 3–5 não serão apresentadas como concluídas por existir uma rotina preparatória.

## Convenções para todos os incrementos

- Preservar `indicadores_secoes`, fichas, relatórios de referência e pacotes `resultados-2026-v1`. Resultados novos vão para subpastas próprias e não substituem a classificação original.
- Registrar entradas e SHA256, parâmetros, universo, unidades, versões do código e dependências relevantes, limitações e situação da execução.
- Separar Brasil e exterior. Ausência, dispersão insuficiente e falta de pares não são zeros ou ausência demonstrada de irregularidade.
- Distinguir comparação territorial de elegibilidade estatística, critérios absolutos de robustos e investigação das causas de conferência dos valores.
- Cada commit funcional deve executar os testes pertinentes. A execução nacional deve conferir os totais com o universo original e validar os artefatos antes de divulgar resultados.
- Arquivos grandes permanecem fora do Git; sínteses, documentação e relatórios leves podem ser versionados. Publicar tabelas grandes por pacotes próprios, com hashes, sem alterar releases anteriores.
- Não realizar contatos externos automaticamente. Uma necessidade de esclarecimento oficial será documentada com fontes e perguntas objetivas.

## 1. Estabilidade dos pares e dos rankings

**Pergunta:** as prioridades permanecem semelhantes quando mudamos a quantidade de pares? Quais escores são elevados principalmente por uma dispersão muito pequena?

**Entrada:** Parquets de indicadores e candidatos da entrega atual. Usar apenas as seções elegíveis; manter os 30 pares publicados como referência preservada. Não baixar novamente a base nacional.

**Método proposto:**

1. Conferir os pares publicados: quantidade, unicidade, ausência do próprio alvo, mesma UF e elegibilidade dos membros.
2. Comparar 15, 30 e 50 pares de forma aninhada: os 15 iniciais da referência; os 30 publicados; os 30 publicados acrescidos dos vizinhos necessários para 50. Manter prioridade municipal e completar na UF. A âncora preserva o resultado de referência e evita confundir sua alteração com desempates de distâncias.
3. Na extensão, usar somente características do primeiro turno: `ln(1 + aptos)`, comparecimento e participações de todos os candidatos. Centralizar pela mediana e escalar pelo desvio padrão da UF, como na análise original.
4. Recalcular medianas, MAD, escores e a união dos critérios. MAD ≤ `1e-9` continua inconclusivo. A análise de MAD pequeno é diagnóstica e não altera arbitrariamente os critérios originais.
5. Comparar rankings em um **universo comum**, com pares suficientes em todas as variantes. Quantificar à parte as unidades sem 50 pares. Não misturar falta de cobertura com mudança de classificação.
6. Medir retenção/interseção/Jaccard dos primeiros 25/50/100 casos, entradas/saídas da triagem, amplitude de posição e frequência de seleção por configuração. Informar também quando uma lista contém menos casos que o limite solicitado.
7. Mostrar indicador de maior afastamento, mudança observada, quantidade absoluta, mediana e MAD. Comparar MAD à ordem de grandeza de um voto no denominador do indicador, como diagnóstico de escala, sem interpretação probabilística.

**Artefatos:** tabelas por seção/configuração, tabela comparativa, rankings, resumo JSON, dicionário e relatório HTML separado em `outputs/2026/estabilidade/`.

**Aceitação:** k=30 reproduz escores e seleção publicados; pares válidos e aninhados; testes para MAD zero/pequeno, empate, passagem a zero e UF com poucos pares; rankings no universo comum; nenhuma alteração das fontes. Documentar se não houver reprodução da referência em vez de substituir os resultados silenciosamente.

**Commits previstos:** implementação/testes do comando; execução nacional e síntese conferida. Uma alteração do algoritmo original além da parametrização exige justificativa e comparação própria.

**Incremento implementado:** `eleicoes estabilidade --output outputs/2026 --pares 15 30 50`. O comando escreve em `outputs/2026/estabilidade/` e recusa sobrescrever uma pasta já preenchida; `--dest` permite uma execução independente. Há testes de referência reproduzida, conjuntos aninhados, pares insuficientes, MAD, listas vazias e preservação das entradas. A execução nacional foi conferida; resultados e limites constam da síntese incremental vinculada ao final deste roteiro.

## 2. Cobertura e perfil das unidades excluídas

**Pergunta:** os resultados da amostra comparável descrevem adequadamente o universo territorial? Onde as exclusões se concentram?

**Entrada:** inventário completo de seções e motivos de comparação, sem nova ingestão.

**Método:**

1. Separar grupos mutuamente exclusivos: não comparável; comparável pequena; elegível estatística. Manter também a classificação territorial original e seus motivos.
2. Contar unidades e cobertura por município/UF, incluindo exterior em quadros próprios. Publicar denominadores e ausências.
3. Comparar tamanho, comparecimento, brancos/nulos e participações dos finalistas no **primeiro turno**; apresentar medianas, quartis e cobertura das medidas. Não transformar ausência de uma medida em zero.
4. Comparar a composição geográfica dos grupos e suas diferenças descritivas. Evitar chamar diferenças observadas de prova de viés causal ou calcular uma margem de erro de amostragem aleatória para uma seleção não aleatória.
5. Informar quantos municípios têm cobertura baixa por faixas explícitas e sensibilidade ao limite escolhido. Coortes não substituem o total territorial.

**Artefatos:** cobertura municipal/UF, perfis e distribuição por motivo, resumo JSON, dicionário e relatório HTML separado em `outputs/2026/cobertura/`.

**Aceitação:** fechar as 499.248 unidades da referência; separar 429.166 comparáveis de 428.571 elegíveis; fechar motivos de exclusão; percentuais com denominador conhecido; testes de ausências e grupos pequenos; fontes preservadas.

**Commits previstos:** implementação/testes; execução e documentação dos achados. Se os resultados justificarem, propor ponderação ou modelagem como nova etapa, sem alterar a amostra original automaticamente.

**Incremento implementado:** `eleicoes cobertura --output outputs/2026 --limiares 50 80 95`. A saída padrão é `outputs/2026/cobertura/`; `--dest` escolhe uma pasta nova. Os testes distinguem ausência de zero publicado, conferem os três grupos e seus denominadores, medidas não finitas/fora do intervalo, grupos vazios, diferenças em pp e contagens CSV/Parquet. A análise é descritiva e não atribui representatividade automaticamente às coortes.

## 3. Nulos técnicos, versões e esclarecimento documental

**Pergunta:** qual documento ou classificação oficial explica a diferença nominal de 5.246 votos nas 2.148 unidades município/zona do primeiro turno?

**Entrega preparatória:** inventário por unidade/candidato/turno, categorias, gerações e arquivos; reprodução da compensação aritmética; lista de documentos oficiais consultados; questões ainda sem resposta.

**Execução:** procurar versões compatíveis e documentos oficiais sobre destinação/categorias. Preservar os arquivos obtidos, a data da consulta e os hashes. Uma nova versão será comparada à anterior e não a substituirá. Incluir a situação das seções sem comparecimento quando houver documentação específica.

**Aceitação:** separar correspondência aritmética, documento encontrado e explicação jurídica/operacional confirmada. Concordância de números ou busca sem resultado não encerra a explicação. Solicitações formais ou contatos dependem de instrução expressa do usuário.

**Commits previstos:** ferramenta de dossiê e testes; fontes/documentos obtidos; relatório da conferência. Publicar pendências quando a explicação não puder ser determinada.

**Primeiro passo implementado:** `eleicoes dossie --output outputs/2026 --data data`, com saída separada em `dossie_categorias/`. O [método do dossiê](DOSSIE_CATEGORIAS.md) descreve parcelas, partições, datas, seleção e validação. A pesquisa externa e a confirmação jurídica/operacional permanecem pendentes; não são realizadas pelo comando local.

**Execução conferida:** 12.584 unidades por turno, 90.236 linhas nominais preservadas e 2.231 casos detalhados. Foram reproduzidos os 5.246 votos nas 2.148 unidades e as contagens distintas de 42/83/576. As categorias concordaram com o detalhe original; 104 testes passaram. Código inicial em `efb3522` e distinção das duas conferências de comparecimento em `e253f71`. Resultados e limites no [dossiê publicado](DOSSIE_CATEGORIAS.md). A frente 3 permanece aberta para os passos de pesquisa e esclarecimento.

**Pesquisa documental realizada:** [norma e cadastro da candidatura 28](PESQUISA_CATEGORIAS.md), com seis fontes/capturas identificadas. O guia oficial e o art. 17 da Resolução 23.677/2021 foram confrontados com a situação Renúncia do registro presidencial de ID 280002554479. A hipótese é compatível com as quantidades; o processo indicado não pôde ser consultado integralmente por indisponibilidade/CAPTCHA. O ato e sua eficácia temporal, a situação da chapa e o vínculo com as versões do SISTOT continuam pendentes. Relatório complementar em HTML/PDF, 113 testes aprovados e referência preservada. Esta pesquisa não encerra a frente 3.

## 4. Investigação nacional e mapas de mudanças

**Pergunta:** como as inversões e grandes reduções de vantagem se distribuem fora de RJ/MG?

**Método:** ampliar o inventário dirigido aos demais estados com critérios simétricos; manter margens entre finalistas e participação sobre todos os nominais como medidas distintas; incluir inversões e empates; preservar a análise RJ/MG existente.

**Mapas:** acrescentar mudança de margem e frequência de triagem por 1.000 seções elegíveis, com numerador, denominador e cobertura territorial. Municípios sem denominador adequado ficam identificados, não coloridos como taxa zero. Quantidade de eleitores, área geográfica e frequência de alertas são medidas diferentes.

**Aceitação:** somas nacionais e estaduais conferidas; população elegível explícita; mesmas regras nos dois sentidos; cobertura/cartografia preservadas; filtros e cores testados; nenhuma equivalência automática entre concentração de alertas e fraude.

**Commits previstos:** inventário nacional; agregações/taxas; mapas e relatórios; publicação de resultados completos com hashes.

**Entrega executada:** [investigação nacional](NACIONAL.md), em três etapas isoladas. Inventário em `f192ab6`, taxas/coortes em `d41deb6`, mapas e relatório em `cae77ef`. Foram preservadas as 499.248 seções e a cartografia de 5.571 unidades brasileiras. O resultado municipal completo registra 211 inversões para Lula e uma para Flávio no Brasil; no exterior, sete e três. A comparabilidade não foi presumida a partir dessas contagens. Há 1.356 prioridades por seção, até 50 por UF, sem reclassificação causal. A suíte tem 135 testes aprovados; a validação confere as tabelas, 84 escores com o método anterior e 33.467 condições da interface. A próxima implementação é a frente 5; a eficácia do ato na frente 3 continua pendente.

## 5. RDV, assinaturas e documentos da urna

**Pergunta:** uma conferência com documentos adicionais confirma os números dos casos selecionados?

**Seleção proposta:** amostra de 10–20 casos prioritários após a estabilidade e uma amostra de comparação sem alerta, estratificadas por território/tamanho/comparecimento quando possível. Registrar o procedimento de seleção antes da conferência.

**Etapas:** obter RDV e documentos disponíveis por seção; identificar formato/versão; preservar originais; conferir hashes e assinaturas com referências oficiais; recontar votos do RDV e comparar por cargo/categoria com BU; confrontar BU digital e impresso/imagem quando disponível. Tratar ausência ou incompatibilidade de formato como cobertura insuficiente.

O [TSE descreve possibilidades de auditoria](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria), incluindo assinaturas, BU impresso e recontagem do RDV. Os arquivos da urna não são, por si, uma fonte independente do equipamento. Não identificar eleitores, reconstruir escolhas individuais ou assumir cronologia de votos a partir do RDV.

**Aceitação:** cada caso com fontes, versão, resultado e limite da conferência; testes com arquivos controlados; documentação dos formatos suportados; causas e persistência só classificadas quando houver evidência suficiente. Não anunciar auditoria integral a partir de uma amostra.

**Commits previstos:** seleção e inventário; leitores/verificadores por formato; conferência da amostra; relatório com casos confirmados, limitados e pendentes.

## Registro de cada entrega

**Etapa 5 iniciada:** [protocolo e amostra](AUDITORIA.md) registrados antes da obtenção dos documentos dos casos: 12 prioridades e 12 controles, 48 unidades seção/turno, cinco regiões e exterior. Quatro testes verificam determinismo, controles, ausência de dados do segundo turno no pareamento e insuficiências explícitas. A seleção não representa auditoria executada.

Em cada frente, acrescentar: commit(s), comando executado, parâmetros, testes, arquivos produzidos, resultados, limitações, pendências e próxima decisão. Atualizar o estado na tabela somente com base nesses registros. A referência atual continua verificável enquanto os novos estudos são produzidos.

### Primeira rodada concluída

- Roteiro: `e4b7222`.
- Implementação de estabilidade: `6ff5db4`.
- Implementação de cobertura: `fa0392a`.
- Leitores e validação independente: `7428437`.
- Execução nacional e conferências: [resultados incrementais](RESULTADOS_INCREMENTAIS.md).
- Estabilidade: referência de 30 reproduzida nas 28 UFs; universo comum de 428.521 seções; sensibilidade relevante do topo dos rankings.
- Cobertura: 499.248 unidades fechadas em três grupos; perfis, cobertura municipal/UF e ausências explicitados.
- Próxima frente de trabalho: dossiê de categorias/versões, preservando a distinção entre compensação aritmética e explicação documental confirmada.
