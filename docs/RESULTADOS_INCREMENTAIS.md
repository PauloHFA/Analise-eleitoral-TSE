# Primeira rodada: estabilidade e cobertura

Execução nacional de **3 de novembro de 2026**, sobre os arquivos locais. Os dados, as fichas e os relatórios de referência foram preservados; estes estudos são complementares. Métodos e próximas frentes: [roteiro de implementação](PROXIMAS_ETAPAS.md).

## 1. Quanto as prioridades dependem dos pares?

O estudo usou **428.571 seções elegíveis**. A referência de **30 pares reproduziu os escores e a seleção publicados em todas as 28 UFs**, incluindo o exterior (`ZZ`). Os 15 primeiros pares da referência formaram a configuração menor; a configuração de 50 preservou os 30 originais e acrescentou vizinhos do primeiro turno, com prioridade municipal e complemento na UF.

As 50 unidades elegíveis do exterior não dispõem de outras 50 unidades na mesma UF: o próprio alvo é excluído. Por isso, o universo comum às três configurações tem **428.521 seções**, todas no Brasil. Falta de pares não foi tratada como ausência de alerta.

| Pares | Unidades com pares suficientes, Brasil + exterior | Na triagem, universo disponível | Na triagem, universo comum |
| --- | --- | --- | --- |
| 15 | 428.571 | 83.997 | 83.983 |
| 30 | 428.571 | 63.809 | 63.796 |
| 50 | 428.521 | 59.045 | 59.045 |

O critério absoluto de 10 pp ou passagem a zero permanece fixo. Mudam os pares e os escores robustos. As contagens não são quantidades de irregularidades.

### A ordem dos primeiros casos é sensível

| Comparação | Casos em comum entre os 100 primeiros | Retenção de uma lista de 100 |
| --- | --- | --- |
| 15 × 30 pares | 8 | 8% |
| 15 × 50 pares | 6 | 6% |
| 30 × 50 pares | 18 | 18% |

**Isso mede a composição do topo do ranking. Não significa que os demais casos deixaram de ter alerta.** Um caso pode continuar selecionado e apenas ocupar outra posição. Os limites de 25 e 50 casos e os índices de Jaccard estão no relatório completo.

| Quantas configurações selecionam a seção? | Seções no universo comum |
| --- | --- |
| Nenhuma | 339.256 |
| Uma | 27.277 |
| Duas | 6.417 |
| As três | 55.571 |

### Como usar esse resultado

A seleção e a ordem das prioridades devem ser consideradas separadamente. Não recomendamos escolher casos para auditoria somente pela maior posição no ranking original. A estabilidade entre configurações, a magnitude absoluta e a situação documental devem acompanhar a prioridade.

O estudo também identifica quando o MAD do indicador de maior afastamento fica abaixo da escala de uma unidade no numerador. Esse diagnóstico não altera os critérios nem estima a probabilidade de irregularidade. Os arquivos preservam mudanças em pp, quantidades dos dois turnos, denominadores, mediana, MAD, pares e posições.

Entregas: [relatório de estabilidade](../outputs/2026/estabilidade/relatorio.html), [resumo e hashes](../outputs/2026/estabilidade/resumo.json), [primeiros 100 por configuração](../outputs/2026/estabilidade/top100.csv) e [dicionário](../outputs/2026/estabilidade/dicionario.csv). Tabelas completas em CSV/Parquet na pasta do estudo e no pacote publicado.

## 2. Quem ficou fora da comparação?

Os grupos são mutuamente exclusivos:

| Universo | Elegíveis estatísticas | Comparáveis pequenas | Sem comparação territorial | Total |
| --- | --- | --- | --- | --- |
| Brasil | 428.521 | 568 | 68.808 | 497.897 |
| Exterior | 50 | 27 | 1.274 | 1.351 |
| Total | 428.571 | 595 | 70.082 | 499.248 |

Assim, **429.166 comparáveis = 428.571 elegíveis + 595 comparáveis pequenas**. A categoria pequena do inventário completo se sobrepõe às exclusões e não deve ser somada a esses três grupos como uma quarta categoria.

### Cobertura das unidades municipais brasileiras

O denominador é a quantidade de seções observadas em cada unidade municipal, e não votos ou eleitores. Há 5.571 unidades municipais brasileiras na base, incluindo unidades especiais.

| Limite de cobertura | Unidades abaixo do limite: comparação territorial | Unidades abaixo do limite: elegibilidade estatística |
| --- | --- | --- |
| 50% | 38 | 39 |
| 80% | 851 | 875 |
| 95% | 3.933 | 3.968 |

Os limites são descritivos, não uma classificação automática de qualidade. O exterior tem quadros separados para suas 186 unidades municipais/localidades na classificação do TSE.

### Perfis do primeiro turno — Brasil

Medianas por seção, sem ponderação. Cada medida tem cobertura e quartis próprios nos arquivos completos.

| Medida | Elegíveis | Sem comparação territorial |
| --- | --- | --- |
| Eleitorado apto | 325 | 339 |
| Comparecimento, quantidade | 256 | 268 |
| Comparecimento sobre aptos | 79,66% | 80,00% |
| Participação de Lula na soma nominal | 42,64% | 42,69% |
| Participação de Flávio na soma nominal | 48,32% | 47,84% |

**Proximidade entre medianas nacionais não demonstra representatividade.** Composição territorial e diferenças locais podem permanecer. O estudo oferece perfis por UF e distribuição geográfica dos grupos para aprofundamento. As diferenças entre medianas de taxas são em pp entre grupos no primeiro turno; não são mudanças entre turnos.

Ausências, valores não finitos e valores fora do intervalo foram contados separadamente. Zero publicado permanece zero conhecido; grupo sem medidas utilizáveis não recebe mediana zero. Coberturas ponderadas das medidas usam somente as somas utilizáveis disponíveis no inventário e não substituem a totalização oficial.

Entregas: [relatório de cobertura](../outputs/2026/cobertura/relatorio.html), [resumo e hashes](../outputs/2026/cobertura/resumo.json), [perfis completos](../outputs/2026/cobertura/perfis.csv), [diferenças por grupo/UF](../outputs/2026/cobertura/diferencas.csv) e [cobertura por UF](../outputs/2026/cobertura/resumo_uf.csv). O inventário individual mantém o motivo original da comparação.

## 3. Validação e reprodução

- As entradas foram identificadas por SHA256 e conferidas novamente após cada execução.
- A configuração de 30 pares foi comparada à referência em todas as UFs.
- Os conjuntos de pares, ausência do próprio alvo, unicidade, tamanhos e prefixos aninhados foram conferidos nas tabelas produzidas.
- Grupos, cobertura, disponibilidades e rankings no universo comum foram conferidos.
- CSV e Parquet foram lidos com tipos, aspas e política de vazios explícitos, comparando quantidade e dois checksums agregados de linhas. Aspas raras não dependem da inferência da amostra inicial do leitor CSV.
- A suíte cobre também UF sem pares suficientes, MAD zero/pequeno, listas vazias, grupos sem dados, valores inválidos e preservação das entradas.
- Validação final: **92 testes aprovados**, validação geral da entrega e conferência independente dos dois estudos. O validador também reproduziu a ordem da referência no universo comum e as interseções das listas prioritárias.

```powershell
.\.venv\Scripts\python.exe -m eleicoes estabilidade --output outputs/2026 --pares 15 30 50
.\.venv\Scripts\python.exe -m eleicoes cobertura --output outputs/2026 --limiares 50 80 95
.\.venv\Scripts\python.exe scripts/validar_incrementos.py outputs/2026
```

Os comandos recusam uma pasta de saída já preenchida; use `--dest` para outra execução. As entradas numéricas permanecem nos Parquets de referência. O PDF e a síntese de referência são protegidos por hash, mas não são usados para recalcular os escores.

Tabelas completas: [release estabilidade-cobertura-v1](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/estabilidade-cobertura-v1). Extrair os pacotes na raiz do clone. Versões, conteúdo e SHA256 por arquivo constam do manifesto da publicação. Registros: [testes incrementais](../outputs/logs/testes-incrementos.log) e [validação dos estudos](../outputs/logs/validacao-incrementos.log).

O [manifesto dos pacotes](incrementos-publicados.json) identifica os arquivos completos e os commits usados no cálculo. Os leitores do projeto declaram delimitador vírgula, aspas/escape duplos e tratamento de campos vazios; não dependem da inferência de aspas a partir das primeiras linhas.

## 4. O que continua pendente

O esclarecimento jurídico/operacional dos nulos técnicos, a expansão dirigida nacional/mapas e a conferência de RDV/assinaturas/documentos continuam nas frentes 3–5 do roteiro. A primeira rodada não realizou esses procedimentos e não encerra a investigação das causas ou da persistência de divergências.
