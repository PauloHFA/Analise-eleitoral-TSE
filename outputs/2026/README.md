# Resultados eleitorais — 2026

## Relatórios principais

- **[Relatório principal HTML](relatorio.html)** — leitura interativa, navegação e tabelas.
- **[Relatório principal PDF](relatorio.pdf)** — edição narrativa para leitura e impressão.

Os relatórios principais preservam o núcleo estatístico da análise-base. Esta edição acrescenta um quadro editorial com resultados posteriores, sem misturar universos, métricas ou denominadores entre etapas.

## Análises locais complementares

### Cruzamento integrado

- [Relatório HTML](auditoria/cruzamento_integrado/relatorio.html) · [PDF](auditoria/cruzamento_integrado/relatorio.pdf)
- Cruzamento de 48 unidades seção/turno em 24 seções: 33 apontamentos em 28 unidades. As 265 linhas amostrais de votação estão completas e concordantes; nas 255 linhas com correspondência nacional não houve diferença não nula.
- Dez chaves de categoria não têm linha nacional: oito de brancos (código 95) e duas de nulos (código 96). Os valores nacionais dessas chaves continuam ausentes, não são tratados como zero. Os valores zero observados nas cinco fontes da amostra tornam provável a omissão de linhas sem votos, mas a regra de exportação não foi confirmada formalmente.
- Método, tabela das dez chaves, hashes e limitações estão no [relatório detalhado](auditoria/cruzamento_integrado/relatorio.html) e em [CRUZAMENTO_INTEGRADO.md](../../docs/CRUZAMENTO_INTEGRADO.md).

### Pesquisa documental ampliada

- [Relatório HTML](auditoria/atas_ampliacao/relatorio.html) · [PDF](auditoria/atas_ampliacao/relatorio.pdf)
- Houve busca individual nas 28 unidades, com 55 resultados e 34 fontes de contexto revisadas. Nenhum documento específico dos casos foi obtido; 28 minutas locais não foram enviadas.
- A cobertura das buscas não confirma causas nem demonstra a inexistência de documentos. Nenhum contato externo foi realizado.

## Escopo e reprodução

As etapas complementares usam os arquivos e registros locais já preservados. Os relatórios são descritivos, a amostra é dirigida e não estima resultados nacionais. Concordância entre arquivos não prova independência de fonte, causa ou efeito nos votos; a validação de assinatura com chave embutida não equivale à validação da cadeia institucional.

Para regenerar a apresentação principal com as tabelas locais existentes, sem baixar dados:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\gerar_relatorio.py outputs\2026
```
