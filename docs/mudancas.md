# Histórico de mudanças

Versão do sistema: constante `VERSAO_SISTEMA` em [src/versao.py](../src/versao.py), gravada como `sistema.versao` na raiz de todo trace.

> **Commits:** controles em `19862a6`; traces, versão e ligação ao grafo em `49b2ec3`; suíte em `65a7694`. Os controles 2 e 3 têm duas partes: a função (`19862a6`) e a chamada no grafo (`49b2ec3`). **Aprovador de cada mudança:** a preencher pelo grupo.

## 3.1.0 — Fechamento das pendências da Parte 2 e da Parte 3 (2026-11-08)

> **Commit:** ainda não commitado quando este texto foi escrito. Depois do commit, preencher a coluna Commit e regenerar `logs/` (`python -m src.demo`), que carregam o hash do código.

| Mudança | Por quê | Arquivos | Commit |
|---|---|---|---|
| `memoria.registrar` passa a derivar chave de idempotência do conteúdo e a devolver `{gravado, ja_existia, bloqueado}` | Parte 2 §5.3: escrita de memória é escrita e precisa ser idempotente | `src/memoria.py`, `src/grafo.py`, `tests/test_controles.py` | a preencher |
| Memória procedural em texto no system prompt | Parte 2 §5.2: as três memórias | `src/prompts/memoria-procedural.txt`, `src/modelo.py` | a preencher |
| Interruptor de suspensão `AGENTE_SUSPENSO=1` e término `suspenso` | Governança: quem pode suspender o agente | `src/grafo.py`, `tests/test_controles.py`, `.env.example` | a preencher |
| `esquecer` apaga os traces do cliente em `logs/traces.jsonl` | Cobertura da remoção (Parte 2 §5.4) e dado pessoal no trace (Parte 3 §3.4) | `src/esquecer.py`, `tests/test_controles.py` | a preencher |
| `saida_modelo_rejeitada` e `memoria_bloqueada` viram atributos do span raiz | Falhas silenciosas sem sinal no trace (observabilidade §1.3) | `src/grafo.py` | a preencher |
| `evals.rodar` aceita `--modo gemini` e `--casos` | Medir o sistema com o modelo real | `evals/rodar.py` | a preencher |
| Caminho da fonte do corpus em POSIX (`as_posix`) | Em Windows a fonte vinha com `\\` e `avaliar_rag` marcava 2/10 em vez de 10/10 | `src/recuperacao.py` | a preencher |
| Avaliação de registro e experimento do documento revogado | Parte 2 §4: perguntas de registro e curadoria | `src/avaliar_registro.py`, `src/demo_revogado.py`, `dados/perguntas-registro.json` | a preencher |
| `logs/traces.jsonl` no `.gitignore` | O trace guarda a entrada completa e o `cliente_id` | `.gitignore` | a preencher |

**Achado não corrigido (decisão do grupo).** Na rodada com Gemini real, `finalizar` sobrescreve o motivo de término por `limite_de_tempo` quando a chamada ao modelo passa dos 30 s, **mesmo que a reserva já tenha sido feita** (`ag-05`). O motivo de término deixa de dizer a verdade sobre a escrita. Correções possíveis: não sobrescrever `agendamento_confirmado`, ou reduzir o timeout do Gemini abaixo do teto. Medido em `evals/resultados/3.1.0-gemini-20261108-135625`.

## 3.0.0 — Parte 3 (2026-11-06)

| Mudança | Por quê | Arquivos | Commit |
|---|---|---|---|
| Versão do sistema (`2.0.0` → `3.0.0`) | A Parte 2 só versionava o prompt; sem versão nenhum número se compara entre versões. | `src/versao.py` | 49b2ec3 |
| Traces OpenTelemetry (convenções GenAI) em arquivo JSONL | Observabilidade (§4) e registro da decisão (§2.3). | `src/telemetria.py`, `src/grafo.py` | 49b2ec3 |
| Controle 1: filtro de gravação da memória | Memória aceitava qualquer texto (e-mail, senha, instrução injetada). | `src/memoria.py` | 19862a6 |
| Controle 2: verificação da escrita (aprovação + opção consultada + 1 escrita por execução) | Defesa em código, com teste, do risco de maior impacto. | `src/controles.py`, `src/grafo.py` | 19862a6, 49b2ec3 |
| Controle 3: validação da saída do Gemini | O modelo podia introduzir id, preço, horário ou afirmar escrita inexistente. | `src/controles.py`, `src/grafo.py` | 19862a6, 49b2ec3 |
| Motivo de término `escrita_bloqueada` | Sem ele, uma escrita bloqueada sairia como `aprovacao_rejeitada`. | `src/grafo.py` | 49b2ec3 |
| Suíte de avaliação, juiz, métricas | §1 e §4.3. | `evals/` | 65a7694 |
| Testes dos controles | §3.2. | `tests/test_controles.py` | 19862a6 |
| `.gitignore` cobre `dados/*.sqlite-shm` e `-wal` | O SQLite em modo WAL gera esses arquivos locais. | `.gitignore` | 3c2e040 |
| Removido `sqlite-vec` do `requirements.txt`; adicionados OpenTelemetry e pytest | `sqlite-vec` não é importado em nenhum arquivo do projeto. | `requirements.txt` | 3c2e040 |

## Defeito encontrado e corrigido nesta entrega

**O que estava errado.** Em `finalizar`, o texto redigido pelo Gemini era atribuído a `estado["resultado"]`, mas o nó não devolvia essa chave no dicionário de retorno. O LangGraph só persiste o que o nó devolve, então a resposta do modelo nunca chegava à saída final: em `MODO=gemini` o usuário recebia sempre a resposta-base, embora o custo da chamada fosse pago.

**O que mudou.** O nó passa a devolver `resultado` quando o modelo é aceito pelo controle 3 (`validar_saida_modelo`); quando é rejeitado, a resposta-base permanece e o evento `saida_modelo_rejeitada` é registrado. O defeito foi achado ao implementar o controle 3, que seria inócuo sem isso.

**Consequência a conhecer.** A avaliação do prompt da Parte 2 (`src/avaliar_prompt.py`) chama o modelo diretamente e não passa por `finalizar`, então seus resultados não são afetados. O comportamento ponta a ponta do modo Gemini, porém, nunca foi medido com a resposta do modelo chegando ao usuário: **LACUNA** (ver `docs/evals.md`).

**Commit:** 49b2ec3.

## Correções apontadas pela correção da Parte 2

Não foi fornecido ao grupo o relatório de correção da Parte 2 no material desta entrega; nenhuma correção externa foi registrada. **Se houver, acrescentar aqui** (o que estava errado, o que mudou, commit).
