# Observabilidade

Código: [src/telemetria.py](../src/telemetria.py) (exportador) e [src/grafo.py](../src/grafo.py) (spans). Métricas: [evals/metricas.py](../evals/metricas.py), saída em [evals/resultados/metricas.md](../evals/resultados/metricas.md).

## 1. O plano

### 1.1 As perguntas

| Interessado | Pergunta | Decisão que a resposta muda |
|---|---|---|
| Negócio | Que fração dos pedidos termina em resposta útil (resposta, reserva ou rejeição consciente) e não em erro ou limite? | Se cair abaixo do SLO, congelar novas funções e corrigir. |
| Operação | A API de disponibilidade e o catálogo estão respondendo? Qual ferramenta falha mais? | Acionar quem cuida da API; ativar mensagem de degradação. |
| Quem paga | Quanto custa uma execução com Gemini, e quanto uma rodada de avaliação? | Manter ou desligar `MODO=gemini`; ajustar o teto de US$ 0,01. |
| Quem responde pelo sistema | O que o agente decidiu numa execução específica, com base em quê e sob qual versão? | Aceitar ou reverter uma versão; responder a uma contestação. |

### 1.2 O trace de uma execução

```
invoke_agent agendeakiai            (raiz)
├── execute_tool consultar_historico
├── execute_tool buscar_opcoes      (ou buscar_regra)
├── chat gemini-3.8-flash           (só em MODO=gemini)
└── execute_tool confirmar_agendamento   (só após a aprovação, na execução de retomada)
```

Uma execução que para na aprovação humana termina como `aguardando_humano`; a retomada abre **outra** raiz `invoke_agent` (atributo `retomada = true`) com a mesma `conversa_id`.

Atributos próprios da raiz (`src/grafo.py`, função `executar`): `sistema.versao`, `motivo_termino`, `conversa_id`, `cliente_id`, `entrada`, `retomada`, `prompt.id`, `prompt.sha256`, `contexto_recuperado` (fontes), `saida`, `aprovacao_humana`, `saida_modelo_rejeitada` e `memoria_bloqueada` (booleanos, desde a versão 3.1.0). Spans de ferramenta: `gen_ai.tool.name`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`, `ferramenta.ok`. Span de modelo: `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `custo_usd`.

Motivos de término observados: `resposta_final`, `agendamento_confirmado`, `aprovacao_rejeitada`, `aguardando_humano`, `escrita_bloqueada`, `limite_de_passos`, `limite_de_tempo`, `aprovacao_expirada`, `suspenso`, `erro`.

### 1.3 Os modos de falha

| Modo de falha | Silenciosa? | Sinal que o torna visível |
|---|---|---|
| API de disponibilidade fora do ar | não | `ferramenta.ok = false` e status ERROR nos spans `execute_tool`; taxa de erro por ferramenta |
| Limite de passos ou de tempo atingido | não | `motivo_termino` = `limite_de_passos` / `limite_de_tempo` |
| **Ferramenta falha e o agente responde "não consegui consultar" com término `resposta_final`** | **sim** | Taxa de erro por ferramenta e SLI de qualidade (§4): o término parece bom, mas há ferramenta com erro no mesmo trace |
| **Gemini rejeitado pelo controle 3 ou indisponível: o usuário recebe a resposta-base, sem erro** | **sim** | Atributo `saida_modelo_rejeitada` na raiz (desde 3.1.0); span `chat` com status ERROR quando o Gemini falha |
| Memória bloqueia gravação (R2) e o usuário perde personalização | sim | Atributo `memoria_bloqueada` na raiz (desde 3.1.0) |
| Aprovação humana expira | não | `motivo_termino = aprovacao_expirada` |
| **Gemini lento ou fora do ar: o texto base é mantido, ou o término vira `limite_de_tempo` mesmo com a reserva feita** | **sim** | Span `chat` com status ERROR e duração; `motivo_termino = limite_de_tempo` junto de `confirmar_agendamento` ok no mesmo trace. Medido em 2026-11-08 (ver §3) |

As silenciosas que o SLO de qualidade cobre diretamente: a 3ª linha (ferramenta com erro, término "normal") e, desde a rodada com Gemini, a que termina em `limite_de_tempo` (não está em `TERMINOS_BONS`). A 4ª e a 5ª agora têm atributo na raiz, mas o SLI ainda não as usa.

## 2. A instrumentação

- `invoke_agent <agente>` na raiz, `execute_tool <ferramenta>` por chamada e `chat <modelo>` por chamada ao modelo, com atributos das convenções GenAI (`gen_ai.operation.name`, `gen_ai.tool.name`, `gen_ai.request.model`, `gen_ai.usage.*`).
- **Versão do sistema** (`sistema.versao`) e **motivo de término** (`motivo_termino`) na raiz, como o §4.2 exige.
- Exportação: um span por linha em JSONL, em `logs/traces.jsonl` (padrão) ou no caminho de `TRACES_ARQUIVO`. A suíte grava em `evals/resultados/<rodada>/traces.jsonl`.
- Não usa collector nem plataforma externa. **Divergência da convenção:** o span `chat` só existe quando o Gemini é chamado; na suíte (mock) ele não aparece.

## 3. Métricas sobre execuções reais

Fonte: 102 execuções em `evals/resultados/*/traces.jsonl`: três rodadas em `MODO=mock` (2.0.0, 3.0.0 e 3.1.0, 31 execuções cada) e uma rodada **com Gemini real** (`3.1.0-gemini`, 9 execuções de 7 casos, 2026-11-08). Valores exatos em [evals/resultados/metricas.md](../evals/resultados/metricas.md). **Limites:** são execuções de teste, não tráfego real; na rodada mock a latência é a de um mock local (milissegundos) e o custo é zero; o `p95` de 31 execuções é dominado por 2 pontos e varia de uma rodada para outra.

| versão | execuções | p50 (ms) | p95 (ms) | custo médio (US$) |
|---|---|---|---|---|
| 2.0.0 (sem controles) | 31 | 13,8 | 20,0 | 0 |
| 3.0.0 | 31 | 13,2 | 85,8 | 0 |
| 3.1.0 | 31 | 13,5 | 54,7 | 0 |
| **3.1.0-gemini** | 9 | **11.886,5** | **118.606,1** | 0,0002 |

Motivos de término em mock (iguais nas três versões): `resposta_final` 71%, `aguardando_humano` 16%, `agendamento_confirmado` 6%, `aprovacao_rejeitada` 6%. Com Gemini: `aguardando_humano` 3, `limite_de_tempo` 3, `resposta_final` 2, `agendamento_confirmado` 1. Taxa de erro por ferramenta: `consultar_historico` 3,7% (1 de 27: cliente inexistente, esperado) nas três versões mock; 0% nas demais e na rodada Gemini.

**O que a rodada com Gemini mostrou.** Das 6 chamadas ao modelo, **1 teve sucesso** (633 tokens de entrada, 93 de saída, **US$ 0,0022485**, 83,6 s) e 5 terminaram em erro (duas perto de 118 s, no teto de 120 s do SDK; as outras em 3,5 s, 11,8 s e 19 s; o tipo do erro não é gravado no span). Como o teto de tempo do sistema é 30 s e é verificado no fim de `finalizar`, três execuções terminaram como `limite_de_tempo`, **inclusive uma em que a reserva foi confirmada** (`ag-05`: o término sobrescreve `agendamento_confirmado`). O custo médio de US$ 0,0002 é média sobre 9 execuções, a maioria sem chamada bem-sucedida; **o custo de uma chamada bem-sucedida é a referência: ≈ US$ 0,002**. A amostra é pequena e coincidiu com instabilidade do provedor (HTTP 503/504 observados na mesma hora em `src.avaliar_prompt`).

## 4. O objetivo: SLI e SLO

- **SLI.** Razão entre execuções **boas** e **válidas**, calculada pelo atributo `motivo_termino` da raiz e pelo atributo `ferramenta.ok` dos spans `execute_tool` do mesmo `trace_id`.
  - *Válida:* execução cujo `motivo_termino` ≠ `aguardando_humano` (parar para o humano não é término).
  - *Boa:* válida, com `motivo_termino` ∈ {`resposta_final`, `agendamento_confirmado`, `aprovacao_rejeitada`} **e** nenhum span `execute_tool` com `ferramenta.ok = false`.
- **SLO.** SLI ≥ **90%**, janela de 7 dias. Orçamento de erro: 10% das execuções válidas.
- **Valor medido** (janela de teste de um dia, não de 7): em `MODO=mock`, **25 boas de 26 válidas = 96,2%** em cada uma das três versões (2.0.0, 3.0.0, 3.1.0); orçamento de erro consumido **38%**; SLO **cumprido**. Na rodada **com Gemini real, 3 boas de 6 válidas = 50,0%; orçamento consumido 500%; SLO VIOLADO**. É o resultado que importa para produção, e não foi ajustado: o alvo continua em 90%. O que o mede é o SLI, que não conta `limite_de_tempo` como bom. O que fariam: reduzir o timeout do Gemini abaixo do teto de 30 s com texto-base como alternativa, e repetir a rodada com mais casos quando a cota permitir.
- Em mock, a única execução "ruim" é `ag-03` (cliente inexistente): término `resposta_final`, mas com `consultar_historico` retornando 404. É a degradação silenciosa que o SLI foi desenhado para pegar. Com Gemini, as ruins são as três `limite_de_tempo`.
- **Ressalva.** O resultado vem de uma suíte desenhada pelo próprio grupo, em mock. Ele não é uma medida de produção; vale como o procedimento de cálculo, que passa a valer sobre tráfego real.

## 5. As quatro perguntas, respondidas com os números

| Pergunta | Resposta com os números | Lacuna |
|---|---|---|
| Negócio: fração útil? | Mock: 96,2% (25/26), SLO de 90% cumprido. **Gemini real: 50% (3/6), SLO violado** | sem usuários reais; 6 execuções válidas com Gemini |
| Operação: qual ferramenta falha? | `consultar_historico`, 3,7% (1/27); demais 0%. **O modelo** falhou em 5 de 6 chamadas na rodada Gemini | a API real não foi medida |
| Quem paga: custo por execução? | US$ 0 em mock. Com Gemini: **≈ US$ 0,002 por chamada bem-sucedida** (1 chamada medida: 633 + 93 tokens); média de US$ 0,0002 por execução na rodada, diluída por chamadas que falharam | uma única chamada bem-sucedida: estimativa frágil. Repetir com mais casos |
| Quem responde: o que decidiu, sob qual versão? | Reconstruído de um trace em [model-card.md](model-card.md) §11 | `aprovador` é o `cliente_id`; sem login do aprovador |

## 6. Como ver os traces

```bash
python -m evals.rodar --versao 3.1.0          # gera evals/resultados/3.1.0-<ts>/traces.jsonl
python -m evals.metricas                      # resumo por versão
# ler um trace pelo trace_id da raiz:
python -c "import json; [print(json.dumps(l, ensure_ascii=False)) for l in map(json.loads, open('evals/resultados/<rodada>/traces.jsonl', encoding='utf-8')) if l['trace_id']=='<ID>']"
```

Cada linha do JSONL é um span (`nome`, `trace_id`, `parent_id`, `duracao_ms`, `status`, `atributos`). Para ler um trace: filtrar as linhas pelo `trace_id` da raiz.
