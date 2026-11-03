# Pesquisa documental — nulos técnicos e candidatura 28

Pesquisa realizada em 03/11/2026, como segundo passo da frente 3. Complementa o [dossiê local](DOSSIE_CATEGORIAS.md), preservando seus arquivos e classificações.

**Resultado: a norma foi identificada e a situação cadastral Renúncia foi confirmada. A explicação é compatível com os arquivos; sua aplicação temporal ao caso continua pendente.** Não se confirmou a causa jurídica individual dos 5.246 votos nem a persistência de divergências.

## Evidências e alcance

| Pergunta | Achado | Alcance |
| --- | --- | --- |
| O que é nulo técnico? | O guia do TSE descreve votos em candidatura excluída que permaneceu na urna, com registro no BU e tratamento distinto na divulgação nominal. | Regra geral identificada. |
| Qual norma se aplica à Presidência? | Art. 17 da Resolução-TSE 23.677/2021, texto compilado com a redação de 2026; especialmente inciso III, sobre a irregularidade da chapa sem substituição de componente falecido ou renunciante. | Norma majoritária; o art. 21, de proporcionais, não fundamenta esta análise. |
| Qual a situação da candidatura examinada? | O DivulgaCandContas registra Renúncia para Leonardo Alves de Araujo, Leonardo Avalanche, Presidente, número 28, ID 280002554479, eleição 20322002026, ano 2026. | Situação no cadastro consultado, sem reconstrução automática do histórico. |
| Como isso se liga aos números? | As mesmas 2.148 unidades têm 5.246 votos de diferença nominal do número 28 e compensação em nulos técnicos no dossiê. | Correspondência quantitativa confirmada; explicação por renúncia é uma inferência apoiada na regra e no cadastro. |
| Quando a renúncia teve eficácia? | Nenhum ato individual foi obtido nesta pesquisa. | Permanece pendente; atualização cadastral e notícia não equivalem a ato processual. |

O [guia oficial de destinação dos votos de 2026](https://www.tse.jus.br/eleicoes/arquivos/tabela-de-destinacao-de-votos-1/@@display-file/file/destinacao_de_votos_2026_web_final.pdf) relaciona a categoria às condições de exclusão da candidatura e explica sua presença na urna/BU. Também ressalva o efeito da renúncia posterior ao pleito. O guia fornece o mecanismo geral; não menciona este candidato e estas 2.148 unidades individualmente.

A [Resolução-TSE 23.677/2021 compilada](https://www.tse.jus.br/legislacao/compilada/res/2021/resolucao-no-23-677-de-16-de-dezembro-de-2021), art. 17, exige considerar a situação da chapa no intervalo entre o fechamento do CAND e a eleição. A existência de Renúncia no cadastro atual, isoladamente, não comprova todos os requisitos dessa aplicação.

A [consulta individual oficial](https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/buscar/2026/BR/20322002026/candidato/280002554479) confirma a identidade eleitoral e a situação Renúncia. O [painel do TSE](https://sig.tse.jus.br/ords/dwapr/f?p=1002%3A20%3A2773522857754%3A%3A%3ARP%2C20%3AP20_BACK%2CP20_DS_CARGO%2CP20_SG_UF%2CP20_NM_REGIAO%2CP20_NM_UE%3A5%2CPresidente%2CBR%2CBR%2C) contém também outro registro de número 28, de Pablo Marçal. Por isso, o vínculo usa ID, cargo, ano e eleição, além do número. O registro de vice-presidente de Leonardo possui outro ID e não foi confundido com o registro presidencial.

## Cronologia verificada e pendência

| Data | Fato / origem | Interpretação |
| --- | --- | --- |
| 30/09/2026 | Publicação da Agência Brasil sobre anúncio de desistência. | Contexto jornalístico, sem substituir documento eleitoral primário. |
| 04/10/2026 | Primeiro turno, na identificação da eleição analisada. | Referência temporal do pleito. |
| 05/10/2026 12:51 | `dataUltimaAtualizacao` no cadastro individual consultado. | Atualização do cadastro; não é data de apresentação, homologação ou eficácia da renúncia. |
| 03/11/2026 | Pesquisa das fontes e tentativa de consulta processual. | Estado da evidência nesta execução. |

A [notícia da Agência Brasil](https://agenciabrasil.ebc.com.br/politica/noticia/2026-09/candidato-do-prtb-leonardo-avalanche-desiste-de-disputar-presidencia) relata anúncio em 30/09/2026. É uma fonte de contexto, classificada separadamente das fontes eleitorais primárias.

O cadastro indica o processo **0602033-94.2026.6.00.0000**. A [Consulta Pública Unificada do PJe](https://consultaunificadapje.tse.jus.br/) apresentou indisponibilidade e depois CAPTCHA. A tentativa foi interrompida, sem contorno do controle, sem contato externo e sem obtenção de ato individual. Buscas pelo número formatado e sem pontuação não localizaram decisão indexada. Isso não demonstra inexistência de decisão ou renúncia. Documentos de 2024 e de outros processos foram excluídos por não corresponderem ao caso.

## Preservação das fontes

As seis capturas integrais foram arquivadas localmente em `data/documentacao/categorias_2026/capturas/`, identificadas por SHA256. Não são versionadas no Git ou distribuídas nos pacotes públicos. O [catálogo revisado](pesquisa_categorias_2026.json) informa URL, papel, data de gravação da captura e hash. Os hashes são das **extrações JSON/textuais do Firecrawl**, não dos binários originais do servidor. A data de gravação local não é a data jurídica do ato nem um cabeçalho de geração do TSE.

O download binário direto do guia retornou HTTP 403. Foi utilizada a extração textual consultada, cujo extrator informou status 200. Não se afirma ter preservado o PDF original byte a byte.

A [projeção eleitoral do cadastro](candidatura28_evidencia.json) distribui apenas os campos necessários à identidade e à situação eleitoral, vinculados ao hash da captura integral. Campos pessoais adicionais da resposta original e URLs de sessões interativas não integram os artefatos públicos. As sínteses são de autoria do projeto; textos e materiais de terceiros mantêm suas condições de origem.

## Reprodução e entregas

```powershell
.\.venv\Scripts\python.exe scripts/gerar_pesquisa_categorias.py --output outputs/2026
.\.venv\Scripts\python.exe scripts/validar_pesquisa_categorias.py --output outputs/2026
.\.venv\Scripts\python.exe -m pytest -q
```

A geração é local e usa o catálogo já revisado, a projeção do cadastro e os Parquets do dossiê. Não refaz a pesquisa web nem interpreta automaticamente um novo ato. Uma saída preenchida é recusada; usar `--dest` para nova pasta. As consultas atuais são novas evidências documentais, sem substituir a versão da base eleitoral usada no cálculo.

O relatório complementar fica em `outputs/2026/pesquisa_categorias/`, em HTML e PDF. A tabela de unidades mantém as chaves, candidato, diferença, nulos técnicos, zero implícito e avaliação documental, sem reclassificar a referência. O resumo registra entradas e hashes, as fontes e o estado da evidência.

## Acesso e validação

- [Relatório HTML](../outputs/2026/pesquisa_categorias/relatorio.html) e [PDF complementar](../outputs/2026/pesquisa_categorias/relatorio.pdf), com três páginas e sete marcadores.
- [Resumo e hashes](../outputs/2026/pesquisa_categorias/resumo.json), [fontes](../outputs/2026/pesquisa_categorias/fontes.json) e [projeção do cadastro](../outputs/2026/pesquisa_categorias/candidatura.json).
- [Validação](../outputs/logs/validacao-pesquisa.log), [execução](../outputs/logs/execucao-pesquisa.log) e [testes](../outputs/logs/testes-pesquisa.log).

A suíte passou com **113 testes**, incluindo nove que verificam a distinção entre atualização cadastral e eficácia de ato, o vínculo de identidade e o papel das fontes. O novo CSV/Parquet foi comparado pelo multiconjunto tipado completo nos dois sentidos. As 2.148 unidades e 5.246 votos foram vinculados ao dossiê, com classificação causal ainda não confirmada. Foram verificadas as seis capturas locais, 13 links do HTML e hashes das entradas e artefatos. O PDF passou por conferência de conteúdo, margens, marcadores e inspeção visual.

O [pacote pesquisa-categorias-v1](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/pesquisa-categorias-v1) contém as tabelas e os relatórios complementares, com manifesto e SHA256. As capturas integrais locais não integram o pacote público.

## O que falta para avançar a conclusão

1. Obter o ato ou histórico de renúncia do processo identificado, com sua data de eficácia.
2. Confirmar situação da chapa e eventual substituição entre fechamento do CAND e primeiro turno.
3. Relacionar a destinação no SISTOT à candidatura e às versões dos arquivos.
4. Verificar se as diferenças de geração contribuíram para a diferença nominal; a hipótese permanece aberta.

A pesquisa da definição geral e do cadastro foi realizada. A confirmação da causa individual e a conferência das unidades sem comparecimento permanecem pendentes. Não foi atribuída irregularidade nem ausência de irregularidade a partir desses resultados.
