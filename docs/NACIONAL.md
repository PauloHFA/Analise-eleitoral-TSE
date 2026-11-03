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

## Próximos incrementos desta etapa

1. Agregar numerador/denominador de alertas, cobertura municipal/UF, coortes das mesmas seções e somatórios entre níveis.
2. Gerar mapas próprios de mudança de margem e alertas por 1.000 seções elegíveis, com critérios explícitos de exibição e ausência.
3. Conferir artefatos, apresentar os resultados nacionais e publicar tabelas completas com hashes.
