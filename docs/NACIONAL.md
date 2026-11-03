# Investigação nacional de mudanças e mapas

Etapa 4 do [roteiro](PROXIMAS_ETAPAS.md). Amplia a investigação dirigida a todas as UFs e mantém o exterior separado. Os relatórios, tabelas, mapas e fichas anteriores são preservados. Não realiza nova ingestão nacional.

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
