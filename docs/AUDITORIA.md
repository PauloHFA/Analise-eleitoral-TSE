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

O [TSE descreve esses procedimentos de auditoria](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria). A seleção concluída não significa que os documentos já foram obtidos ou conferidos. A situação de cada etapa será registrada aqui à medida que houver execução verificável.
