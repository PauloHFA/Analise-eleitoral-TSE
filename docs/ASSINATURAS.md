# Assinaturas da amostra — leitura e verificação parcial

Este incremento resolve a leitura dos **48 arquivos de assinatura** preservados na primeira conferência. Os documentos e os relatórios anteriores não foram substituídos. A amostra continua com 24 seções, 12 prioridades e 12 controles, nos dois turnos, sem representatividade estatística nacional.

## Alcance e resultados

| Procedimento | Quantidade | Resultado |
| --- | --- | --- |
| Leitura do layout observado | 48 arquivos VSC | Todos lidos e recodificados byte a byte |
| SHA512 dos documentos obtidos, nas listas SW e HW | 384 verificações de 192 documentos | Todas concordantes |
| SHA512 do conteúdo das listas SW/HW | 96 verificações | Todas concordantes |
| Comparação dos hashes declarados em SW e HW | 48 pares de listas | Nenhuma diferença observada |
| Assinatura ECDSA da lista de hardware | 14 unidades seção/turno | Confere com a chave do certificado embutido |
| Assinaturas ECDSA dos documentos obtidos | 56 verificações | Conferem com a mesma chave embutida |
| Hardware Ed521 | 34 unidades, 136 assinaturas dos documentos e 34 das listas | Não verificado: algoritmo ainda não implementado |
| Software CEPESC | 48 unidades, 192 assinaturas dos documentos e 48 das listas | Não verificado: algoritmo não implementado |
| Validade temporal do certificado de ponta | 48 ocorrências | Compatível com a data declarada no VSC, em todos os fusos considerados |
| Cadeia até âncora oficial e revogação | Todos os casos | Não validadas |

São **70 verificações ECDSA** (14 listas e 56 documentos), sem equivalência com 70 urnas. As 384 verificações de hash usam os mesmos 192 documentos duas vezes, uma na lista SW e outra na HW. Os arquivos VSC são o quinto tipo da amostra de 240 documentos; não são contados como documentos assinados por si próprios.

As listas mencionam **1.008 entradas** em SW/HW. Dessas, **624** se referem a documentos não obtidos no escopo inicial. Elas são inventariadas como fora do escopo, não como arquivo ausente inexplicável ou hash divergente. Nenhum arquivo adicional de comparecimento, biometria ou votos foi baixado.

## Por que o leitor anterior não conseguiu ler

O esquema consultado descreve o modelo do equipamento antes das listas SW/HW. Os arquivos da amostra trazem essas listas primeiro, seguidas de uma sequência com modelo e algoritmo. Os opcionais `conjuntoChave` e `certificadoDigital` usam tags de contexto `[0]` e `[1]`.

O projeto passa a ter um esquema próprio, **`observado-vsc-2026-sequencia-final-v1`**, que descreve explicitamente essa estrutura. Trata-se de **adaptação inferida dos arquivos, não de especificação oficial localizada ou homologada pelo TSE**. O esquema anterior e os erros registrados na primeira entrega são preservados como histórico.

O leitor exige versão 2, fase/unidade compatível pelo vínculo com o inventário, SHA512 declarado, listas SW/HW com nomes únicos e compatíveis, nomes seguros e correspondência exata dos quatro documentos com seção/turno. Consome a entidade inteira e exige que a recodificação reproduza todos os bytes. Isso evita descartar campos desconhecidos ou aceitar arquivos truncados como válidos. Formatos ou versões diferentes são limitados explicitamente, sem busca por trechos que aparentem funcionar.

## Hash, assinatura, certificado e confiança são verificações distintas

1. O SHA256 do inventário confirma que cada original local é o mesmo obtido na rodada anterior.
2. O SHA512 compara os bytes de BU, RDV, imagem e log com os hashes declarados em SW e HW. O conteúdo de cada lista também é comparado ao hash declarado no seu envelope.
3. Para ECDSA P-521, a mensagem é o hash de 64 bytes; a verificação aplica SHA512 a essa mensagem, conforme a rotina técnica de exemplo do pacote consultado. Não se experimentam sucessivos algoritmos até obter aprovação. Quando r/s usam largura fixa em BER, os mesmos inteiros são recodificados em DER; campos extras e sufixos são rejeitados.
4. A chave para essa equação vem do certificado embutido no VSC. **Uma assinatura que confere com essa chave não demonstra sozinha que o certificado é institucionalmente autêntico.**
5. O certificado de ponta é extraído e identificado por SHA256, OIDs, emissor e datas. Não foi validado o caminho até uma raiz oficial, a assinatura do certificado pelo emissor, a validade dos emissores nem revogação. Nenhuma contagem de certificados confiáveis foi inferida.

Os VSC não indicam fuso horário. A data declarada é comparada ao intervalo do certificado em todas as hipóteses de UTC−12 a UTC+14. Compatibilidade em todas essas hipóteses é registrada separadamente; proximidade de um limite seria inconclusiva sem fuso. **A data declarada no VSC não é um carimbo de tempo autenticado.** Essa checagem não comprova quando a assinatura ocorreu.

Os modelos observados são UE2013 (oito unidades) e UE2015 (seis), com ECDSA; UE2020 (quatro) e UE2022 (30), com Ed521. Essas contagens descrevem apenas a amostra dirigida, sem comparação nacional de segurança por modelo.

## Fontes e proveniência

- [Catálogo oficial dos arquivos transmitidos para totalização](https://dadosabertos.tse.jus.br/dataset/resultados-2026-arquivos-transmitidos-para-totalizacao): origem dos VSC e demais documentos já preservados por hash.
- [Como realizar auditoria, do TSE](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria): distingue conferências de assinaturas, BU e RDV.
- [Documentação técnica publicada pelo TSE para 2022](https://www.tse.jus.br/eleicoes/eleicoes-2022/documentacao-tecnica-do-software-da-urna-eletronica): foi a página de formatos encontrada na pesquisa. Não foi apresentada como documentação compatível de 2026.
- Pacote técnico preservado na rodada anterior, obtido de [espelho](https://github.com/doccaz/urnas-br/tree/main/docv2), SHA256 `1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235`. O exemplo `python/assinatura_hash.py` fundamenta a mensagem de verificação ECDSA. O download direto tentado no TSE havia retornado HTTP 403; a origem do espelho permanece explícita.
- [Leitor de referência DataUrnas-BR](https://github.com/alissonlinneker/DataUrnas-BR/blob/main/src/dataurnas/parsers/signature.py): referência de terceiros que também descreve a diferença do layout. O leitor deste projeto usa esquema explícito, validação integral e controles próprios. Não foram executados códigos desses repositórios nem adotadas suas contagens ou conclusões.

As buscas desta rodada ficaram preservadas em `.firecrawl/assinaturas-2026-formato.json`, `assinaturas-estrutura.json` e `assinaturas-oficial-compatibilidade.json`, fora do Git. Busca sem localização de um documento não demonstra que ele inexiste.

## Artefatos e reprodução

[Pacote público completo deste incremento](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/assinaturas-amostrais-v1), com quatro pares CSV/Parquet, esquema local, relatórios, inventários e hashes. Extrair na mesma árvore da primeira entrega amostral para resolver os links de referência. Não inclui VSC brutos, certificados completos nem os documentos pessoais mencionados nas listas.

[HTML](../outputs/2026/auditoria/assinaturas/relatorio.html) · [PDF](../outputs/2026/auditoria/assinaturas/relatorio.pdf) · [síntese](../outputs/2026/auditoria/assinaturas/resumo.json) · [layout observado](../outputs/2026/auditoria/assinaturas/layout_observado.asn1).

As quatro tabelas são geradas em CSV/Parquet: `arquivos_assinados` (1.008 entradas, com escopo), `envelopes` (96 listas), `certificados` (48 ocorrências) e `unidades` (48 seções/turnos). Algoritmo não suportado, assinatura que não confere com a chave e formato não suportado têm classificações distintas. O resultado não constitui auditoria integral nem explica escolhas dos eleitores.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[auditoria,test]'
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --data data --etapa assinaturas
# Pasta nova para repetir a etapa, preservando a versão anterior
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --data data --etapa assinaturas --dest outputs/reproducao-assinaturas
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings
.\.venv\Scripts\python.exe -X utf8 scripts/validar_assinaturas.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe scripts/preservar_documentacao.py --check
```

**Validação executada:** 160 testes aprovados, com nove testes novos de leitura/criptografia; quatro pares CSV/Parquet comparados integralmente com tipos; 48 leituras e 1.008 entradas reconciliadas; 14 assinaturas ECDSA das listas reconferidas; nove links locais verificados. O PDF tem cinco páginas e cinco marcadores, com conteúdo/margens conferidos e páginas renderizadas inspecionadas; o HTML foi inspecionado no Chrome headless. Os 578 artefatos anteriores e os manifestos da primeira conferência permaneceram intactos. Os 362 avisos dos testes são de depreciação da dependência ASN.1; não houve teste com falha.

## Próximas verificações

Confirmar o layout por documentação oficial; implementar Ed521 com referência e vetores independentes antes de atribuir resultados criptográficos; validar cadeia e revogação com âncoras oficiais. A análise de eventos dos logs, o BU de fonte independente e a eficácia temporal do ato sobre nulos técnicos permanecem abertos. A leitura agora realizada não transforma retrospectivamente a primeira entrega em auditoria completa.
