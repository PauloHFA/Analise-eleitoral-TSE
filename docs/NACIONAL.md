# Investigação nacional de mudanças e mapas

Etapa 4 do [roteiro](PROXIMAS_ETAPAS.md). Amplia a investigação dirigida a todas as UFs e mantém o exterior separado. Os relatórios, tabelas, mapas e fichas anteriores são preservados. Não realiza nova ingestão nacional.

## Resultados da execução — 03/11/2026

| Universo / medida | Resultado |
| --- | --- |
| Seções observadas | 499.248 |
| Locais observados | 94.343 |
| Unidades municipais, Brasil + exterior | 5.757 |
| UFs, incluindo ZZ | 28 |
| Seções territorialmente comparáveis | 429.166 |
| Seções elegíveis para triagem | 428.571 |
| Alertas da triagem original | 63.809 |
| Cartografia brasileira preservada | 5.571 unidades, sem novo vínculo ou polígono faltante |
| Lista nacional de prioridades | 1.356 seções; até 50 elegíveis por UF |

### Inversões entre os dois finalistas

| Universo | Flávio → Lula | Lula → Flávio | Empates no 1º | Empates no 2º |
| --- | --- | --- | --- | --- |
| Brasil, 5.571 unidades municipais | 211 | 1 | 2 | 1 |
| Exterior, 186 unidades na classificação TSE | 7 | 3 | 1 | 0 |

São contagens do resultado territorial completo com margens disponíveis, sem selecionar apenas municípios comparáveis. No Brasil, **72 das 211 inversões para Lula têm composição e aptos compatíveis pelos critérios estritos da referência; 139 têm comparação territorial limitada**. A inversão para Flávio é territorialmente comparável. A restrição não apaga o resultado municipal publicado; exige cuidado para atribuir a mudança à mesma composição de seções e eleitorado. Cobertura das coortes é publicada nos dois turnos.

O inventário reproduz **76 inversões para Lula em MG e nove no RJ**. O sentido inverso no Brasil ocorre em **Uirapuru/GO**: Flávio 854 → 1.087 votos; Lula 930 → 1.069. A margem de Flávio passa de −4,26 para +0,83 pp. Lula ganhou votos absolutos e perdeu a liderança relativa entre finalistas. Há sete seções na coorte e 70% de cobertura elegível; a taxa não recebe cor no limite padrão de 30 elegíveis/80% de cobertura. Nenhum desses fatos determina irregularidade.

| UF | Flávio → Lula | Lula → Flávio |
| --- | --- | --- |
| AL | 7 | 0 |
| AM | 3 | 0 |
| AP | 2 | 0 |
| CE | 1 | 0 |
| ES | 3 | 0 |
| GO | 14 | 1 |
| MA | 1 | 0 |
| MG | 76 | 0 |
| MS | 4 | 0 |
| MT | 2 | 0 |
| PA | 5 | 0 |
| PR | 20 | 0 |
| RJ | 9 | 0 |
| RN | 1 | 0 |
| RS | 19 | 0 |
| SC | 1 | 0 |
| SP | 32 | 0 |
| TO | 11 | 0 |
| ZZ | 7 | 3 |

As demais UFs não têm inversão municipal desse tipo na cópia analisada. A tabela [contagens](../outputs/2026/nacional/inventario/contagens.csv) inclui todos os estados, os quatro níveis e a sensibilidade de 5/10/15 pp. Os padrões selecionados somam 249 unidades municipais no Brasil e 23 no exterior; essa união inclui inversões, reduções de vantagem de 10 pp e mudança de condição de empate, não somente viradas.

### Taxas e exibição no mapa

| Universo | Elegíveis | Alertas originais | Por 1.000 elegíveis |
| --- | --- | --- | --- |
| Brasil | 428.521 | 63.796 | 148,87 |
| Exterior | 50 | 13 | 260,00 |

O exterior tem apenas 50 elegíveis em 1.351 seções observadas, cobertura de 3,70%. A taxa descritiva não torna esse subconjunto representativo. No Brasil, a cobertura elegível é de 86,07% das 497.897 seções observadas.

Nos limites padrão, **2.397** unidades brasileiras recebem cor de taxa e **3.174** ficam identificadas sem cor: quatro sem elegíveis, 2.876 abaixo da quantidade mínima e 294 abaixo da cobertura mínima, depois de separar os grupos anteriores. Os valores brutos permanecem nas tabelas. Cinza não significa ausência de alerta.

### Conferências e validação

- Os 112 somatórios completos disponíveis, por UF/Brasil, turno e finalista, concordaram entre seção/local/município/UF e fonte nominal oficial. Quatro comparações do exterior ficaram limitadas por total estadual indisponível; não foram transformadas em totais zero.
- Foram agregadas 5.731.614 linhas da conferência BU armazenada, sem apontamento de diferença nessas linhas. São registros, não pessoas ou urnas distintas, e isso não certifica completude ou causa das mudanças.
- A igualdade tipada completa dos **12 pares CSV/Parquet** foi conferida nos dois sentidos. A seleção original foi preservada e 84 escores de margem, três por UF, reproduziram a implementação anterior.
- O mapa passou por **33.467 verificações** de cores, turnos, UFs, padrões, limites, ausência e teclado; geometrias/códigos/limites foram comparados à referência. Houve inspeção visual em Chrome headless dos modos de margem e taxa.
- O PDF complementar tem **cinco páginas e dez marcadores**, com conteúdo, margens e orientação conferidos e páginas inspecionadas visualmente.
- A suíte passou com **135 testes**. Os 578 artefatos do inventário anterior preservaram seus SHA256. HTML/PDF/síntese de referência e a investigação RJ/MG mantiveram seus hashes.
- Em 07/11/2026, após uma revisão apenas editorial dos relatórios principais, os hashes desses dois arquivos nas três etapas nacionais foram atualizados com histórico do valor anterior. Nenhuma tabela, síntese ou indicador nacional foi recalculado; a validação completa voltou a conferir.

### Acesso aos resultados

- [Relatório nacional HTML](../outputs/2026/nacional/mapas/relatorio.html), [PDF](../outputs/2026/nacional/mapas/relatorio.pdf) e [mapa interativo](../outputs/2026/nacional/mapas/mapa.html).
- [Contagens por UF/nível](../outputs/2026/nacional/inventario/contagens.csv), [taxas por UF](../outputs/2026/nacional/taxas/ufs.csv), [Brasil/exterior](../outputs/2026/nacional/taxas/regioes.csv) e [somatórios](../outputs/2026/nacional/taxas/reconciliacao.csv).
- [Prioridades por seção](../outputs/2026/nacional/mapas/prioridades.csv), [dicionário](../outputs/2026/nacional/taxas/dicionario.csv), [validação](../outputs/logs/validacao-nacional.log) e [testes](../outputs/logs/testes-nacional.log).

As tabelas completas e o JSON geográfico do novo mapa são distribuídos no [pacote nacional-v1](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/nacional-v1), com [manifesto e hashes por arquivo](nacional-publicado.json). Extrair na raiz do clone. As capturas e releases anteriores não são substituídas.

## Inventário nacional

```powershell
.\.venv\Scripts\python.exe -m eleicoes nacional --output outputs/2026 --etapa inventario
```

A saída padrão é `outputs/2026/nacional/inventario/`. Uma saída preenchida é recusada; `--dest` permite outra pasta. As entradas são os quatro níveis de indicadores, os candidatos e o manifesto já existentes.

As regras são as da investigação dirigida: margem `100 × (Flávio − Lula)/(Flávio + Lula)` em cada turno; inversão com sinais estritamente opostos; empate entre finalistas com soma positiva; reduções de margem de 5/10/15 pp para quem liderava no primeiro turno. A perda relativa é separada da variação em votos absolutos. O denominador da margem não inclui os eliminados, mas suas quantidades e as participações sobre todos os nominais são preservadas.

Os indicadores são calculados por seção, local, município e UF. O inventário completo conserva as unidades sem comparação territorial válida e as pequenas, identificadas como tal. A seleção de padrões descritivos não transforma essas unidades em elegíveis para triagem estatística.

Na análise de margem por seção, reutilizam-se os 30 pares já publicados, sem selecionar novos vizinhos pelo segundo turno. São conferidas quantidade, unicidade, ausência do próprio alvo, UF e elegibilidade. Mediana e MAD da mudança de margem geram escore absoluto simétrico. MAD ≤ `1e-9`, falta de pares ou indicador indisponível produzem comparação inconclusiva, não ausência demonstrada de mudança ou irregularidade.

`reference_alert` preserva a triagem combinada original. `margin_robust_flag` é outro diagnóstico e não a substitui. Os IDs dos pares continuam na fonte identificada por hash; a exportação evita duplicá-los em todo o inventário.

Cada etapa registra fontes e hashes, estado de execução e código. RJ/MG serão conferidos contra o resultado dirigido anterior. Mudanças agregadas não identificam transferências individuais nem demonstram fraude.

Se apenas o HTML/PDF principal mudar editorialmente, sem alteração das entradas analíticas, atualize as referências das etapas e os resumos dependentes sem recalcular indicadores:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\atualizar_proveniencia_nacional.py --output outputs\2026
.\.venv\Scripts\python.exe -X utf8 scripts\validar_nacional.py --output outputs\2026
```

O comando recusa diferenças em qualquer entrada além dos dois relatórios e dos resumos de etapas anteriores alterados por essa mesma atualização. Confere os manifestos de saída antes de escrever e preserva hashes anteriores no campo `provenance_refresh`. Se mudar uma entrada analítica, a etapa correspondente precisa ser regenerada em vez de ter sua proveniência reescrita.

## Taxas, coortes e somatórios

```powershell
.\.venv\Scripts\python.exe -m eleicoes nacional --output outputs/2026 --etapa taxas --min-elegiveis 30 --cobertura-minima 80
```

A saída é `outputs/2026/nacional/taxas/`. A taxa é `1.000 × seções elegíveis com alerta original / seções elegíveis`, agregando contagens antes de dividir. Não usa eleitores, votos ou área no denominador e não é a média das taxas municipais. A cobertura é a proporção de seções elegíveis entre as observadas. Sem elegíveis, a taxa é ausente.

A apresentação padrão requer ao menos 30 seções elegíveis e 80% de cobertura elegível. Esses limites operacionais facilitam a leitura; não são um teste de validade ou uma estimativa de precisão. As taxas descritivas integrais permanecem na tabela, inclusive abaixo dos limites; a coluna para colorir o mapa fica ausente e a razão é identificada.

Os totais das mesmas seções territorialmente comparáveis são publicados em campos `cohort_*`, incluindo as pequenas. Contagem zero de seções da coorte não transforma suas quantidades em votos zero. Uma soma exige todas as parcelas conhecidas. A cobertura por aptos, comparecimento e nominais é calculada para cada turno, sem substituir o resultado territorial completo.

Os somatórios de votação disponível por seção/local/município/UF são confrontados com a votação oficial nominal dos finalistas, por UF e no Brasil. Linhas ausentes e totais indisponíveis permanecem explícitos. Exterior e Brasil são separados. Essa conferência não presume mesma data de geração das fontes ou equivalência jurídica de todas as categorias. O quadro de BU descreve linhas disponíveis, sem certificar completude de todas as urnas.

## Mapas e relatório complementar

```powershell
.\.venv\Scripts\python.exe -m eleicoes nacional --output outputs/2026 --etapa mapas --min-elegiveis 30 --cobertura-minima 80
```

A saída é `outputs/2026/nacional/mapas/`. A cartografia e o vínculo TSE–IBGE vêm do mapa de referência identificado por hash, sem novo download ou associação de nomes. Exterior permanece nas tabelas.

O mapa tem três modos: liderança entre finalistas no turno escolhido; mudança da margem do segundo menos primeiro turno; e triagem original por 1.000 elegíveis. Azul indica Flávio e vermelho Lula nos modos eleitorais. Na mudança, a cor indica o sentido relativo, não necessariamente quem lidera ao final. A escala de mudança é simétrica fixa ±200 pp. A taxa usa roxo com escala fixa 0–1.000. As escalas não são recalculadas pela UF filtrada.

Branco representa zero conhecido nos modos de mudança/taxa; cinza indica indicador indisponível ou taxa fora dos limites de exibição. No modo de liderança, cinza também identifica empate. Os limites de quantidade/cobertura podem ser ajustados na interface; os valores descritivos permanecem íntegros. Filtros por UF e padrão incluem as inversões nos dois sentidos, reduções de vantagem e mudança de empate.

Ao clicar ou selecionar um território pelo teclado, o painel mostra votos dos dois turnos, quantidades nominais, margem, comparecimento/aptos, variação absoluta, numerador/denominador de alertas e cobertura da coorte. O HTML funciona localmente, sem dependências externas. O PDF complementar usa mapas estáticos com a mesma orientação e regra de cor.

`prioridades.csv/parquet` contém até 50 seções elegíveis com padrão selecionado por UF, nos dois sentidos, ordenadas por escore robusto da margem, mudança absoluta e chave geográfica. Não é uma nova classificação de fraude; dispersão, magnitude e evidência documental precisam acompanhar a prioridade. As fichas anteriores continuam preservadas.

## Fechamento desta etapa

Conferir artefatos, apresentar os resultados nacionais e publicar tabelas completas com hashes.
