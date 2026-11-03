# Dossiê local de categorias e versões

Esta entrega implementa o primeiro passo da frente 3: organizar as evidências já disponíveis por município, zona e turno. A pesquisa de documentos oficiais e a explicação jurídica/operacional das categorias continuam pendentes. Não houve nova ingestão nacional ou contato externo.

## Pergunta e escopo

Quais parcelas sustentam a diferença nominal já identificada, em quais unidades ela ocorre e quais versões dos arquivos foram comparadas?

O inventário inclui todas as unidades das tabelas de referência. Os casos com apontamentos recebem detalhes no HTML, com valores, candidatos afetados, gerações e pendências. Os dois turnos permanecem nas tabelas, inclusive quando o apontamento ocorre somente em um deles. Brasil e exterior têm identificação própria.

## Fontes e método

1. Ler os Parquets de reconciliação nominal, categorias, aptos/comparecimento e seções por turno. Preservar valores, ausências, zeros implícitos e situações originais. Recusar chaves duplicadas nas tabelas já agregadas.
2. Relacionar os quatro arquivos eleitorais de origem ao manifesto da análise e conferir seus SHA256. Não escolher silenciosamente outra versão ou presumir que a URL atual entregue os mesmos bytes.
3. Ler o detalhe oficial original de município/zona, selecionando Presidente. Preferir o CSV nacional quando houver também arquivos estaduais, para evitar dupla contagem. Preservar todos os campos, membro do ZIP e linha final de cada registro no CSV.
4. Manter as partições de voto em trânsito e conferir a unicidade dentro de cada partição. Duplicidades ou múltiplas identificações de eleição na mesma unidade/turno bloqueiam a confirmação das quantidades originais. Valores negativos, ausentes ou não inteiros permanecem indisponíveis. Uma soma exige todas as parcelas conhecidas.
5. Confrontar as categorias originais com as categorias publicadas. Recalcular a correspondência aritmética: excesso nominal igual aos nulos técnicos; diferença nos nulos totais igual ao valor oposto; nulos das seções iguais aos regulares oficiais; brancos e comparecimento concordantes. Exigir cobertura nominal compatível e correspondência entre as diferenças por candidato e a diferença por categoria.
6. Examinar diferenças por candidato antes de somar. Valores de sinais contrários que se compensem no total continuam sendo apontamentos; soma líquida zero não encerra o caso.
7. Separar lacunas nominais com comparecimento zero conhecido nas duas fontes e zero nominal oficial conhecido. Contar separadamente unidades geográficas município/zona, unidades por turno e linhas por candidato. Não imputar votos ausentes nem interpretar ausência como falha de urna.
8. Preservar todas as gerações distintas informadas. Comparar datas no formato dia/mês/ano, sem inferir fuso; marcar datas ausentes/inválidas. Data de geração, última totalização, modificação remota e obtenção são conceitos diferentes. Datas distintas não demonstram a causa das diferenças.
9. Exportar tabelas completas e relatório HTML com filtros locais de UF, turno, situação e município/zona. Conferir novamente os hashes das entradas, dos arquivos originais e do relatório/PDF/síntese de referência.

## Classificações

| Resultado no dossiê | Alcance |
| --- | --- |
| Correspondência aritmética com nulos técnicos | As parcelas locais conferem, incluindo o detalhe oficial original. A causa permanece não investigada neste incremento. |
| Lacuna nominal com comparecimento zero | A ausência nominal é compatível com os quantitativos conhecidos. O motivo da ausência permanece pendente. |
| Pendência de conferência | Alguma diferença, lacuna, conflito ou não reprodução exige revisão. |
| Concordante no escopo aritmético | As verificações quantitativas deste inventário não apontaram diferenças. Não é uma certificação de ausência de irregularidades. |

A classificação publicada está preservada em campo próprio. Explicação documental da causa e persistência permanecem como **não investigadas neste incremento**, inclusive para os casos aritmeticamente compatíveis. O dossiê não reconstitui a razão jurídica da destinação dos votos de uma candidatura.

`attendance_difference` compara a soma dos votos das seções com o comparecimento oficial. `detail_attendance_difference` compara as quantidades de comparecentes nos dois arquivos de detalhe. Os nomes são distintos porque os numeradores representam conferências diferentes.

## Reprodução

São necessários os Parquets de referência e os quatro arquivos eleitorais originais, nas versões do manifesto. Os ZIPs originais não integram as releases de tabelas derivadas; a rotina recusa versões ausentes ou com hash diferente. Não usa o banco DuckDB da ingestão e não acessa a rede.

```powershell
.\.venv\Scripts\python.exe -m eleicoes dossie --output outputs/2026 --data data
.\.venv\Scripts\python.exe scripts/validar_dossie.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe -m pytest -q
```

A saída padrão é `outputs/2026/dossie_categorias/`. Uma pasta já preenchida é recusada; para repetir, usar `--dest` com uma pasta nova. `estado_execucao.json` distingue execução incompleta e concluída.

## Entregas e validação

- `unidades.csv/parquet`: universo por município/zona/turno, parcelas, cobertura, versões e resultados da conferência.
- `nominais.csv/parquet`: todas as linhas de reconciliação por candidato, com campos adicionais de diagnóstico; valores e classificações de referência preservados.
- `categorias_originais.csv/parquet`: linhas presidenciais do detalhe oficial original e suas partições, sem descarte dos campos de quantidade.
- `resumo_uf.csv/parquet`: contagens por UF/turno, com identificação do exterior.
- `dicionario.csv/parquet`, `fontes.json`, `resumo.json`, `manifesto.json` e `relatorio.html`: definições, proveniência, contagens, hashes e leitura dos casos.

O validador compara o multiconjunto completo de cada CSV/Parquet com tipos e política de aspas/vazios explícitos, por `EXCEPT ALL` nos dois sentidos. Confere também a preservação de todas as linhas nominais originais, os hashes, os vínculos locais, a unicidade das âncoras de casos e a distinção das três unidades de cobertura.

Os testes controlados abrangem compensação entre candidatos, lacunas com comparecimento zero, partições de trânsito, duplicidades, categorias alteradas/ausentes, datas inválidas, preferência pelo CSV nacional, registros multilinha, escape de HTML e preservação das fontes.

## Próxima etapa

Pesquisar documentação oficial sobre categorias, datas de geração e versões compatíveis, registrando o que foi encontrado e o que permanece sem explicação. Esta entrega prepara as perguntas verificáveis; não antecipa a conclusão dessa pesquisa.
