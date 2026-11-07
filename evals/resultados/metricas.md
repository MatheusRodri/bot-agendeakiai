# Métricas por versão do sistema

Fonte: 62 traces em `evals/resultados/*/traces.jsonl`. Cada `invoke_agent` é uma execução; uma retomada após aprovação humana é uma segunda execução.

| versão | execuções | latência p50 (ms) | latência p95 (ms) | custo médio (US$) |
|---|---|---|---|---|
| 2.0.0 | 31 | 13.8 | 20.0 | 0.0000 |
| 3.0.0 | 31 | 13.2 | 85.8 | 0.0000 |

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

## SLI de qualidade

SLI = execuções com término em {resposta_final, agendamento_confirmado, aprovacao_rejeitada} **e** nenhuma ferramenta com erro ÷ execuções que terminaram (exclui `aguardando_humano`).

| versão | bons | válidas | SLI | alvo | orçamento de erro consumido |
|---|---|---|---|---|---|
| 2.0.0 | 25 | 26 | 96.2% (cumprido) | ≥90% | 38% |
| 3.0.0 | 25 | 26 | 96.2% (cumprido) | ≥90% | 38% |
