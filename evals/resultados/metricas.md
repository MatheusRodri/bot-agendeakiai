# Métricas por versão do sistema

Fonte: 208 traces em `evals/resultados/*/traces.jsonl`. Cada `invoke_agent` é uma execução; uma retomada após aprovação humana é uma segunda execução.

| versão | execuções | latência p50 (ms) | latência p95 (ms) | custo médio (US$) |
|---|---|---|---|---|
| 2.0.0 | 31 | 13.8 | 20.0 | 0.0000 |
| 3.0.0 | 31 | 13.2 | 85.8 | 0.0000 |
| 3.1.0 | 31 | 13.5 | 54.7 | 0.0000 |
| 3.1.0-gemini | 9 | 11886.5 | 118606.1 | 0.0002 |
| 3.2.0 | 53 | 13.0 | 52.2 | 0.0000 |
| 3.2.0-sem-controles | 53 | 13.5 | 36.2 | 0.0000 |

## Motivos de término

| versão | motivo | n | % |
|---|---|---|---|
| 2.0.0 | resposta_final | 22 | 71% |
| 2.0.0 | aguardando_humano | 5 | 16% |
| 2.0.0 | agendamento_confirmado | 2 | 6% |
| 2.0.0 | aprovacao_rejeitada | 2 | 6% |
| 3.0.0 | resposta_final | 22 | 71% |
| 3.0.0 | aguardando_humano | 5 | 16% |
| 3.0.0 | agendamento_confirmado | 2 | 6% |
| 3.0.0 | aprovacao_rejeitada | 2 | 6% |
| 3.1.0 | resposta_final | 22 | 71% |
| 3.1.0 | aguardando_humano | 5 | 16% |
| 3.1.0 | agendamento_confirmado | 2 | 6% |
| 3.1.0 | aprovacao_rejeitada | 2 | 6% |
| 3.1.0-gemini | aguardando_humano | 3 | 33% |
| 3.1.0-gemini | limite_de_tempo | 3 | 33% |
| 3.1.0-gemini | resposta_final | 2 | 22% |
| 3.1.0-gemini | agendamento_confirmado | 1 | 11% |
| 3.2.0 | resposta_final | 22 | 42% |
| 3.2.0 | aguardando_cliente | 16 | 30% |
| 3.2.0 | agendamento_confirmado | 7 | 13% |
| 3.2.0 | aguardando_humano | 5 | 9% |
| 3.2.0 | aprovacao_rejeitada | 2 | 4% |
| 3.2.0 | fora_do_escopo | 1 | 2% |
| 3.2.0-sem-controles | resposta_final | 23 | 43% |
| 3.2.0-sem-controles | aguardando_cliente | 12 | 23% |
| 3.2.0-sem-controles | agendamento_confirmado | 10 | 19% |
| 3.2.0-sem-controles | aguardando_humano | 5 | 9% |
| 3.2.0-sem-controles | aprovacao_rejeitada | 2 | 4% |
| 3.2.0-sem-controles | fora_do_escopo | 1 | 2% |

## Taxa de erro por ferramenta

| versão | ferramenta | chamadas | erros | taxa |
|---|---|---|---|---|
| 2.0.0 | buscar_opcoes | 13 | 0 | 0.0% |
| 2.0.0 | buscar_regra | 11 | 0 | 0.0% |
| 2.0.0 | confirmar_agendamento | 2 | 0 | 0.0% |
| 2.0.0 | consultar_historico | 27 | 1 | 3.7% |
| 3.0.0 | buscar_opcoes | 13 | 0 | 0.0% |
| 3.0.0 | buscar_regra | 11 | 0 | 0.0% |
| 3.0.0 | confirmar_agendamento | 2 | 0 | 0.0% |
| 3.0.0 | consultar_historico | 27 | 1 | 3.7% |
| 3.1.0 | buscar_opcoes | 13 | 0 | 0.0% |
| 3.1.0 | buscar_regra | 11 | 0 | 0.0% |
| 3.1.0 | confirmar_agendamento | 2 | 0 | 0.0% |
| 3.1.0 | consultar_historico | 27 | 1 | 3.7% |
| 3.1.0-gemini | buscar_opcoes | 4 | 0 | 0.0% |
| 3.1.0-gemini | buscar_regra | 3 | 0 | 0.0% |
| 3.1.0-gemini | confirmar_agendamento | 2 | 0 | 0.0% |
| 3.1.0-gemini | consultar_historico | 7 | 0 | 0.0% |
| 3.2.0 | buscar_opcoes | 13 | 0 | 0.0% |
| 3.2.0 | buscar_regra | 11 | 0 | 0.0% |
| 3.2.0 | confirmar_agendamento | 2 | 0 | 0.0% |
| 3.2.0 | consultar_historico | 27 | 1 | 3.7% |
| 3.2.0 | criar_agendamentos | 5 | 0 | 0.0% |
| 3.2.0 | listar_horarios | 18 | 0 | 0.0% |
| 3.2.0 | listar_servicos | 10 | 0 | 0.0% |
| 3.2.0 | localizar_salao_mais_proximo | 10 | 0 | 0.0% |
| 3.2.0-sem-controles | buscar_opcoes | 13 | 0 | 0.0% |
| 3.2.0-sem-controles | buscar_regra | 11 | 0 | 0.0% |
| 3.2.0-sem-controles | confirmar_agendamento | 2 | 0 | 0.0% |
| 3.2.0-sem-controles | consultar_historico | 27 | 1 | 3.7% |
| 3.2.0-sem-controles | criar_agendamentos | 8 | 0 | 0.0% |
| 3.2.0-sem-controles | listar_horarios | 18 | 0 | 0.0% |
| 3.2.0-sem-controles | listar_servicos | 10 | 0 | 0.0% |
| 3.2.0-sem-controles | localizar_salao_mais_proximo | 10 | 0 | 0.0% |

## SLI de qualidade

SLI = execuções com término em {resposta_final, agendamento_confirmado, aprovacao_rejeitada, fora_do_escopo} **e** nenhuma ferramenta com erro ÷ execuções que terminaram (exclui `aguardando_humano` e `aguardando_cliente`). Cada turno do modo conversa é uma execução.

| versão | bons | válidas | SLI | alvo | orçamento de erro consumido |
|---|---|---|---|---|---|
| 2.0.0 | 25 | 26 | 96.2% (cumprido) | ≥90% | 38% |
| 3.0.0 | 25 | 26 | 96.2% (cumprido) | ≥90% | 38% |
| 3.1.0 | 25 | 26 | 96.2% (cumprido) | ≥90% | 38% |
| 3.1.0-gemini | 3 | 6 | 50.0% (VIOLADO) | ≥90% | 500% |
| 3.2.0 | 31 | 32 | 96.9% (cumprido) | ≥90% | 31% |
| 3.2.0-sem-controles | 35 | 36 | 97.2% (cumprido) | ≥90% | 28% |
