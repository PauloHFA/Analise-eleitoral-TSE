# Eventos dos logs — análise descritiva da amostra

Foram analisados **48 arquivos `log.jez` das mesmas 24 seções**, nos dois turnos. A seleção anterior aos documentos permanece congelada: 12 prioridades e 12 controles, nas cinco regiões e no exterior. Este incremento analisa registros operacionais; não amplia a amostra nem estima uma frequência nacional de irregularidade.

[HTML com filtros](../outputs/2026/auditoria/logs/relatorio.html) · [PDF](../outputs/2026/auditoria/logs/relatorio.pdf) · [síntese](../outputs/2026/auditoria/logs/resumo.json) · [fontes consultadas](logs-fontes.json).

## O que foi encontrado

| Medida | Resultado | Unidade e interpretação |
| --- | --- | --- |
| ZIPs originais | 48 | Arquivos vinculados aos hashes e assinaturas de hardware anteriores |
| Membros textuais | 49 | Um `logd.dat` adicional dentro de outro ZIP aninhado |
| Registros válidos lidos | 287.649 | Ocorrências físicas nos arquivos, não eventos únicos da eleição |
| Antes da data-alvo do respectivo turno | 129.546 | Preparação e histórico, inclusive do primeiro turno em arquivos do segundo |
| Na data-alvo | 158.103 | 04/10/2026 no primeiro turno; 25/10/2026 no segundo |
| Depois da data-alvo | 0 | Observação do recorte, sem comprovar completude |
| Linhas não interpretadas / sobreposição entre membros | 0 / 0 | Dentro do layout e dos arquivos examinados |
| Registros ERRO na data-alvo | 33, em 24 unidades seção/turno | Todos no segundo turno; classificação emitida pelo software |
| Registros ALERTA na data-alvo | 596 | Mensagens, não pessoas ou votos afetados |
| Retrocessos na ordem temporal | 49 no conteúdo completo; um na data-alvo | Ordem física do mesmo membro, sem presumir causa |
| Mais de um identificador de hardware na data-alvo | Uma unidade | Não confirma substituição sem documento operacional |
| Ligações entre marcos avaliáveis | Três unidades | Mensagens dentro do mesmo membro; não duração de interrupções |
| Apontamentos selecionados | 33 linhas em 28 unidades seção/turno | Motivos podem se sobrepor; não são 33 seções distintas |

Todos os 48 conjuntos têm ao menos um registro de urna pronta, início de encerramento e geração do BU na data-alvo. **A presença desses marcos não prova continuidade ou completude do log.** Também não se presume que a mesma seção utilizou o mesmo equipamento entre turnos.

### Tipos de erro e contexto

| Tipo local | Registros na data-alvo | Posição em relação aos marcos do mesmo membro |
| --- | --- | --- |
| Problema na desmontagem de MR | 31 | 25 antes da primeira prontidão; quatro entre prontidão e início de encerramento; dois não classificáveis |
| OpenSession / impossibilidade de continuar a execução | 1 | Entre prontidão e início de encerramento |
| Erro desconhecido da impressora | 1 | Contexto não classificável pelos marcos |

Essas categorias correspondem a mensagens fixas, sem reprodução de dados pessoais. “Antes da prontidão” não determina causa, normalidade ou ausência de impacto. A classificação temporal só é feita quando o mesmo membro tem os marcos necessários, um único identificador de hardware e relógio sem retrocesso na data-alvo. Não se usam marcos de outro membro para preencher essa falta.

O número 33 não é uma contagem de falhas físicas, votos afetados ou divergências RDV/BU. **A causa e o efeito desses eventos não foram confirmados.** Os [erros por tipo/contexto](../outputs/2026/auditoria/logs/erros_contexto.csv) permitem conferir todas as ocorrências agregadas por membro e seção/turno.

### Casos que precisam de contexto documental

- **BA, município TSE 34193, zona 53, seção 274, segundo turno:** arquivo com ZIP aninhado e dois identificadores de hardware na data-alvo. Os dois membros foram incluídos e não têm linhas idênticas em sobreposição. A composição não foi declarada como troca de equipamento confirmada.
- **Exterior, município TSE 29416, zona 1, seção 920, primeiro turno:** um retrocesso do relógio na ordem das linhas da data-alvo. Não foi atribuída causa nem comparação de fuso entre locais.
- As três unidades com ligações entre marcos e as unidades com mensagens ERRO estão no [inventário de apontamentos](../outputs/2026/auditoria/logs/pendencias.csv), com critérios iguais para prioridades e controles.

## Método, passo a passo

1. Reutilizar a amostra, o inventário e a conferência Ed521/ECDSA, fixando as entradas por SHA256. Verificar unicidade por ano/turno/UF/município/zona/seção e por tipo de documento.
2. Conferir SHA256 e tamanho dos 48 ZIPs originais. Relacionar cada um à linha de hardware do estágio anterior, com hash concordante e assinatura válida com a chave embutida. Isso não valida a cadeia institucional; a [etapa PKIX](CAMINHO_PKIX.md) permanece inconclusiva sem âncora.
3. Percorrer todos os `logd.dat`, inclusive aninhados, sem extrair caminhos no sistema. Rejeitar caminhos inseguros, membros desconhecidos/repetidos/cifrados, ZIP/CRC inválido e limites excedidos. Limites: 32 MiB de descompressão acumulada por arquivo, profundidade até dois e 16 membros por ZIP.
4. Ler o **layout observado**: timestamp, nível, identificador técnico, módulo, mensagem e token final, separados por tabulação; texto Latin-1. Validar data, número de campos, controles, identificador de oito dígitos e token hexadecimal de 16 dígitos. Este último é validado **somente na sintaxe**: seu algoritmo/integridade encadeada não foi verificado. Não há homologação oficial do parser.
5. Separar cada registro em anterior, data-alvo ou posterior, usando datas explícitas do projeto. Os horários são locais declarados, sem fuso ou carimbo autenticado; não são comparados entre locais. Não ordenar antes de medir regressões nem criar uma cronologia entre membros distintos.
6. Aplicar as expressões fixas de [regras.csv](../outputs/2026/auditoria/logs/regras.csv), com restrição de módulo quando definida. As demais mensagens entram em `outro_evento`. A classificação é exploratória, definida após inspeção do formato; não é um dicionário oficial nem análise pré-registrada.
7. Contar níveis e categorias por janela/unidade; detectar repetições internas e sobreposição exata entre membros por hash de linha, sem deduplicar automaticamente. Uma linha histórica em arquivos dos dois turnos continua sendo ocorrência física em cada fonte; não é promovida a evento único.
8. Registrar marcos e contexto dos erros somente dentro do mesmo membro. O intervalo entre a primeira prontidão e o último início de encerramento não é prova de sessão oficial contínua. Não calcular tempo de paralisação nem inferir substituições físicas a partir de contagens.
9. Comparar os dois turnos da mesma seção, preservando ausências. A taxa descritiva de ERRO usa `1.000 × registros ERRO / comparecimento` e produz ausência se o denominador não é positivo. Ela **não** é risco, probabilidade por eleitor ou taxa de votos afetados. O grupo e a região permanecem disponíveis nas tabelas; não se faz inferência causal entre prioridades e controles.
10. Gerar tabelas, síntese, gráfico, relatório e apontamentos em pasta própria, sem modificar os relatórios nacionais ou as nove etapas amostrais anteriores.

As regras não exportam mensagens brutas, nomes, identificações pessoais, teclas, biometria ou horários/sequências de votação individual. Apenas os horários de marcos operacionais selecionados são publicados. Módulos/níveis fora do vocabulário observado são normalizados e não propagam texto arbitrário.

## Tabelas e reprodução

Os **sete pares CSV/Parquet** são `unidades`, `membros`, `contagens`, `erros_contexto`, `comparacao_turnos`, `pendencias` e `regras`. O [protocolo](../outputs/2026/auditoria/logs/protocolo.json) registra datas, limites e interpretação do token. O manifesto preserva os hashes dos resultados e a síntese identifica os hashes do código e das entradas.

```powershell
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --data data --etapa logs
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 scripts/validar_logs.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe scripts/preservar_documentacao.py --check
```

O comando recusa pasta preenchida. Para repetir, use `--dest` em uma pasta nova, mantendo as entradas anteriores em `--output`; para reprodução completa em outra máquina, obtenha os originais pelos endereços/hashes do inventário anterior. Não há downloads no comando de análise.

**Validação:** 211 testes aprovados, incluindo 17 novos; 543 avisos de depreciação ASN.1, sem falhas. Sete pares CSV/Parquet comparados integralmente com tipos; contagens reconferidas nos 48 originais; 5.292 condições dos filtros testadas; 12 referências locais de links/imagem verificadas. PDF de sete páginas/sete marcadores validado por conteúdo/margens, com páginas renderizadas e HTML inspecionados. Nove manifestos amostrais anteriores e os 578 artefatos originais preservados. Os [logs de execução](../outputs/logs/README.md) distinguem cada conferência.

[Pacote público separado](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/logs-amostrais-v1), com tabelas completas e hashes. Não inclui conteúdo bruto dos logs ou registros individuais. Extrair na mesma árvore dos pacotes anteriores para resolver os links cruzados; as versões anteriores permanecem preservadas.

## Fontes e limites da interpretação

A [explicação da Justiça Eleitoral de 2022](https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2022/logs-das-urnas-eletronicas-sao-dados-publicos-e-nao-revelam-votos-de-eleitores) descreve logs como registros de funcionamento e falhas, sem revelar a escolha dos candidatos por eleitor. É contexto histórico, não especificação dos eventos de 2026. O [TSE descreve a comparação entre atas e arquivos digitais](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria) entre os procedimentos possíveis de auditoria.

As capturas textuais dessas duas páginas têm URL, data de obtenção e SHA256 em [logs-fontes.json](logs-fontes.json); o hash identifica a captura, não os bytes HTTP originais. O README técnico do pacote em espelho já preservado identifica `log.jez` como texto compactado; essa referência não é confirmação oficial autenticada do parser. Nenhum código do espelho foi executado.

**Próximo passo:** obter atas e registros de atendimento/substituição dos casos apontados, para confrontar o que o software registrou com documentação operacional. Nenhuma mensagem foi classificada como normal ou explicada apenas por aparecer nos arquivos. Não houve contato externo automático. CEPESC, fontes oficiais da cadeia/LCR, layout oficial, BU independente e eficácia temporal do ato dos nulos técnicos continuam pendentes em suas frentes próprias.
