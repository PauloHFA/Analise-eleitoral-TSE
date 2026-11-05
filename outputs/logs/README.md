Os registros desta pasta preservam a execução e os diagnósticos do desenvolvimento.
Falhas antigas de importação ou ajuste de desempenho não representam a validação final.

Resultados finais:

- `testes-documentacao.log`: suíte vigente após a revisão da documentação; `testes-validacao-final.log` é de uma execução anterior.
- `validacao-entrega.log`: validação dos relatórios e tabelas dos três anos.
- `execucao.log`: processamento nacional e ingestão dos boletins.
- `conferencia-final.log`: atualização das composições e totais.
- `categorias-final.log`: conferência de categorias de destinação.
- `relatorio-final.log`: geração final de HTML e PDF.
- `investigacao.log`: execução dos zeros nacionais, viradas em RJ/MG e respectivas provas.
- `validacao-investigacao.log`: conferência das fichas dirigidas e filtros JavaScript offline.
- `mapa-preparacao.log`: fontes geográficas e cobertura do vínculo TSE–IBGE.
- `validacao-mapa.log`: votos, cores dos dois turnos e controles do mapa.
- `relatorio-documentacao.log`: regeneração do HTML/PDF com o resumo executivo comum.
- `documentacao.log`: geração da síntese e do README.
- `validacao-sintese.log`: coerência entre fontes, síntese, README, HTML e texto do PDF.
- `preservacao-documentacao.json`: hashes anteriores à revisão para conferir a preservação de tabelas, fichas e mapas.
- `preservacao-documentacao-conferencia.log`: resultado da conferência final dos hashes.
- `validacao-publicacao.log`: hashes dos pacotes e de todos os arquivos incluídos na release.
- `validacao-pdf.log`: edição explicativa do PDF; sumário, contagens, fichas, margens e proporções das imagens.
- `testes-incrementos.log`: suíte após estabilidade, cobertura e leitores CSV estritos.
- `validacao-incrementos.log`: entradas por hash, conteúdo tipado das tabelas novas, pares, rankings, grupos e cobertura.

## Registros do dossiê de atas e atendimento

`fontes-atas.log` resume seis buscas individuais, 18 resultados, 12 fontes de contexto e zero documento específico obtido. `auditoria-atas.log` registra a geração do dossiê. `testes-atas.log` contém 228 testes aprovados, incluindo 17 novos, com 543 avisos de depreciação ASN.1. `validacao-atas.log` confere seis pares CSV/Parquet, preservação dos 33 apontamentos, 28 fichas/28 minutas, dez manifestos anteriores, 123 links, 3.132 condições dos filtros e PDF de cinco páginas/seis marcadores. `preservacao-atas.log` confirma os 578 artefatos originais. Vinte e duas unidades ainda não receberam busca individual; nenhuma minuta foi enviada e nenhuma causa foi confirmada.

## Registros da análise dos logs das urnas

`auditoria-logs.log` registra a execução descritiva dos 48 ZIPs/49 membros. `testes-logs.log` contém 211 testes aprovados, incluindo 17 novos, com 543 avisos de depreciação ASN.1. `validacao-logs.log` confere sete pares CSV/Parquet completos, 48 originais, datas-alvo, nove manifestos anteriores, 12 referências locais, 5.292 condições dos filtros e PDF de sete páginas/sete marcadores. `preservacao-logs.log` confirma os 578 artefatos originais. Os 33 registros ERRO e os 33 apontamentos em 28 unidades são contagens distintas; nenhum impacto nos votos foi inferido.

## Registros do backend PKIX

`fontes-pkix.log` registra 11 consultas complementares sem objeto obtido. `auditoria-pkix.log` é a execução do backend; `testes-pkix.log` registra 194 testes aprovados e 543 avisos de depreciação ASN.1. `validacao-pkix.log` confere três pares CSV/Parquet completos, 48 unidades/144 hipóteses inconclusivas, 14 pendências preservadas, oito manifestos anteriores, oito links locais e PDF de cinco páginas/cinco marcadores. `preservacao-pkix.log` confere os 578 artefatos originais. O sucesso sintético não é atribuído à amostra; a revogação real não foi avaliada sem caminho.

## Registros de vínculos e consulta de revogação

`fontes-cadeia.log` resume a preparação dos candidatos e as 21 tentativas; `auditoria-cadeia.log` registra a execução dos 48 vínculos. `testes-cadeia.log` contém 185 testes aprovados. `validacao-cadeia.log` confere quatro pares CSV/Parquet, 48 reconferências criptográficas, 14 pendências de vigência, links/PDF e os sete manifestos anteriores. `preservacao-cadeia.log` confirma os 578 artefatos originais. Nenhuma cadeia completa ou revogação real foi concluída; LCR não obtida permanece indeterminada.

## Registros do incremento Ed521

`auditoria-ed521.log` registra a verificação estendida; `referencia-ed521.log`, a comparação independente de 170 originais e 170 mensagens alteradas e a fronteira de política esperada. `testes-ed521.log` contém 176 testes aprovados. `validacao-ed521.log` confere cinco pares CSV/Parquet, resultados/escopo, PDF/links, hash do documento técnico do ITI e preservação dos cinco manifestos amostrais anteriores. `preservacao-ed521.log` confirma os 578 artefatos originais. Os vetores são gerados pelo projeto com referência independente, sem caráter oficial; cadeia, revogação e CEPESC não são validados.

## Registros do incremento de assinaturas

`auditoria-assinaturas.log` registra a execução da leitura observada, hashes SW/HW e verificação ECDSA com a chave embutida. `testes-assinaturas.log` registra 160 testes aprovados. `validacao-assinaturas.log` confere os quatro pares CSV/Parquet, 48 unidades, escopo das 1.008 entradas, separação entre hash/criptografia/confiança, links e PDF. `preservacao-assinaturas.log` confirma os 578 artefatos anteriores. Os resultados não validam Ed521, CEPESC, cadeia ou revogação.

## Registros da primeira conferência amostral

`auditoria-amostra.log` registra a seleção anterior aos documentos; `auditoria-documentos.log`, a obtenção seletiva; `auditoria-conferencia.log`, a recontagem agregada; e `auditoria-relatorio.log`, o relatório complementar. `testes-auditoria.log` registra 151 testes aprovados (avisos de depreciação da dependência ASN.1). `validacao-auditoria.log` confere os seis pares CSV/Parquet completos, 240 originais, 48 unidades, 265 linhas, links, filtros e o PDF. `preservacao-auditoria.log` confirma os 578 hashes anteriores. Assinaturas criptográficas, cadeia e eventos dos logs não foram verificados; essa limitação consta dos resultados e não é uma validação negativa das assinaturas.

## Registros da investigação nacional

`nacional-inventario.log`, `nacional-taxas.log` e `nacional-mapas.log` registram as três execuções. `validacao-nacional.log` confere tabelas tipadas, referência, coortes, 84 escores, geografia e 33.467 condições da interface. `testes-nacional.log` registra 135 testes aprovados; `preservacao-nacional.log` confirma os 578 hashes anteriores. Os logs de validações anteriores mantêm suas contagens históricas.

## Registros da pesquisa documental

`execucao-pesquisa.log` registra a geração local dos relatórios a partir das evidências revisadas. `validacao-pesquisa.log` confere as fontes/capturas, vínculos das unidades, identidade da candidatura, ausência de conclusão causal automática e igualdade CSV/Parquet. `testes-pesquisa.log` contém a suíte de 113 testes deste incremento.

## Registros do dossiê local

`execucao-dossie.log` registra o processamento nacional do primeiro passo da frente 3. `validacao-dossie.log` confere os hashes, as parcelas, as três unidades de cobertura, as 2.231 âncoras e os cinco pares CSV/Parquet pelo multiconjunto tipado completo. `testes-dossie.log` contém a execução da suíte após este incremento. Os logs das rodadas anteriores são preservados como registros de suas respectivas validações.
