# 📋 Pendências e Próximos Passos — Analise-eleitoral-TSE

> Documento padronizado de rastreabilidade de entregas, limites metodológicos e pendências documentais do projeto **Analise-eleitoral-TSE** (ver roteiro detalhado em [`docs/PROXIMAS_ETAPAS.md`](docs/PROXIMAS_ETAPAS.md)).

---

## ✅ 1. O que já está Concluído e Validado (Offline / Reproduzível)

- **Processamento Nacional Completo (`499.248` Seções & `5.571` Municípios):**
  - Separação estrita entre Brasil e exterior; vínculo TSE–IBGE completo preservado.
  - Conferência integral de `5.731.614` linhas de votação (`BU × resultado`).
- **Frentes 1, 2 e 4 Executadas e Validadas:**
  - Estabilidade de pares (`15/30/50`), cobertura e exclusões territoriais, inventário nacional, taxas com cobertura e mapas municipais em HTML/PDF.
- **Auditoria Criptográfica e Documental Amostral (`48` Unidades / `240` Arquivos):**
  - Decodificação estrita ASN.1 de RDV, BU binário e VSC.
  - Verificação de assinaturas de hardware **ECDSA** (`70` verificações) e **Ed521** (`170` verificações) conferidas contra vetores independentes Noble (`340` comparações).
  - Motor de validação **PKIX** (`pyhanko-certvalidator` + adaptador Ed521 + checagem de revogação LCR).
  - Análise de **287.649 registros de logs** identificando 33 ocorrências `ERRO`, retrocesso de relógio e 33 apontamentos em 28 unidades.
  - Cruzamento integrado local (`265` linhas amostrais concordantes).
- **Engenharia & Qualidade de Software:**
  - Suíte com **258 testes automatizados** passando com 100% de aprovação (`pytest`).
  - Linter **Ruff** configurado e 100% limpo (`0 erros`).
  - Esteira **GitHub Actions CI** automatizada.

---

## 📄 2. Dependências Externas (Documentos Oficiais Pendentes)

O encerramento substantivo das investigações documentais abertas (Frentes 3 e 5) depende exclusivamente da obtenção externa de documentos oficiais não disponíveis publicamente nas bases abertas consultadas:
- [ ] **Cadeia Institucional Completa & Âncoras PKIX:** Disponibilização oficial das cadeias de certificação completas AC Raiz/TSE, CEPESC e listas de revogação (LCRs) vigentes para validar as 14 pendências de vigência e as 48 unidades hoje inconclusivas sem âncora.
- [ ] **Atas Individuais de Atendimento e Substituição:** Obtenção de atas específicas de seção/urna para confrontar os 33 apontamentos dos logs nas 28 unidades (busca automática em 55 resultados públicos não retornou atas individuais).
- [ ] **Consulta de Processo da Candidatura 28 (`ID 280002554479`):** Acesso completo aos autos de renúncia e eficácia temporal (bloqueado em consultas automatizadas por CAPTCHA) para encerramento formal da Frente 3 (5.246 nulos técnicos).
- [ ] **BU de Origem Independente:** Confronto com vias físicas/impressas independentes dos Boletins de Urna.

---

## 🚀 3. Melhorias Futuras Opcionais (Backlog de Engenharia)
- [ ] **Automação de Coleta com Resolução Assistida de CAPTCHA:** Fluxo interativo opcional para coleta do processo judicial da Frente 3 pelo usuário.
- [ ] **Publicação Contínua via GitHub Pages:** Exposição automática dos relatórios HTML (`outputs/2026/relatorio.html`) caso o usuário decida tornar a visualização navegável online.
