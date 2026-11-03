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

## Registros da pesquisa documental

`execucao-pesquisa.log` registra a geração local dos relatórios a partir das evidências revisadas. `validacao-pesquisa.log` confere as fontes/capturas, vínculos das unidades, identidade da candidatura, ausência de conclusão causal automática e igualdade CSV/Parquet. `testes-pesquisa.log` contém a suíte de 113 testes deste incremento.

## Registros do dossiê local

`execucao-dossie.log` registra o processamento nacional do primeiro passo da frente 3. `validacao-dossie.log` confere os hashes, as parcelas, as três unidades de cobertura, as 2.231 âncoras e os cinco pares CSV/Parquet pelo multiconjunto tipado completo. `testes-dossie.log` contém a execução da suíte após este incremento. Os logs das rodadas anteriores são preservados como registros de suas respectivas validações.
