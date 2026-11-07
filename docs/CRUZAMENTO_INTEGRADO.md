# Cruzamento integrado local — logs, votos, indicadores e assinaturas

Este incremento cruza somente os arquivos já presentes na base local. Não houve download, contato externo, alteração das fontes ou inferência causal. A saída é uma análise descritiva das 24 seções selecionadas (48 unidades seção/turno), não uma estimativa nacional.

[Relatório HTML](../outputs/2026/auditoria/cruzamento_integrado/relatorio.html) · [PDF](../outputs/2026/auditoria/cruzamento_integrado/relatorio.pdf) · [síntese](../outputs/2026/auditoria/cruzamento_integrado/resumo.json) · [lacunas](../outputs/2026/auditoria/cruzamento_integrado/sem_correspondencia.csv).

## Método

- Chave territorial comum: ano, turno, UF, município, zona e seção. Os indicadores de 2026 não têm turno; são ligados pela chave territorial sem turno, na relação muitos-para-um, mantendo as unidades dos dois turnos separadas.
- Os logs são ligados às assinaturas de hardware, aos apontamentos, à conferência amostral por candidato e à comparação nacional por candidato. As chaves sem correspondência permanecem explícitas.
- A conferência amostral compara RDV, BU binário, imagem e arquivos de resultado/BU. A comparação nacional é uma fonte distinta; chave sem linha nela não é divergência nem voto zero.
- O estado criptográfico informado é o resultado da verificação local com chave embutida e hash correspondente. Não valida cadeia institucional, revogação, confiança oficial ou proveniência independente.
- As contingências são contagens descritivas por grupo, região, presença de mensagem ERRO e estados das fontes de voto; não testam causalidade.

## Resultados

| Medida | Resultado |
| --- | --- |
| Unidades seção/turno | 48, em 24 seções |
| Apontamentos dos logs | 33 linhas em 28 unidades seção/turno |
| Correspondência de indicadores | 48/48 unidades |
| Correspondência de hash e assinatura dos logs | 48/48; hash concordante e assinatura válida com chave embutida |
| Conferência amostral por candidato | 265 linhas completas e concordantes; nenhuma discordância de valores |
| Linhas de candidato com correspondência na comparação nacional | 255; nenhuma diferença não nula |
| Chaves de candidato sem linha na comparação nacional | 10: candidato 95 em 8 linhas e candidato 96 em 2 |

Os códigos 95 e 96 não são candidaturas: na exportação, 95 representa votos brancos e 96, votos nulos ([critério documentado na conferência](AUDITORIA.md)). As dez chaves são:

| Turno | UF | Município | Zona | Seção | Chave ausente | Outra categoria presente, votos local/nacional |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | BA | 34193 | 53 | 231 | 95 — brancos | 96 — nulos: 3 / 3 |
| 1 | GO | 95613 | 29 | 40 | 95 — brancos | 96 — nulos: 6 / 6 |
| 1 | PA | 4057 | 16 | 137 | 95 — brancos | 96 — nulos: 3 / 3 |
| 1 | ZZ | 29416 | 1 | 3466 | 96 — nulos | 95 — brancos: 2 / 2 |
| 2 | AC | 1139 | 7 | 47 | 95 — brancos | 96 — nulos: 4 / 4 |
| 2 | BA | 34193 | 53 | 274 | 95 — brancos | 96 — nulos: 1 / 1 |
| 2 | CE | 15997 | 109 | 220 | 95 — brancos | 96 — nulos: 4 / 4 |
| 2 | GO | 95613 | 29 | 44 | 95 — brancos | 96 — nulos: 2 / 2 |
| 2 | PA | 4057 | 16 | 137 | 95 — brancos | 96 — nulos: 2 / 2 |
| 2 | ZZ | 29416 | 1 | 3466 | 96 — nulos | 95 — brancos: 1 / 1 |

Em todas as dez chaves, RDV, BU binário, imagem e as duas fontes tabulares da conferência amostral registram zero para a categoria ausente. Na categoria complementar, os cinco valores locais também coincidem com os votos nacionais indicados na tabela. A tabela nacional tem outras categorias concordantes na mesma unidade; portanto, não falta toda a seção na comparação, mas especificamente a linha daquela categoria.

O padrão é consistente com a omissão de linhas nacionais de valor zero: para as oito chaves brancas, há votos nulos positivos; para as duas chaves nulas, há votos brancos positivos. Essa é uma explicação forte para o padrão observado, mas não substitui uma especificação formal da regra de exportação. Como não existe linha nacional para a própria chave ausente, seus valores nacionais continuam nulos, não zero. A análise não transforma as ausências em divergências nem em evidência de irregularidade.

Nas 24 unidades com mensagem ERRO, a conferência amostral também está concordante, e não há diferença nacional não nula nas linhas correspondentes. Esse cruzamento não demonstra que o erro não afetou a votação, nem confirma sua causa ou efeito. A conferência é amostral e não equivale a uma apuração independente em papel.

## Artefatos e reprodução

O diretório de saída contém tabelas CSV e Parquet de unidades, apontamentos, candidatos, lacunas e contingências, além de resumo, manifesto, HTML e PDF. A etapa verifica os manifestos das entradas antes de cruzá-las e gera os próprios hashes das saídas.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m eleicoes auditoria --output outputs/2026 --etapa cruzamento-integrado
.\.venv\Scripts\python.exe -X utf8 scripts\validar_cruzamento.py --output outputs/2026
.\.venv\Scripts\python.exe -m pytest tests\test_audit_crosswalk.py
```

Validação independente: 48 unidades, 33 apontamentos, 265 linhas de candidato, 10 chaves sem correspondência, cinco pares CSV/Parquet comparados com tipos, 12 links locais e PDF de duas páginas/quatro marcadores dentro das margens. Os dois testes focados passaram. A suíte completa passou com 251 testes e 543 avisos de depreciação ASN.1. `git diff --check` passou após a alteração do validador para usar conexões isoladas por tabela.

## Pendências interpretativas

As dez chaves são categorias de brancos/nulos sem linha nacional, apesar de valores zero nas cinco fontes amostrais. Em cada unidade, a categoria complementar tem votos positivos e concordantes entre as fontes locais e nacionais; isso torna provável que a linha nacional da categoria ausente tenha sido omitida por valor zero, embora a regra de exportação não tenha sido confirmada formalmente. A comparação não imputa valores nacionais. A cadeia institucional das assinaturas, a independência da conferência e os motivos operacionais dos logs também não são validados por este cruzamento. Para confirmar causas ou impacto seriam necessários registros independentes específicos, que não estão nesta base.
