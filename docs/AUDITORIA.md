# Conferência ampliada dos documentos das urnas

A etapa 5 começou com uma seleção registrada **antes da obtenção dos documentos dos casos**. A amostra contém **24 seções, 12 prioritárias e 12 de comparação, nos dois turnos: 48 unidades seção/turno**. Ela cobre as cinco regiões brasileiras e o exterior. Não é uma amostra probabilística e não permite estimar a frequência nacional de irregularidades.

## Seleção reproduzível

```powershell
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --etapa amostra
```

A rotina reutiliza o inventário nacional e as variantes de estabilidade preservadas. Recusa sobrescrever uma pasta preenchida; `--dest` permite outra execução. Os hashes das entradas e dos resultados estão no [manifesto da amostra](../outputs/2026/auditoria/amostra/manifesto.json).

1. Selecionar seções estatisticamente elegíveis, com alerta original, padrão nacional e alerta em todas as variantes disponíveis (pelo menos duas).
2. Reservar dois prioritários por região: um com aumento e outro com redução da margem entre finalistas. Preferir UFs distintas. Ordenar por ausência de aviso de MAD muito pequeno, menor escore robusto entre variantes em ordem decrescente, mudança absoluta de margem e chave geográfica. Registrar qualquer insuficiência, sem substituir casos após conhecer documentos.
3. Para cada prioridade, selecionar um controle único, sem alerta original, sem alerta nas variantes disponíveis e sem padrão nacional selecionado. Preferir o mesmo município; completar na mesma UF.
4. Parear por distância euclidiana de `ln(1+aptos)`, comparecimento/aptos e participações dos finalistas nos votos nominais do primeiro turno. Centralizar pela mediana e escalar pelo desvio padrão da UF (`ddof=0`). Não usar valores do segundo turno no pareamento.
5. Registrar as duas unidades seção/turno de cada caso e os valores locais de referência.

No exterior há somente duas variantes disponíveis (15 e 30 pares). A frequência foi calculada diretamente de `estabilidade/variantes.parquet`, preservando a ausência de 50 pares; ela não é chamada de estabilidade 3/3. Não houve insuficiência de estratos ou controles na seleção final.

**Arquivos:** [seções selecionadas](../outputs/2026/auditoria/amostra/secoes.csv), [turnos](../outputs/2026/auditoria/amostra/turnos.csv), [protocolo](../outputs/2026/auditoria/amostra/protocolo.json) e [resumo](../outputs/2026/auditoria/amostra/resumo.json). CSV e Parquet são gerados conjuntamente; os Parquets permanecem fora do Git.

## Escopo da conferência

Obter RDV, BU binário, assinatura, imagem do BU e log quando disponíveis. Preservar os bytes originais e registrar fonte, obtenção, formato e hash. Recontar apenas totais por cargo/categoria, sem conservar ordem de votos ou tentar identificar eleitores. Comparar com os valores da mesma seção/turno e da versão de referência.

Separar integridade por hash, validação criptográfica da assinatura e confiança na cadeia de certificados. Concordância entre arquivos do mesmo equipamento não constitui fonte independente. Uma imagem digital do BU não será apresentada como conferência com o papel recolhido no local. Arquivo ausente, formato incompatível ou referência criptográfica insuficiente gera limitação explícita, sem conclusão automática de fraude.

O [TSE descreve esses procedimentos de auditoria](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria). Seleção, obtenção e conferência são registradas separadamente a seguir.

## Execução e resultados da primeira conferência

Seleção congelada em `e1ed429`; obtenção e leitores em `0ba50d7`, em 4 de novembro de 2026. Foram obtidos **240 documentos**, cinco tipos para cada uma das **48 unidades seção/turno**, em **22 ZIPs oficiais**. O [inventário](../outputs/2026/auditoria/documentos/inventario.csv) identifica os originais, URL, membro, obtenção, SHA256, tamanho e CRC32. As versões remotas e os intervalos recebidos estão em [arquivos_remotos.json](../outputs/2026/auditoria/documentos/arquivos_remotos.json).

Não foi necessário baixar os pacotes estaduais completos. Foram transferidos 353.642.570 bytes, incluindo diretórios ZIP e intervalos de leitura. Um ETag forte fixa a versão de cada ZIP durante a extração; `Content-Range` e o CRC32 de cada membro são conferidos. **Não foi calculado SHA256 dos ZIPs completos**: os hashes publicados se referem aos membros e aos intervalos efetivamente obtidos. Os 240 originais ficam em `data/auditoria/urnas/`, fora do Git.

| Conferência | Universo | Resultado |
| --- | --- | --- |
| RDV presidencial × BU binário × texto da imagem do BU × CSV de resultados × CSV de BU | 265 linhas por candidato/categoria, em 48 unidades seção/turno | Todas concordantes |
| Soma dos votos × comparecimento | 48 unidades seção/turno | Todas reconciliadas |
| Aptos e comparecimento do BU e da imagem × referência preservada | 48 unidades seção/turno | Todos coincidentes |
| Integridade dos originais obtidos | 240 arquivos | CRC32 e SHA256 conferidos |
| Assinatura criptográfica e cadeia de confiança | 48 arquivos de assinatura | Não verificadas: formato incompatível com o esquema consultado |
| Eventos de log | 48 arquivos obtidos | Preservados; análise de eventos não executada |
| BU em papel ou imagem recolhida de fonte independente | Nenhum obtido | Conferência não realizada |

Brasil: 40 unidades seção/turno (20 prioritárias e 20 controles). Exterior: oito (quatro prioritárias e quatro controles). **265 são linhas por candidato/categoria, não 265 pessoas, urnas ou seções.** O candidato 95 na exportação representa brancos; 96 representa nulos. Os votos nominais de todos os candidatos presidenciais são comparados, não somente os finalistas.

### Leitura dos formatos e denominadores

O leitor ASN.1 exige consumo completo da entidade, limites do esquema, fase oficial, identificação territorial e eleição presidencial compatíveis. Um cargo ausente ou duplicado não se transforma em votação zero. No RDV, nominais são contados por número; brancos e brancos após suspensão compõem brancos; as categorias de nulos são agregadas como nulos. Legenda e tipos desconhecidos no cargo presidencial são rejeitados como formato não suportado. Não são exportados ordem, lista individual de votos ou conteúdo dos logs.

O BU é lido em seu envelope e conteúdo binário; o eleitorado apto e o comparecimento são extraídos da eleição correspondente. A imagem é um arquivo digital com texto do boletim e blocos gráficos: o leitor usa o bloco textual presidencial, valida município/zona/seção e reconcilia os totais da extração. **Não se trata de OCR nem de conferência com papel independente.**

As duas bases CSV de referência permanecem nas versões preservadas. As ausências nominais somente podem ser interpretadas como zeros implícitos em uma unidade instalada, com votação e cargo identificado; a presença da linha original continua registrada. Uma diferença conhecida entre fontes permanece apontada mesmo se outra fonte estiver ausente; ausência não vira zero nem apaga uma diferença. As gerações das fontes CSV e do BU binário são conservadas nos arquivos vinculados.

### Limitação das assinaturas e proveniência dos esquemas

O [catálogo oficial de 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026-arquivos-transmitidos-para-totalizacao) forneceu os documentos das urnas. A documentação técnica consultada remete ao pacote de formatos; o download direto tentado no TSE retornou HTTP 403. Os três esquemas usados foram extraídos de um [espelho de terceiros](https://github.com/doccaz/urnas-br/tree/main/docv2), fixando o SHA256 do ZIP em `1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235`. Nenhum código do espelho é executado. O script de preparação confere também o hash individual de cada esquema.

Os BUs e RDVs da amostra foram decodificados com esses esquemas. **Todos os 48 arquivos de assinaturas apresentaram incompatibilidade de estrutura com o esquema de assinaturas consultado.** Os erros exatos constam da [conferência por documento](../outputs/2026/auditoria/conferencia/documentos.csv). Não houve adaptação silenciosa, verificação criptográfica, validação de cadeia ou classificação de assinatura inválida. Um SHA256 local e um CRC32 correto não demonstram autenticidade criptográfica. O espelho dos esquemas tampouco constitui uma âncora oficial de confiança.

### Relatórios e interpretação

[Pacote completo desta conferência](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/auditoria-amostral-v1), com CSV/Parquet, relatórios, fontes e hashes. Os originais brutos e os esquemas externos não são redistribuídos no pacote. As bases de entrada pertencem às entregas anteriores de estabilidade e investigação nacional.

[HTML com filtros e casos](../outputs/2026/auditoria/relatorio/relatorio.html) · [PDF](../outputs/2026/auditoria/relatorio/relatorio.pdf) · [síntese derivada](../outputs/2026/auditoria/relatorio/resumo.json) · [votação linha a linha](../outputs/2026/auditoria/conferencia/votacao.csv) · [unidades e denominadores](../outputs/2026/auditoria/conferencia/unidades.csv).

O PDF tem **nove páginas e dez marcadores**, com conclusão e alcance, método/fontes, seis páginas de seções e pendências. O HTML contém as 24 seções e filtros por UF/grupo. O resultado confirma os totais desta amostra e dessas versões, sem explicar a escolha dos eleitores ou afastar todas as possibilidades de irregularidade. Os documentos digitais pertencem ao mesmo equipamento; a concordância entre eles não fornece observação independente do voto.

## Reprodução completa e validação

Reutilizar os artefatos das entregas nacional e de estabilidade já preservados. Extrair o pacote complementar na mesma árvore dessas entregas, para resolver os links aos relatórios anteriores. Para reprodução completa, copiar as entradas necessárias para uma raiz `--output` nova e executar a sequência abaixo nessa raiz. Cada etapa recusa sobrescrever a pasta preenchida. `--dest` serve para repetir uma etapa isolada; não altera automaticamente as entradas das etapas seguintes. Para nova obtenção, usar também `--data` separado, preservando os originais anteriores. Os resultados podem divergir se a fonte remota tiver sido atualizada; conferir ETags, hashes e gerações.

```powershell
# Dependência opcional dos leitores
.\.venv\Scripts\python.exe -m pip install -e '.[auditoria,test]'
# 1. Seleção anterior à consulta dos documentos
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --etapa amostra
# 2. Obtenção seletiva dos cinco tipos, somente para a amostra
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --etapa documentos --data data
# 3. Preparação explícita dos esquemas do espelho, conferidos por hash
.\.venv\Scripts\python.exe scripts/preparar_especificacao_auditoria.py --data data
# 4. Recontagem/confronto agregado, com limitações por documento
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --etapa conferencia --data data
# 5. Síntese e relatórios separados da referência
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --etapa relatorio
# 6. Conferências locais; PyMuPDF é usado na inspeção do PDF
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings
.\.venv\Scripts\python.exe -X utf8 scripts/validar_auditoria.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe scripts/preservar_documentacao.py --check
```

**Validação:** 151 testes aprovados; seis pares CSV/Parquet comparados integralmente com tipos; 240 originais conferidos por SHA256/tamanho/CRC32; 48 unidades e 265 linhas reconciliadas; todos os links locais conferidos; 900 condições dos filtros verificadas em JavaScript; conteúdo e margens do PDF conferidos, além de inspeção de páginas renderizadas e HTML no Chrome headless. Os 578 artefatos anteriores mantêm seus hashes. Os 181 avisos da suíte são de APIs descontinuadas de `pyparsing` usadas por `asn1tools`; não houve teste com falha.

## Próximos incrementos ainda abertos

1. Localizar e preservar a especificação compatível dos arquivos de assinaturas da amostra; implementar leitura com teste de corrupção e versões.
2. Conferir o vínculo de cada arquivo com a assinatura, o algoritmo, a assinatura criptográfica, a validade temporal e a cadeia com âncoras oficiais. Documentar separadamente qualquer limite de cadeia ou revogação.
3. Definir e executar conferência de eventos dos logs, sem inferir sequência de votos a partir do RDV e sem publicar dados pessoais.
4. Obter BU em papel ou imagem de fonte independente nos casos prioritários e comparar a mesma seção/turno/versão.
5. Manter aberta a pesquisa do ato individual e da eficácia temporal da classificação dos nulos técnicos da frente 3.

A primeira conferência de totais está concluída; **a etapa 5 completa permanece aberta** para os procedimentos acima. Não houve nova ingestão nacional nem contato com terceiros.
