# Atas e registros operacionais — pesquisa e dossiê

A etapa de pesquisa e organização documental foi executada. **O confronto específico das causas ainda não foi concluído:** nenhuma ata de mesa receptora ou registro individualizado de atendimento/substituição dos casos selecionados foi obtido nesta rodada. Não se transformou ausência de obtenção em comprovação de inexistência ou de regularidade.

[HTML e inventário](../outputs/2026/auditoria/atas/relatorio.html) · [PDF](../outputs/2026/auditoria/atas/relatorio.pdf) · [síntese](../outputs/2026/auditoria/atas/resumo.json) · [casos](../outputs/2026/auditoria/atas/casos.csv) · [situação dos apontamentos](../outputs/2026/auditoria/atas/confronto.csv).

## Universo e resultado

| Medida | Resultado | Alcance |
| --- | --- | --- |
| Inventário de origem | 33 apontamentos em 28 unidades seção/turno | Preservado integralmente da análise dos logs; 24 seções distintas |
| Seleção documental inicial | 6 unidades | Eventos adicionais ao nível ERRO; cinco prioridades amostrais e um controle |
| Buscas individuais registradas | 6, com 18 resultados | Município, zona, seção, data e ano nos termos de busca |
| Unidades sem busca individual nesta rodada | 22 | Não classificadas como buscas sem resultado |
| Fontes de contexto revisadas | 12 | Orientações, norma, notícia agregada, diretórios e páginas gerais; não são 12 atas |
| Evidências específicas dos casos | 0 | Nenhum confronto específico concluído |
| Fichas / minutas locais | 28 / 28 | Uma por unidade, sem envio automático |
| Necessidades documentais | 56 | Dois tipos a procurar por unidade; não documentos existentes ou recebidos |
| Confirmação das causas | Não realizada | Valor `null` na síntese, sem automatização de causalidade |

Foram pesquisadas individualmente: **Feijó/AC, zona 7, seção 47, segundo turno; Campo Formoso/BA, zona 53, seção 274, nos dois turnos; Barra do Garças/MT, zona 9, seção 369, primeiro turno; Guarapuava/PR, zona 43, seção 384, primeiro turno; Boston/ZZ, zona 1, seção 920, primeiro turno**. A escolha usa os apontamentos dos logs — conteúdo aninhado, identificadores, impressora, ligações, OpenSession e cronologia — e não uma conclusão de irregularidade.

As 22 unidades de acompanhamento continuam com os mesmos apontamentos. Ter uma ficha ou minuta gerada não significa ter realizado busca individual, obtido documento ou confirmado causa.

## O que as fontes encontradas permitem dizer

Uma busca sobre o segundo turno retornou o [boletim do TRE-BA sobre 60 substituições](https://www.tre-ba.jus.br/comunicacao/noticias/2026/Outubro/2deg-boletim-tre-ba-substitui-60-urnas-eletronicas-na-bahia). O texto refere-se ao **primeiro turno e ao estado**, sem identificar a seção selecionada. Ele não confirma troca de equipamento em Campo Formoso em qualquer turno, nem explica a composição de seus logs.

As [atas de julgamento do TSE](https://www.tse.jus.br/servicos-judiciais/atas-das-sessoes) também não são atas das mesas receptoras. Normas e explicações gerais não documentam o que ocorreu numa seção. O [TSE inclui a comparação de atas e arquivos digitais](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria) entre as possibilidades de auditoria; isso fundamenta o tipo de confronto proposto, sem confirmar seus resultados.

Os diretórios de [zonas eleitorais do Acre](https://www.tre-ac.jus.br/institucional/cartorios-eleitorais) e da [Zona do Exterior](https://www.tre-df.jus.br/servicos-eleitorais/zonas-eleitorais/zz-zona-exterior-endereco-e-telefones) foram preservados como rotas de acesso. **Nenhum pedido foi enviado.** Os 18 resultados das buscas têm decisão de uso registrada: os que não são fontes eleitorais oficiais não foram usados como evidência institucional dos casos.

## Método e critérios

1. Conferir o manifesto da etapa de logs e preservar todas as 33 linhas de apontamento. Relacioná-las às 28 unidades sem eliminar motivos ou trocar a amostra.
2. Separar as seis unidades da seleção inicial das 22 de acompanhamento. Registrar consultas exatas, captura, horário de gravação UTC, hash e resultados; uma busca registrada não é busca exaustiva.
3. Preservar capturas e metadados em `data/auditoria/atas/v1/`, com manifesto próprio. Os hashes identificam as extrações textuais Firecrawl, não os bytes HTTP originais nem autenticação independente da fonte. Conteúdo bruto de páginas e logs não é redistribuído.
4. Catalogar fontes de contexto com tipo e alcance. Notícias estaduais, norma, diretório, página geral e ata de julgamento não podem confirmar um caso individual por coincidência de palavras ou números.
5. Exigir, para confronto específico, tipo documental adequado (`ata_mrv`, `registro_atendimento` ou `registro_substituicao`), origem declarada em domínio eleitoral oficial e identidade exata de ano/turno/UF/município/zona/seção. Zeros à esquerda são normalizados; outro turno, ano ou seção não é aceito.
6. Exigir vínculo ao apontamento, localização verificável no documento, justificativa e revisão registrada. O manifesto e os metadados são pressupostos declarados: não substituem a inspeção do original e de sua proveniência.
7. Distinguir registro corroborado no escopo, divergência documental a revisar e evidência insuficiente. Corroboração de uma mensagem não explica automaticamente sua causa; divergência não vira persistência confirmada. O registro de evidências específicas está vazio nesta execução.
8. Gerar 28 fichas e 28 minutas, com identificação territorial e questões correspondentes aos apontamentos. Pedir ata e registros operacionais aplicáveis, sem solicitar dados pessoais de eleitores, biometria ou escolhas individuais. Minuta não é pedido protocolado.

As contagens de documentos necessários são uma lista de verificação. Não se presume que exista um atendimento para cada mensagem ERRO ou que cada necessidade corresponda a um arquivo distinto.

## Tabelas e reprodução

São seis pares CSV/Parquet: `casos`, `confronto`, `buscas`, `resultados_busca`, `fontes` e `documentos_necessarios`. As [evidências registradas](../outputs/2026/auditoria/atas/evidencias_registradas.json) estão separadas da pesquisa geral. `manifesto_fichas.json` preserva os 56 arquivos de fichas/minutas; o manifesto principal cobre as tabelas, relatório, síntese e o próprio manifesto de fichas.

```powershell
# Preserva as capturas já obtidas; não executa buscas ou envia pedidos
.\.venv\Scripts\python.exe scripts/preparar_pesquisa_atas.py --capturas .firecrawl --data data
# Reutiliza a etapa dos logs; não faz downloads
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --data data --etapa atas
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 scripts/validar_atas.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe scripts/preservar_documentacao.py --check
```

A preparação e a análise recusam pastas preenchidas. `--dest` muda a pasta de resultados; uma nova captura deve usar outra árvore `--data`. Para reproduzir exatamente esta pesquisa, são necessárias as capturas preservadas e seus hashes; novas buscas podem retornar conteúdo diferente. As consultas estão na tabela `buscas`, mas o comando de preparação não as reexecuta. O pacote público inclui metadados e resultados, sem textos integrais das capturas.

**Validação executada:** 228 testes aprovados, incluindo 17 novos, com 543 avisos de depreciação ASN.1. Seis pares CSV/Parquet comparados integralmente com tipos; 28 fichas e 28 minutas verificadas; 123 links locais e 3.132 condições dos filtros conferidos. O PDF tem cinco páginas/seis marcadores, com conteúdo/margens validados; quatro páginas, o HTML e uma ficha foram inspecionados renderizados. Dez manifestos amostrais anteriores e os 578 artefatos originais mantiveram os hashes. Registros em [outputs/logs](../outputs/logs/README.md).

[Pacote público desta etapa](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/atas-dossie-amostral-v1), separado das entregas anteriores. Não inclui logs brutos, capturas integrais de páginas ou atas específicas não obtidas. Extrair na mesma árvore dos pacotes anteriores para resolver os links cruzados.

Para incorporar documento específico posteriormente, criar nova versão com original preservado, captura/arquivo e SHA256 no catálogo, tipo e identidade territorial completos; no registro de evidências, informar `evidence_id`, `source_id`, `case`, `indicator`, `finding`, `locator`, `justification` e `review_status`. Os valores de `finding` são `corrobora_registro`, `contradiz_registro` ou `inconclusivo`; a revisão deve estar marcada como `revisao_documental_registrada`. Essa declaração precisa corresponder a revisão efetivamente feita; não autentica o arquivo por si.

A validação desta entrega fixa as contagens da captura atual. Uma versão com novas buscas ou documentos específicos também precisa revisar as conclusões e os critérios de validação, preservando a versão anterior; não basta editar o registro de evidências.

## Próxima dependência

Obter atas e registros específicos pelos canais públicos ou por solicitações expressamente autorizadas, começando pelas seis unidades. As minutas estão prontas para revisão e não foram transmitidas. Enquanto esses documentos não chegam, nenhuma causa é encerrada. As frentes de cadeia/LCR, CEPESC, perfil/layout oficial, BU independente e ato individual dos nulos técnicos permanecem separadas.
