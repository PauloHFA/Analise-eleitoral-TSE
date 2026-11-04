# Caminho de certificados — backend PKIX e revogação obrigatória

O item 1 ganhou uma implementação de **construção e validação de caminho completo**, usando `pyhanko-certvalidator 0.33.0`, com adaptador para Ed521. Os testes controlados verificam caminhos completos ECDSA e Ed521, inclusive assinatura de LCR. Isso supera o verificador anterior, restrito ao vínculo ponta–intermediário.

**A conclusão com os arquivos reais continua pendente.** Nenhuma raiz oficial, emissor faltante ou LCR utilizável foi obtida nesta captura. As 48 unidades seção/turno continuam sem caminho validado; sucesso com certificados sintéticos não é evidência de confiança nos certificados das urnas.

## Execução real e unidades

| Medida | Resultado | Interpretação |
| --- | --- | --- |
| Amostra preservada | 24 seções, 48 unidades seção/turno | Mesmas prioridades e controles das etapas anteriores |
| Certificados de ponta distintos | 25 | Não confundir ocorrências com equipamentos distintos |
| Hipóteses de horário | 144, três por unidade | Não são 144 urnas nem prova de tempo autenticado |
| Intermediários candidatos fornecidos | 3 | Cópias anteriores preservadas, sem promoção a âncora |
| Âncoras selecionadas / LCR fornecidas | 0 / 0 | Não há base para concluir confiança ou revogação |
| Caminhos | 144 inconclusivos por falta de âncora | Não significa 144 assinaturas inválidas |
| Revogação | 144 não avaliadas sem caminho | A passagem estrita não foi alcançada; não são aprovações |
| Novas consultas | 11 respostas HTTP 403 | Separadas das 21 tentativas anteriores |
| Apontamento anterior de vigência | 14 ocorrências | AC URNA candidato fora do período; causa ainda desconhecida |

O [HTML](../outputs/2026/auditoria/caminho_pkix/relatorio.html) e o [PDF](../outputs/2026/auditoria/caminho_pkix/relatorio.pdf) apresentam método e resultado por unidade. As tabelas completas são [validações](../outputs/2026/auditoria/caminho_pkix/validacoes.csv), [unidades](../outputs/2026/auditoria/caminho_pkix/unidades.csv) e [novas consultas](../outputs/2026/auditoria/caminho_pkix/novas_tentativas.csv), cada uma também em Parquet. A [política executada](../outputs/2026/auditoria/caminho_pkix/politica_executada.json) e a [síntese](../outputs/2026/auditoria/caminho_pkix/resumo.json) registram entradas e versões.

## Método e política de confiança

1. Conferir SHA256 dos originais, das fontes anteriores e da captura complementar; reutilizar a seleção congelada. Não realizar nova ingestão nacional.
2. Extrair a ponta do VSC e fornecer ao backend os três intermediários candidatos. A construção do caminho, assinaturas, validade, `BasicConstraints`, uso de chave, `pathLen`, restrições de nomes e extensões críticas são tratadas pelo backend sob a configuração escolhida. Não é uma alegação de suporte universal a toda política/extensão da RFC 5280 ou de homologação do perfil TSE.
3. Fornecer **sempre uma lista explícita de âncoras**, inclusive vazia. Não carregar raízes TLS do sistema. Um autoassinado, um arquivo de espelho ou um intermediário recebido não se torna confiável por estar disponível.
4. Selecionar âncoras somente por manifesto `confianca.json`, versão 1: arquivo local, SHA256 DER, URL oficial declarada e justificativa. Caminhos fora da pasta, impressões digitais divergentes e duplicidades são rejeitados. **A declaração de URL não autentica a fonte**; a evidência de publicação e a decisão de confiança precisam ser documentadas pelo responsável. O manifesto executado contém `anchors: []`.
5. Separar duas passagens. A primeira valida o caminho sem consultar revogação (`NO_CHECK`) e recebe status próprio. Somente depois de um caminho conferir é executada a passagem com `CRL_REQUIRED` para ponta e intermediários. Sem LCR adequada, não há êxito de revogação. Uma raiz escolhida é entrada de confiança; não se afirma revogação da própria âncora.
6. Desativar rede automática, OCSP, retroatividade de LCR e tolerância de relógio. O backend recebe apenas os objetos locais preservados. Estados não suportados ou evidência insuficiente não são promovidos a aprovação.
7. Avaliar cada ocorrência em três instantes: data declarada como UTC e limites correspondentes aos fusos UTC+14 e UTC−12. Esses pontos não autenticam o horário, nem provam continuidade de revogação em todo o intervalo.

O adaptador Ed521 verifica **os bytes TBS diretamente**, com chave canônica, subgrupo e algoritmo explícitos. Não aplica o wrapper `SHA512(hash)` das assinaturas dos documentos VSC. Assinaturas ECDSA P-521/SHA512 são normalizadas da codificação observada antes da conferência pelo backend. Outros algoritmos seguem a política padrão da biblioteca; não se usa uma política de aceitação irrestrita.

## Testes sintéticos e limites

Os testes exercitam caminho raiz–intermediário–ponta, LCR válidas, certificado revogado, LCR vencida, falta de âncora, falta de evidência de revogação, assinatura errada apesar de nome/AKI compatíveis, CA vencida, `pathLen`, `NameConstraints`, extensão crítica desconhecida, ausência de uso da lista TLS do sistema e seleção de âncora por manifesto.

Uma fixture sintética usa intermediário Ed521, ponta assinada por Ed521 e LCR Ed521. As assinaturas são geradas com o genérico Noble fixado pelo lockfile já usado como referência; o gerador novo não altera o gerador anterior. Sementes/chaves são **públicas, artificiais e exclusivas de teste**. Não são vetores oficiais, certificados reais ou certificação independente do adaptador.

Implementado não significa integralmente auditado: não houve homologação pelo TSE, teste de conformidade exaustivo da RFC 5280, conclusão OCSP, prova de tempo autenticado, verificação CEPESC ou auditoria de escolhas dos eleitores.

## Pesquisa de fontes

A busca distinguiu a PKI das urnas das raízes genéricas ICP-Brasil. Nenhuma raiz genérica foi usada como substituta. A extração da página HTTP de DPC identificou a base canônica HTTPS `https://acue2020.tse.jus.br/dpc/`; seis nomes candidatos `.crt` foram tentados nessa base. Cinco rotas candidatas de LCR foram consultadas sob os domínios das autoridades. **As rotas de arquivos são hipóteses de busca, não confirmação de publicação oficial.**

As 11 consultas retornaram HTTP 403, com TLS verificado e sem seguir redirecionamentos automaticamente. Datas UTC, status, tamanho/hash da resposta e motivo da escolha constam na tabela. Os corpos de erro não foram tratados como certificados ou LCR. Os registros anteriores, incluindo oito erros TLS, não foram alterados nem recontados como consultas novas. Falha de acesso neste ambiente não prova inexistência dos documentos. Nenhum pedido a terceiros foi enviado.

Referências primárias de implementação: [release do backend 0.33.0](https://pypi.org/project/pyhanko-certvalidator/0.33.0/), [documentação pyHanko](https://docs.pyhanko.eu/en/latest/lib-guide/validation.html) e [RFC 5280](https://www.rfc-editor.org/rfc/rfc5280.html). O código permanece responsável pela configuração e pelo adaptador Ed521; usar uma biblioteca mantida não autentica as entradas.

## Reprodução e preservação

Executar em árvore nova com as entradas e originais das etapas anteriores. As capturas e saídas preenchidas não são sobrescritas. `--dest` escolhe outra pasta de saída; não altera a árvore de fontes.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[auditoria,test]'
.\.venv\Scripts\python.exe scripts/preparar_caminho_pkix.py --data data
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --data data --etapa caminho
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 scripts/validar_pkix.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe scripts/preservar_documentacao.py --check
```

O gerador opcional `scripts/gerar_fixture_pkix.py` depende de Node e das dependências instaladas por `npm ci` em `scripts/ed521_reference/`. Os testes usuais consomem a fixture preservada e não precisam de Node nem rede. A captura complementar fica em `data/auditoria/pkix/v1/`, com manifesto próprio. Os certificados reais completos e VSC não são redistribuídos no pacote deste incremento; a fixture sintética é identificada como tal.

**Validação executada:** 194 testes aprovados; 543 avisos de depreciação da dependência ASN.1, sem falhas. Três pares CSV/Parquet foram comparados integralmente com tipos, oito links locais conferidos e o PDF de cinco páginas/cinco marcadores validado por conteúdo/margens. HTML e três páginas do PDF foram inspecionados renderizados. Oito manifestos amostrais e os 578 artefatos originais mantiveram seus hashes. Os [registros da execução](../outputs/logs/README.md) identificam cada verificação; os [metadados públicos das fontes](pkix-fontes.json) preservam as 11 consultas, sem incluir certificados reais completos.

[Pacote público do incremento](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/caminho-pkix-amostral-v1). Extrair na mesma árvore dos pacotes anteriores para resolver os links cruzados. As versões anteriores permanecem disponíveis e não foram substituídas.

## O que falta para concluir o item 1

- Obter os certificados de emissores faltantes e as raízes aplicáveis, com proveniência oficial verificável; documentar e fixar a seleção das âncoras.
- Esclarecer qual certificado de AC URNA era aplicável às 14 ocorrências, sem presumir renovação, reaproveitamento de chave ou motivo operacional.
- Obter LCR assinadas e adequadas às datas analisadas, inclusive para os intermediários; executar a passagem estrita sobre caminhos efetivamente construídos.
- Confrontar a configuração com o perfil oficial TSE e documentar políticas ou extensões adicionais exigidas. Reexecutar numa versão separada quando essas evidências chegarem.

Não se substitui essa falta de fonte por uma conclusão estatística. Logs, CEPESC, layout oficial, BU independente e eficácia temporal do ato dos nulos técnicos continuam frentes distintas.
