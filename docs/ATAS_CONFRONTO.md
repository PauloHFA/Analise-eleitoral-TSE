# Recepção local e confronto de documentos

## Situação da pesquisa

A pesquisa individual cobre as 28 unidades seção/turno, mas a versão ampliada não contém ata de mesa receptora nem registro individualizado de atendimento/substituição. A etapa seguinte depende de documentos obtidos por fonte pública ou de resposta oficial. Este fluxo não faz novas buscas, não baixa arquivos, não envia pedidos e não contorna controles de acesso.

## Registro de material recebido

Depois de obter e revisar um documento por meios autorizados, prepare localmente um JSON com uma entrada por arquivo:

```json
{
  "documents": [
    {
      "case": {
        "year": 2026,
        "turn": 2,
        "uf": "BA",
        "municipality": "34193",
        "zone": "53",
        "section": "274"
      },
      "indicator": "nested_payloads",
      "document_kind": "resposta_oficial",
      "source_url": "https://www.tre-ba.jus.br/caminho/da-resposta",
      "title": "Resposta oficial sobre a consulta documentada",
      "document_path": "D:\\evidencias\\resposta.pdf",
      "locator": "página 1, trecho sobre abrangência da consulta",
      "justification": "A resposta identifica os registros consultados e o intervalo informado.",
      "finding": "inconclusivo",
      "review_status": "revisao_documental_registrada"
    }
  ]
}
```

`case` e `indicator` devem corresponder exatamente a um apontamento em `confronto.parquet`. Tipos de documento de ocorrência permitidos: `ata_mrv`, `registro_atendimento` e `registro_substituicao`. `resposta_oficial` registra apenas o alcance da resposta; seu resultado obrigatório é `inconclusivo`, nunca corroboração ou contradição do evento. Os resultados de revisão aceitos são `corrobora_registro`, `contradiz_registro` e `inconclusivo`; contradições permanecem para revisão e não confirmam persistência.

O importador aceita somente URL HTTPS de domínio eleitoral oficial, caminho para arquivo local não vazio de formato permitido e até 50 MiB, localização no documento, justificativa e revisão registrada. A URL, o tipo e a revisão são declarações; não autenticam sozinhos origem, assinatura ou integridade jurídica do documento. O importador calcula SHA256 e preserva os bytes originais sem extrair conteúdo ou executar arquivos.

```powershell
.\.venv\Scripts\python.exe scripts\registrar_evidencia_atas.py `
  --registro D:\evidencias\registro.json `
  --output outputs\2026 `
  --data data
.\.venv\Scripts\python.exe -m eleicoes auditoria `
  --output outputs\2026 --data data --etapa atas-confronto
.\.venv\Scripts\python.exe -X utf8 scripts\validar_atas.py `
  --output outputs\2026 --data data --confronto
```

A captura `v3` deriva da ampliação `v2`, preserva seus arquivos e registra o novo documento sob `data/auditoria/atas/v3/documentos/`. A saída é separada em `outputs/2026/auditoria/atas_confronto/`; o relatório v2 não é substituído. Os documentos originais ficam sob `data/`, que é ignorada pelo Git, e não são copiados para os relatórios ou pacotes públicos. Não incluir dados pessoais desnecessários na justificativa, localização ou título.

O relatório reavalia cada apontamento com unidade, turno, tipo documental, localização e revisão. Um documento pode corroborar ou contradizer apenas o registro delimitado; uma resposta oficial permanece inconclusiva sobre a ocorrência. A rotina mantém `causes_confirmed` como `null` e `requests_sent` como zero. Caso não haja documento local recebido, não há confronto novo a executar; ausência de resultado de busca não preenche essa lacuna.

## Validação de desenvolvimento

O fluxo foi exercitado com documento sintético temporário para validar cópia por hash, vínculo exato e geração de relatório. Esse fixture não é fonte eleitoral nem evidência de qualquer caso. A execução substantiva aguarda documentos reais e revisão correspondente.
