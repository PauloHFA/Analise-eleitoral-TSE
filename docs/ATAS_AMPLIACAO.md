# Pesquisa de atas — ampliação às 28 unidades

A segunda rodada acrescentou **22 consultas individuais**, preservando as seis iniciais. Todas as **28 unidades seção/turno** com apontamentos agora têm busca individual registrada. **Nenhuma ata de mesa receptora ou registro específico de atendimento/substituição foi obtido.** Cobertura de busca não é cobertura documental, busca exaustiva ou confirmação da causa.

[HTML atualizado](../outputs/2026/auditoria/atas_ampliacao/relatorio.html) · [PDF](../outputs/2026/auditoria/atas_ampliacao/relatorio.pdf) · [síntese](../outputs/2026/auditoria/atas_ampliacao/resumo.json) · [28 casos](../outputs/2026/auditoria/atas_ampliacao/casos.csv) · [28 consultas](../outputs/2026/auditoria/atas_ampliacao/buscas.csv).

## Cobertura e resultado

| Medida | Primeira rodada preservada | Consolidação ampliada |
| --- | --- | --- |
| Unidades com busca individual | 6 | 28 de 28 |
| Unidades sem busca individual | 22 | 0 |
| Consultas individuais registradas | 6 | 28: seis anteriores e 22 novas |
| Resultados de busca | 18 | 55: 18 anteriores e 37 novos |
| Capturas/URLs de contexto catalogadas | 12 | 34, uma limitada a navegação/cookies |
| Atas/atendimentos específicos obtidos | 0 | 0 |
| Apontamentos preservados | 33 | 33, em 28 unidades seção/turno |
| Fichas / minutas locais | 28 / 28 | 28 / 28 na nova versão, sem envio |

As 22 consultas novas são todas relativas ao segundo turno da amostra. Foram usadas cidade, zona, seção, data-alvo e ano, com restrição ao domínio do TRE da UF; para o exterior, ao TRE-DF. **17 consultas retornaram resultados e cinco não retornaram resultados.** Essas cinco são a seção 100 da zona 351 de São Paulo, as duas unidades de Boston do segundo turno, Praia e Zagreb. Não retornar resultado nesse mecanismo e nessa consulta não demonstra inexistência de documento ou de ocorrência.

O executor registrou **34 tentativas para concluir as 22 consultas novas**: 12 falharam e foram retomadas, preservando o histórico. Falha de execução não foi contada como consulta sem resultado. Esses números se referem às chamadas registradas pelo executor desta rodada; uma consulta exploratória de diagnóstico não integra esse contador. Não se atribuiu causa técnica às falhas do CLI sem evidência suficiente.

## Natureza do material encontrado

Os resultados novos incluem índices de atos normativos e licitações, legislação geral, cadastros de seções/locais e notícias sobre preparação, transporte, consulta de locais e testes de autenticidade. Esses materiais foram classificados segundo sua natureza e pertinência; **não foi feito exame exaustivo de cada ato listado nos índices**.

Um resultado do TRE-SP trata de teste de autenticidade com referência à seção 206 da zona 315 de Osasco. Ele não é registro de atendimento da seção 491 da zona 2 pesquisada. A captura de uma notícia do TRE-RJ sobre urnas a auditar contém apenas navegação/cookies, sem corpo útil para confronto. Foi classificada como **captura limitada**, sem atribuir seu conteúdo ao caso.

As fontes gerais da primeira rodada permanecem preservadas. O boletim do TRE-BA sobre substituições estaduais no primeiro turno continua sem vínculo documental com a seção de Campo Formoso. Atas de julgamento, normas e notícias gerais não substituem atas da mesa receptora ou registros individualizados de atendimento.

## Método e preservação

1. Ler a tabela de casos da primeira rodada por hash; selecionar exclusivamente as 22 unidades sem busca individual. Preservar os seis casos/consultas anteriores e todos os 33 apontamentos.
2. Executar consultas públicas com limite de três resultados e captura textual. O CLI iniciou com duas tarefas; após falhas, a execução foi retomada em lotes sequenciais, sem repetir consultas já concluídas.
3. Manter plano, resultados finais, tentativas e revisão em arquivos distintos. A retomada exige o mesmo plano/referência e confere os hashes das capturas concluídas. Uma captura alterada, execução incompleta ou resultado final incompatível com o histórico impede a consolidação.
4. Distinguir sucesso com resultados, sucesso sem resultados e falha. Quando o CLI retorna `No results found` com exit 0 sem arquivo, o projeto grava um envelope vazio identificado como produzido pelo projeto; ele não é apresentado como resposta JSON original do provedor. Exit diferente de zero continua sendo falha.
5. Revisar os 37 resultados novos, registrando tipo, escopo e decisão. Um resultado que exija exame documental específico não pode ser promovido automaticamente a contexto sem confronto; a preparação exige revisão correspondente para cada resultado.
6. Deduplicar apenas a catalogação de capturas com **mesma URL e mesmo hash de conteúdo**, sem sobrescrever capturas anteriores. Nesta execução há 34 capturas e 34 URLs distintas. O hash identifica a extração textual, não os bytes HTTP originais ou autenticação independente.
7. Preservar a captura v1 sob `data/auditoria/atas/v1/`; a v2 mantém cópias sob `anterior/`, novas capturas sob `novas/`, hashes próprios e vínculo ao manifesto da v1. As saídas novas ficam em `auditoria/atas_ampliacao/`; as primeiras fichas e minutas não são substituídas.
8. Aplicar os mesmos critérios de [confronto específico](ATAS.md): documento de tipo adequado, identidade exata de ano/turno/UF/município/zona/seção, apontamento, localização no documento e revisão registrada. Nenhuma evidência específica foi acrescentada. `causes_confirmed` continua `null`, sem confirmação causal automatizada.

São sete pares CSV/Parquet: os seis anteriores (`casos`, `confronto`, `buscas`, `resultados_busca`, `fontes` e `documentos_necessarios`) e `tentativas_busca`, com as 34 tentativas do executor e seus estados. As 56 necessidades documentais são dois tipos a procurar por unidade; não são 56 documentos existentes ou recebidos. As 28 minutas são locais, não enviadas. Não foram publicados logs brutos, dados pessoais, capturas integrais ou escolhas individuais de voto.

## Reprodução

```powershell
# Pasta nova para capturas; chamadas públicas via CLI Firecrawl
.\.venv\Scripts\python.exe scripts/pesquisar_atas_ampliacao.py --output outputs/2026 --dest .firecrawl/atas-ampliacao-v1
# Retomada conferida: somente consultas não concluídas, lotes de seis
.\.venv\Scripts\python.exe scripts/pesquisar_atas_ampliacao.py --resume --workers 1 --batch-size 6
# Após revisão dos resultados em revisao.json, preserva uma captura v2 nova
.\.venv\Scripts\python.exe scripts/preparar_ampliacao_atas.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --data data --etapa atas-ampliacao
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 scripts/validar_atas.py --ampliacao
.\.venv\Scripts\python.exe scripts/preservar_documentacao.py --check
```

A consulta exige o CLI configurado; obtenção e processamento são etapas distintas. A revisão é efetiva triagem assistida, não uma classificação produzida automaticamente só por conter “ata” ou números iguais. O comando de preparação não executa buscas nem envia pedidos. Preparação e geração recusam sobrescrever pastas preenchidas; `--dest` permite nova saída. Para reproduzir exatamente os resultados, usar as capturas preservadas e seus hashes; novas consultas podem retornar material diferente.

A validação da primeira rodada corresponde ao commit/release daquela rodada. Sua preservação nesta versão é verificada por manifestos e hashes, inclusive as 28 fichas e 28 minutas originais; a mudança do código não reescreve o resultado anterior.

**Validação executada:** 237 testes aprovados, incluindo nove novos de cobertura, falhas, resultados vazios, retomada e captura alterada; 543 avisos de depreciação ASN.1. Sete pares CSV/Parquet comparados integralmente com tipos; 28 fichas/28 minutas, 124 links locais e 3.132 condições dos filtros verificados. PDF de cinco páginas/seis marcadores, conteúdo/margens validados; quatro páginas renderizadas, HTML e uma ficha inspecionados. Onze manifestos amostrais anteriores, as 56 fichas/minutas da primeira rodada e os 578 artefatos originais preservados. Registros em [outputs/logs](../outputs/logs/README.md).

[Pacote público separado](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/atas-pesquisa-ampliada-v1), com metadados, tabelas, fichas/minutas e hashes. Não contém capturas integrais de páginas ou logs brutos. Extrair na árvore das entregas anteriores para resolver links cruzados; a primeira release não foi substituída.

## Próxima dependência

**A pesquisa individual desta rodada cobre todo o inventário; a obtenção documental continua pendente.** Para avançar no confronto, são necessárias atas e registros específicos, ou respostas oficiais com a abrangência da consulta documentada. As minutas permanecem disponíveis para revisão. Nenhum contato, pedido de acesso ou protocolo foi enviado. Não se apresenta ausência de obtenção como ausência de falha ou como prova de irregularidade.

O fluxo local para preservar e confrontar documentos recebidos está descrito em [ATAS_CONFRONTO.md](ATAS_CONFRONTO.md). Ele não envia pedidos nem autentica automaticamente arquivos; sem material recebido, não gera novo achado. PKIX/LCR, CEPESC, perfil/layout oficial, BU de origem independente e ato individual dos nulos técnicos continuam frentes distintas. Repetir consultas genéricas sem novas fontes não encerra essas pendências.
