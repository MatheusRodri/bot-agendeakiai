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

Atributos próprios da raiz (`src/grafo.py`, função `executar`): `sistema.versao`, `motivo_termino`, `conversa_id`, `cliente_id`, `entrada`, `retomada`, `prompt.id`, `prompt.sha256`, `contexto_recuperado` (fontes), `saida`, `aprovacao_humana`. Spans de ferramenta: `gen_ai.tool.name`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`, `ferramenta.ok`. Span de modelo: `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `custo_usd`.

Motivos de término observados: `resposta_final`, `agendamento_confirmado`, `aprovacao_rejeitada`, `aguardando_humano`, `escrita_bloqueada`, `limite_de_passos`, `limite_de_tempo`, `aprovacao_expirada`, `erro`.

### 1.3 Os modos de falha

| Modo de falha | Silenciosa? | Sinal que o torna visível |
|---|---|---|
| API de disponibilidade fora do ar | não | `ferramenta.ok = false` e status ERROR nos spans `execute_tool`; taxa de erro por ferramenta |
| Limite de passos ou de tempo atingido | não | `motivo_termino` = `limite_de_passos` / `limite_de_tempo` |
| **Ferramenta falha e o agente responde "não consegui consultar" com término `resposta_final`** | **sim** | Taxa de erro por ferramenta e SLI de qualidade (§4): o término parece bom, mas há ferramenta com erro no mesmo trace |
| **Gemini rejeitado pelo controle 3 ou indisponível: o usuário recebe a resposta-base, sem erro** | **sim** | Eventos `saida_modelo_rejeitada` / erro em `modelo` no estado; span `chat` com status ERROR. **LACUNA:** o evento `saida_modelo_rejeitada` está no estado, mas ainda não é atributo do span raiz |
| Memória bloqueia gravação (R2) e o usuário perde personalização | sim | Evento `memoria_bloqueada` no estado. **LACUNA:** idem, não é atributo de span |
| Aprovação humana expira | não | `motivo_termino = aprovacao_expirada` |

As duas silenciosas que o SLO de qualidade cobre diretamente: a 3ª linha (ferramenta com erro, término "normal"). A 4ª e 5ª ficam como lacuna de instrumentação.

## 2. A instrumentação

- `invoke_agent <agente>` na raiz, `execute_tool <ferramenta>` por chamada e `chat <modelo>` por chamada ao modelo, com atributos das convenções GenAI (`gen_ai.operation.name`, `gen_ai.tool.name`, `gen_ai.request.model`, `gen_ai.usage.*`).
- **Versão do sistema** (`sistema.versao`) e **motivo de término** (`motivo_termino`) na raiz, como o §4.2 exige.
- Exportação: um span por linha em JSONL, em `logs/traces.jsonl` (padrão) ou no caminho de `TRACES_ARQUIVO`. A suíte grava em `evals/resultados/<rodada>/traces.jsonl`.
- Não usa collector nem plataforma externa. **Divergência da convenção:** o span `chat` só existe quando o Gemini é chamado; na suíte (mock) ele não aparece.

## 3. Métricas sobre execuções reais

Fonte: duas rodadas da suíte (62 execuções: 31 por versão), `evals/resultados/*/traces.jsonl`. **Limites:** são execuções de teste em `MODO=mock`, não tráfego real; a latência é a de um mock local (milissegundos), então só mostra o custo do próprio agente; **o custo é zero** porque nenhuma chamada ao modelo foi feita.

Números (ver o arquivo gerado para os valores exatos; o `p95` varia de uma rodada para outra, porque com 31 execuções ele é dominado por 2 pontos):

| versão | execuções | p50 (ms) | p95 (ms) | custo médio |
|---|---|---|---|---|
| 2.0.0 (sem controles) | 31 | 13,8 | 20,0 | US$ 0 |
| 3.0.0 | 31 | 13,2 | 85,8 | US$ 0 |

Motivos de término (iguais nas duas versões): `resposta_final` 71%, `aguardando_humano` 16%, `agendamento_confirmado` 6%, `aprovacao_rejeitada` 6%. Taxa de erro por ferramenta: `consultar_historico` 3,7% (1 de 27: o caso de cliente inexistente, esperado); as demais 0%.

## 4. O objetivo: SLI e SLO

- **SLI.** Razão entre execuções **boas** e **válidas**, calculada pelo atributo `motivo_termino` da raiz e pelo atributo `ferramenta.ok` dos spans `execute_tool` do mesmo `trace_id`.
  - *Válida:* execução cujo `motivo_termino` ≠ `aguardando_humano` (parar para o humano não é término).
  - *Boa:* válida, com `motivo_termino` ∈ {`resposta_final`, `agendamento_confirmado`, `aprovacao_rejeitada`} **e** nenhum span `execute_tool` com `ferramenta.ok = false`.
- **SLO.** SLI ≥ **90%**, janela de 7 dias. Orçamento de erro: 10% das execuções válidas.
- **Valor medido** (62 execuções das duas rodadas, janela de teste de um dia, não de 7): **25 boas de 26 válidas = 96,2%** em cada versão. Orçamento de erro consumido: **38%**. SLO **cumprido** nas execuções medidas.
- A única execução "ruim" é `ag-03` (cliente inexistente): término `resposta_final`, mas com `consultar_historico` retornando 404. É a degradação silenciosa que o SLI foi desenhado para pegar.
- **Ressalva.** O resultado vem de uma suíte desenhada pelo próprio grupo, em mock. Ele não é uma medida de produção; vale como o procedimento de cálculo, que passa a valer sobre tráfego real.

## 5. As quatro perguntas, respondidas com os números

| Pergunta | Resposta com os números | Lacuna |
|---|---|---|
| Negócio: fração útil? | 96,2% das execuções válidas (25/26) na suíte; SLO de 90% cumprido | só mock, sem usuários reais |
| Operação: qual ferramenta falha? | `consultar_historico`, 3,7% (1/27); demais 0% | a API real não foi medida |
| Quem paga: custo por execução? | **Sem resposta**: US$ 0 em mock | **LACUNA:** não há execuções com Gemini nos traces; rodar parte da suíte com `MODO=gemini` e a cota disponível |
| Quem responde: o que decidiu, sob qual versão? | Reconstruído de um trace em [model-card.md](model-card.md) §11 | `aprovador` é o `cliente_id`; sem login do aprovador |

## 6. Como ver os traces

```bash
python -m evals.rodar --versao 3.0.0          # gera evals/resultados/3.0.0-<ts>/traces.jsonl
python -m evals.metricas                      # resumo por versão
```

Cada linha do JSONL é um span (`nome`, `trace_id`, `parent_id`, `duracao_ms`, `status`, `atributos`). Para ler um trace: filtrar as linhas pelo `trace_id` da raiz.
