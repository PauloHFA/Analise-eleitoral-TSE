# Certificados da amostra — vínculos, vigência e revogação

Este incremento verifica o vínculo entre os certificados das urnas e **três intermediários candidatos**. Não é validação integral de uma cadeia de confiança. A consulta de revogação procura Listas de Certificados Revogados (LCR). As entregas anteriores de RDV, hashes, ECDSA e Ed521 continuam preservadas.

## Resultado e alcance

| Pergunta | Universo | Resultado |
| --- | --- | --- |
| A assinatura da ponta confere com a chave de um candidato intermediário compatível? | 48 ocorrências, 25 certificados de ponta distintos | Sim, nos 48 casos |
| O certificado intermediário candidato cobre a data declarada no VSC? | 48 unidades seção/turno | 34 compatíveis; 14 fora do intervalo |
| Existe caminho completo validado até âncora oficial? | 48 unidades | Nenhum concluído nesta etapa |
| Foi obtida LCR utilizável para conclusão de revogação? | Cinco pontos de distribuição, tentativas HTTP e HTTPS | Nenhuma obtida; status indeterminado |
| O leitor de LCR foi implementado? | Dados sintéticos controlados | Sim, para LCR completa/direta; não executado com LCR real |

São 48 ocorrências nos dois turnos, não 48 urnas necessariamente distintas. A amostra tem 24 seções, mas 25 certificados de ponta distintos. A contagem não presume que o equipamento ou certificado permaneceu igual entre turnos.

**A assinatura matemática que confere não basta para afirmar confiança institucional.** Nenhum candidato foi promovido a âncora. Nenhuma LCR obtida significa revogação **indeterminada**, não ausência demonstrada de revogação. O zero de caminhos completos descreve o alcance do trabalho, não uma frequência de irregularidade eleitoral.

## Apontamento de vigência a esclarecer

O certificado candidato **AC URNA**, SHA256 DER `dc20a4c3b8aef01794b80efe8e143e1fbf719707e00bb0d4ba8865191dc2731d`, tem validade até **18/07/2026 21:59:57 UTC**. Ele é o intermediário candidato para **14 ocorrências** cujos VSC declaram datas de outubro de 2026.

A chave desse candidato verifica as assinaturas dos certificados de ponta dessas ocorrências, mas isso não altera a data de validade do certificado intermediário disponível. Os 48 certificados de ponta, considerados nas respectivas ocorrências, têm sua própria compatibilidade temporal registrada separadamente. As 14 ocorrências estão na [tabela de pendências](../outputs/2026/auditoria/cadeia/pendencias_vigencia.csv) e no relatório.

**A causa não foi confirmada.** Não foi obtido documento indicando qual certificado intermediário era aplicável às datas. Não se presume renovação, reaproveitamento de chave, falha operacional ou outra explicação. O achado não é classificado automaticamente como fraude, revogação ou invalidação dos votos.

AC UE2020 (quatro ocorrências) e AC UE2022 (30) são compatíveis com as datas declaradas. Essa constatação não valida seus emissores, a cadeia completa ou revogação.

## Fontes e obtenção

Os candidatos foram extraídos como **dados**, sem executar o código, da constante do pacote técnico já preservado, SHA256 `1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235`. A origem é um [espelho de terceiros](https://github.com/doccaz/urnas-br/tree/main/docv2), cuja limitação foi registrada nas etapas anteriores. Apesar do nome da constante, os três certificados são tratados como **intermediários candidatos**, não como raízes confiáveis.

| Candidato | Emissor indicado no certificado | SHA256 DER |
| --- | --- | --- |
| AC URNA | AC RAIZ UE | `dc20a4c3b8aef01794b80efe8e143e1fbf719707e00bb0d4ba8865191dc2731d` |
| AC UE2020 | AC URNA v2 | `77f31bef3d8eb35f0cc969a2b9bba3ff2a498cc339d29a375d3181e0547c0376` |
| AC UE2022 | AC URNA v2 | `6ae65790dae7cc5d97394e461204744c8e2f7a810d0303af828d4d3dbecfa293` |

Foram registradas **21 tentativas**: 13 respostas HTTP 403 e oito erros TLS, sem resposta HTTP 200. Os cinco pontos de LCR provêm dos certificados; foram tentadas também alternativas HTTPS. Endereços de certificados de raiz/emissor são candidatos citados em referência de terceiros, não documentos obtidos diretamente. TLS não foi desativado e não houve contorno de autenticação. Erro de acesso deste ambiente não demonstra inexistência dos documentos.

A [página de hashes de 2026 do TSE](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash/resumos-digitais-hashes-das-eleicoes-2026-1o-e-2o-turnos) foi consultada via extração e vincula o recurso HOLOCRON. O download binário desse recurso retornou HTTP 403. Uma [cópia em repositório de terceiros](https://github.com/havaianasdestruido/resumos-eleicao-2026/blob/main/extracted/pc1holo/pc1holo.html) contém hashes que correspondem aos PEM de AC UE2020/2022 extraídos. **Essa correspondência com uma cópia não foi usada como publicação oficial autenticada ou âncora de confiança.** Os hashes de extrações de páginas, quando registrados, identificam a captura, não os bytes originais do servidor.

O método é delimitado em relação à [RFC 5280](https://www.rfc-editor.org/rfc/rfc5280.html). A referência é usada para distinguir assinatura, restrições, validade e revogação; esta implementação de um vínculo não executa todo o algoritmo da RFC.

## Método implementado

1. Conferir os hashes dos originais locais e das três cópias candidatas, sem alterar as fontes anteriores.
2. Extrair o certificado de ponta do VSC e relacionar candidato por nome do emissor. Não escolher arbitrariamente entre candidatos ausentes ou ambíguos.
3. Conferir nome, AKI/SKI, indicação de CA e permissão `keyCertSign`; verificar a assinatura da ponta com a chave candidata. ECDSA P-521/SHA512 e Ed521 são suportados. **O certificado assina os bytes TBS diretamente**, sem o wrapper `SHA512(hash)` dos documentos VSC.
4. Registrar separadamente a compatibilidade temporal da ponta e do intermediário, usando o intervalo possível UTC−12 a UTC+14 para a data declarada. Ela não é carimbo de tempo autenticado.
5. Manter o caminho incompleto, pois não foi estabelecida âncora oficial nem validado o restante da cadeia. As flags de criticidade dos intermediários são expostas na tabela, sem concluir conformidade integral das extensões com um perfil.
6. Tratar LCR ausente como indeterminada. O avaliador só aceita LCR completa/direta com emissor, chave/permissão, assinatura e período compatíveis. Delta LCR, escopo indireto/não suportado, assinatura errada, período vencido e extensões críticas não tratadas não geram conclusão positiva. A presença/ausência de serial é uma observação de LCR verificada, não uma validação de cadeia.

Os caminhos de LCR foram exercitados apenas com material sintético. Não foi feita consulta OCSP; não foi identificada extensão AIA nas 48 ocorrências. O código também não infere status histórico usando uma LCR posterior às datas analisadas. Na execução, todas as 48 revogações permanecem indeterminadas.

## Implementado, limitado e ainda não implementado

| Frente | Código | Execução com evidência real |
| --- | --- | --- |
| Vínculo ponta–intermediário | Implementado | 48 assinaturas conferem com candidatos |
| Datas e restrições suportadas do candidato | Implementado | 34 compatíveis; 14 pendentes de esclarecimento |
| LCR completa/direta | Implementado e testado com dados sintéticos | Não executada com LCR real, por falta de obtenção |
| Validação integral de caminho RFC 5280 e âncora oficial | Ainda não implementada nesta rotina | Cadeia/emissores/âncora não obtidos e validados |
| OCSP e prova histórica de revogação | Não implementados | Nenhuma conclusão de revogação |
| CEPESC | Não implementado | Continua sem verificação |
| Eventos dos logs e BU independente | Frentes posteriores | Logs preservados; nenhuma conferência independente em papel |

## Artefatos e reprodução

[Pacote público deste incremento](https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/cadeia-certificados-amostral-v1), com tabelas completas, relatórios e metadados de fontes. Extrair na mesma árvore das entregas anteriores para resolver os links. Certificados completos e VSC brutos não são redistribuídos neste pacote.

[HTML](../outputs/2026/auditoria/cadeia/relatorio.html) · [PDF](../outputs/2026/auditoria/cadeia/relatorio.pdf) · [síntese](../outputs/2026/auditoria/cadeia/resumo.json) · [48 vínculos](../outputs/2026/auditoria/cadeia/vinculos.csv) · [intermediários](../outputs/2026/auditoria/cadeia/intermediarios.csv) · [tentativas](../outputs/2026/auditoria/cadeia/tentativas.csv).

Os quatro pares CSV/Parquet incluem `pendencias_vigencia`, com as 14 ocorrências completas. Fontes de preparação são preservadas separadamente em `data/auditoria/cadeia/v1/`, com manifesto próprio; nenhuma chave privada foi obtida. Usar uma árvore nova e as entradas das entregas anteriores na reprodução completa.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[auditoria,test]'
# Reutiliza o pacote técnico preservado; consulta só documentos públicos
.\.venv\Scripts\python.exe scripts/preparar_cadeia.py --data data
.\.venv\Scripts\python.exe -m eleicoes auditoria --output outputs/2026 --data data --etapa cadeia
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings
.\.venv\Scripts\python.exe -X utf8 scripts/validar_cadeia.py --output outputs/2026 --data data
.\.venv\Scripts\python.exe scripts/preservar_documentacao.py --check
```

Preparação e análise recusam sobrescrever pastas preenchidas; `--dest` permite versões separadas de cada etapa. Alterar `--dest` não muda automaticamente a pasta de fontes usada pela análise. Em reprodução de uma fonte diferente, manter a organização esperada em uma nova pasta `--data`. Não misturar conclusões de capturas feitas em datas diferentes.

## O que falta e próximos passos possíveis

**Validação executada:** 185 testes aprovados, incluindo nove novos de vínculo/LCR; quatro pares CSV/Parquet completos comparados com tipos; 48 assinaturas de certificados reconferidas; nove links locais conferidos. O PDF tem seis páginas e seis marcadores, com conteúdo/margens verificados e páginas renderizadas inspecionadas; HTML inspecionado no Chrome headless. Os sete manifestos amostrais anteriores e seus arquivos e os 578 artefatos originais foram preservados. Os 362 avisos da suíte são de depreciação da dependência ASN.1, sem falhas.

Para concluir confiança: obter os emissores e a âncora com proveniência oficial, implementar a validação integral do caminho/perfil e obter evidência de revogação aplicável às datas. Para os 14 casos, esclarecer documentalmente qual certificado de AC URNA era aplicável. Nenhum contato externo foi enviado.

Enquanto essas fontes permanecem pendentes, a próxima frente executável com os arquivos locais é **analisar os eventos dos 48 logs**, com critérios próprios e sem reconstruir escolhas individuais. Também continuam abertos CEPESC, confirmação oficial do layout VSC, BU de fonte independente e ato individual/eficácia temporal dos nulos técnicos.
