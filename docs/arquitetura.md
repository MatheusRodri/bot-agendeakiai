# Arquitetura do agente

## Desenho

```text
 texto livre + cliente_id + conversa_id
        |
        |  AGENTE_SUSPENSO=1 ? --> encerra aqui: motivo "suspenso", nada é consultado nem escrito
        v
 validar_entrada [CÓDIGO]            valida o contrato Pydantic; carrega o prompt e grava seu sha256
        |
        v
 consultar_contexto [CÓDIGO] <------ tool consultar_historico (leitura, API mock)
        |                            memória JSON: recuperar (leitura, Jaccard >= 0,15)
        v
 decidir_proxima_acao [CÓDIGO] <----------------------------------+
        |        aresta condicional, regra em código (campo)      |
        |                                                         |
        +-- sem "resultado" ----------> consultar_fontes [CÓDIGO] +
        |                                tools (leitura): buscar_regra (corpus .md)
        |                                                 buscar_opcoes (catálogo, API mock)
        |
        +-- exige_aprovacao -----------> preparar_aprovacao [CÓDIGO]
        |                                        |
        |                                        v
        |                          aprovar_agendamento [CÓDIGO + INTERRUPT: cliente, 15 min]
        |                           aresta condicional: decisao.aprovada (regra em código)
        |                              |                          |
        |                  rejeitar / expirou            aprovar / editar (só opção consultada)
        |                              |                          v
        |                              |        registrar_agendamento [CÓDIGO, ESCRITA IRREVERSÍVEL]
        |                              |          verificar_escrita (fail-closed) -> tool
        |                              |          confirmar_agendamento (chave de idempotência)
        |                              |                          |
        +-- senão / MAX_PASSOS --------+--------------------------+
                                       |
                                       v
                          finalizar [CÓDIGO; MODELO só em MODO=gemini]
                            - Gemini redige o texto; validar_saida_modelo rejeita o que inventar
                            - grava memória (filtro de gravação, idempotente)
                            - define o motivo de término
                                       |
                                       v
                                      END

 Términos: resposta_final | agendamento_confirmado | aprovacao_rejeitada | aprovacao_expirada |
           escrita_bloqueada | limite_de_passos | limite_de_tempo | suspenso
           (na raiz do trace também: aguardando_humano, quando o grafo pausa, e erro)

 O modelo não decide nenhuma aresta: todas as bifurcações são regra em código.
 Checkpointer SqliteSaver: dados/checkpoints.sqlite, endereçado por conversa_id (thread_id)
```

## Modo conversa (versão 3.2.0)

`python -m src.main --chat` abre um chat no terminal. Ele **não usa o grafo**: a conversa tem vários turnos e guarda estado entre eles (`src/conversa.py`, classe `Conversa`). O grafo continua sendo o modo de um comando por vez, com a pausa humana do LangGraph. A decisão de não estender o grafo foi de simplicidade: o fluxo é uma sequência de perguntas com estado em memória, e o backend real já não usava checkpoint.

```text
 mensagem do cliente (um turno)
        |
        |  AGENTE_SUSPENSO=1 ? --> "suspenso", nada é consultado
        v
 pedido_explicito_de_agendamento(texto) [CÓDIGO]   "pode agendar" -> True | "não agende" -> False
        |
        +-- já agendou? ------------------> informa os códigos; não escreve de novo
        +-- pergunta de regra ------------> buscar_regra (corpus), como no grafo
        |
        +-- 1º pedido (ocasião/serviço) --> localizar_salao_mais_proximo  [API, leitura]
        |                                   listar_servicos               [API, leitura]
        |                                   recomendação:
        |                                     MODO=gemini -> recomendar_servicos [MODELO]
        |                                       validar_recomendacao + validar_saida_modelo (fail-closed)
        |                                     senão / rejeitado / erro -> recomendar_por_regras [CÓDIGO]
        +-- turnos seguintes -------------> "sem a barba", "só o corte", "adiciona unha" [CÓDIGO]
        v
 extrair_data / extrair_hora [CÓDIGO]   (hoje, amanhã, sexta, 20/11, 10h, 14:30...)
        |   1º pedido com ocasião + hora ("reunião às 15h") -> prazo: terminar 1 h antes
        |   "corte às 15h" / "pode agendar às 15h" -> hora do atendimento
        |
        +-- sem dia -------> pergunta o dia
        +-- sem horário ---> listar_horarios de cada serviço [API, leitura] -> oferece inícios
        |                    em que todos os serviços cabem em sequência
        +-- horário ocupado -> sugere os mais próximos
        +-- plano pronto, sem pedido explícito -> resumo + "diga 'pode agendar'"
        +-- plano pronto, com pedido explícito:
                 verificar_escrita_conversa (controle 5, fail-closed)
                 -> criar_agendamentos [API, ESCRITA, lote numa transação, valorEsperado]

 Términos por turno: aguardando_cliente | resposta_final | agendamento_confirmado |
                     escrita_bloqueada | fora_do_escopo | erro_ferramenta | suspenso
```

Ferramentas: `AgendeAkiApiTools` (backend real, `src/agendeaki_api.py`) ou `SalaoSimulado` (em memória, `src/salao_simulado.py`, usado por testes, evals e `--chat` sem `--backend agendeaki`). Cada turno gera um trace com raiz `invoke_agent agendeakiai-conversa` e spans `execute_tool` / `chat`, como no grafo. O modelo não decide data, horário, preço nem a escrita: só escolhe serviços do catálogo e redige uma frase de motivo.

## Conferência contra o código

Comando: `python conferir_grafo.py` (importa o mesmo objeto `GRAFO` que `src.grafo.executar` usa e imprime `GRAFO.get_graph()`). Saída observada em **2026-11-08**, versão do sistema `3.1.0`:

```text
Nós:
- __end__
- __start__
- aprovar_agendamento
- consultar_contexto
- consultar_fontes
- decidir_proxima_acao
- finalizar
- preparar_aprovacao
- registrar_agendamento
- validar_entrada
Arestas:
- __start__ -> validar_entrada
- aprovar_agendamento -> finalizar [condicional]
- aprovar_agendamento -> registrar_agendamento [condicional]
- consultar_contexto -> decidir_proxima_acao
- consultar_fontes -> decidir_proxima_acao
- decidir_proxima_acao -> consultar_fontes [condicional]
- decidir_proxima_acao -> finalizar [condicional]
- decidir_proxima_acao -> preparar_aprovacao [condicional]
- finalizar -> __end__
- preparar_aprovacao -> aprovar_agendamento
- registrar_agendamento -> finalizar
- validar_entrada -> consultar_contexto
```

Se esta lista e o desenho divergirem, **vale o código** e o desenho está errado. O ciclo `decidir_proxima_acao` → `consultar_fontes` → `decidir_proxima_acao` está nas arestas acima. O interruptor de suspensão fica em `executar`, antes do grafo, e por isso não aparece como nó.

## Decisões do sistema

**Ferramentas:** `consultar_historico` lê histórico simulado; `buscar_opcoes` lê o catálogo estruturado; `buscar_regra` pesquisa documentos Markdown. As três são leituras reversíveis. `confirmar_agendamento` faz escrita na API mock, que é tratada como irreversível pelo fluxo e protegida por aprovação humana e chave idempotente. Preferências/episódios são gravados no arquivo JSON local ao terminar uma execução.

**Laço:** após consultar contexto, `decidir_proxima_acao` escolhe a etapa de consulta; `consultar_fontes` retorna ao decisor, que termina ou abre o portão de aprovação com base no estado. É um ciclo curto de ferramentas no `StateGraph`, com decisão determinística no modo mock. O modo Gemini opcional só redige a resposta final a partir do resultado já validado.

**Estado explícito:** `EstadoAgente` declara os dados de cliente, conversa, texto, mensagens, eventos, histórico, memória, opções, fontes, suficiência, decisão e agendamento. O conteúdo da conversa é uma mensagem curta. A lista `eventos` usa `operator.add` para acumular a trilha de execução sem apagar eventos anteriores.

**Orçamento:** limite de oito passos explícito em `MAX_PASSOS`; limite de recursão LangGraph definido como `MAX_PASSOS + 4` (12) para cobrir nós de suporte; máximo de 4.000 tokens por chamada remota (800 de saída, incluindo raciocínio, e pré-estimativa da entrada); limite local de US$ 0,01, calculado com taxas configuradas em `.env`; timeout de 120 segundos para Gemini, três segundos por chamada HTTP local e teto de 30 segundos observado no nó terminal. A proteção de tempo total não interrompe um nó no meio.

**Término:** `resposta_final`, `agendamento_confirmado`, `aprovacao_rejeitada`, `aprovacao_expirada`, `escrita_bloqueada`, `limite_de_passos`, `limite_de_tempo` e `suspenso` (interruptor `AGENTE_SUSPENSO=1`); no trace da raiz há ainda `aguardando_humano` (pausa) e `erro`. Erros de consulta são respostas finais sem escrita, com o erro preservado no evento de ferramenta. Erro irrecuperável de validação Pydantic é levantado antes das consultas.

**Humano:** cliente final autenticado revisa a opção escolhida antes de qualquer reserva. A tela de aprovação inclui serviço, profissional, horário, preço e alternativas consultadas. A ausência de resposta por 15 minutos rejeita a escrita. Veja [humano.md](humano.md).

## Nível de autonomia

O modo local combina **workflow sequencial, router e ciclo curto de ferramenta**. O decisor reavalia o estado após a recuperação e escolhe entre aprovação ou término. Para encontrar serviço, preço e local, o filtro determinístico é a camada de menor custo que resolve. A chamada opcional de modelo não escolhe ferramenta nem controla escrita.

| Padrão | Onde aparece | Decisão | Quando não usar |
|---|---|---|---|
| Sequencial com portão | validação → contexto → recuperação → resposta; aprovação antes de escrita | A ordem é obrigatória e a escrita só passa pelo portão humano | Não paralelizar ferramentas que não trazem benefício mensurável nesta API mock pequena |
| Router | `decidir_proxima_acao` escolhe consultar, aprovar ou terminar; código verifica resultado e `exige_aprovacao` | Campo presente no estado; zero chamada de modelo para rotear | Não usar para classificar pedidos livres de domínio amplo com regras simples |
| Sectioning/voting | Não usado | Uma consulta atende ao catálogo pequeno; não há tarefa independente nem avaliador de votos | Reconsiderar se fontes independentes precisarem ser consultadas em paralelo e houver medição |
| Orquestrador-trabalhador | Não usado | Não há decomposição variável em subtarefas | Não adicionar workers para filtros fixos |
| Avaliador-otimizador | Não usado no grafo | A validação atual é schema + regras de segurança; uma segunda geração não é necessária | Usar se houver critério de qualidade mensurável que justifique latência/custo extra |
| Agente com ciclo de ferramenta | `decidir_proxima_acao` → `consultar_fontes` → `decidir_proxima_acao` | A recuperação retorna ao decisor antes de terminar; o ciclo mantém ferramentas dentro do grafo e permite acrescentar outra consulta mantendo o mesmo controle | Não deixar o ciclo livre sem limite ou delegar a decisão de escrita ao modelo |

## Quem decide as bifurcações

| Aresta | Condição | Degrau |
|---|---|---|
| `decidir_proxima_acao` → consulta ou término/aprovação | ausência de `resultado` e valor de `exige_aprovacao` | Regra em código |
| `aprovar_agendamento` → `registrar_agendamento` ou `finalizar` | `decisao.aprovada` booleano validado no nó de aprovação | Regra em código |
| Busca → resposta incompleta/ambígua/opções | serviço ausente, múltiplos bairros ou lista vazia | Regra em código |

Não há aresta condicional decidida por embedding ou por modelo. A API mock não autentica usuário real e não deve ser exposta como serviço.

## Estado e reducers

| Campo | Tipo | Quem escreve | Quem lê | Origem |
|---|---|---|---|---|
| `cliente_id` | `str` | entrada da CLI/integrador | ferramentas, memória, escrita e remoção | identificador de usuário |
| `conversa_id` | `str` | entrada da CLI/integrador | configuração do checkpointer | identificador de sessão |
| `thread_id` | `str` | inicialização do grafo | checkpointer | igual a `conversa_id` |
| `texto` | `str` | entrada e `validar_entrada` | contexto, recuperação, memória e modelo opcional | mensagem do cliente |
| `aprovar` | `bool` | entrada | validação | opção da CLI; a decisão efetiva chega pelo `resume` |
| `passos` | `int` | validação e nós de ferramenta | router e término | execução |
| `iniciado_em` | `float` | validação | término | relógio local |
| `mensagens` | lista de mensagens | validação | redação opcional | fala original do cliente |
| `eventos` | lista; reducer `operator.add` | cada nó | demonstração, logs e verificador | execução |
| `historico` | `dict` | `consultar_contexto` | recuperação e resposta | API mock |
| `memoria` | `dict` | `consultar_contexto` | ordenação e personalização | JSON local |
| `acao_planejada` | `str` | `decidir_proxima_acao` | aresta condicional | estado atual |
| `opcoes` | lista de dicionários | `consultar_fontes` | aprovação e escrita | API mock |
| `fontes` | lista de strings | `consultar_fontes` | saída validada e redação opcional | API/corpus |
| `suficiente` | `bool` | `consultar_fontes`/escrita | saída validada e redação opcional | regra de suficiência local |
| `resultado` | `str` | recuperação, aprovação, escrita e modelo opcional | cliente e log | ferramenta/código/modelo opcional |
| `exige_aprovacao` | `bool` | `consultar_fontes` | decisor | texto do cliente |
| `aprovacao_pendente` | `dict` | `preparar_aprovacao` | nó de interrupt e remoção | opção e prazo |
| `decisao` | `dict` | `aprovar_agendamento` | router e escrita | resposta humana |
| `agendamento` | `dict` | `registrar_agendamento` | saída e log | API mock |
| `motivo_terminacao` | `str` | `finalizar` | CLI e log | código |
| `pendente` | `bool` | nó de aprovação | retomada e logs | execução |
| `prompt_id` | `str` | `validar_entrada` | logs | arquivo de prompt versionado |
| `prompt_hash` | `str` SHA-256 | `validar_entrada` | logs | bytes do prompt |

`eventos` precisa do reducer porque vários nós acrescentam registros em sequência. Os demais campos são atualizados por um único nó em cada etapa e usam o reducer padrão de valor único. `mensagens` guarda somente a fala de entrada; contadores, identificadores e decisões vivem em campos explícitos. Filtros e resumo lexical são derivados e não duplicados no estado. Não há agentes secundários, portanto não existe contrato de passagem entre agentes.

## Limites do framework e parâmetros

O LangGraph grava checkpoint, encaminha arestas e aplica `recursion_limit`. O código ainda define a causa de término, os limites de tempo/passos de negócio, a validade da decisão e a classificação de falhas. `recursion_limit=12` está declarado para que uma mudança do padrão da biblioteca não altere o teto do grafo. Sem reducer, atualizações paralelas do mesmo campo são rejeitadas no LangGraph instalado; o exemplo em `src/demo_reducer.py` registra esse comportamento junto da acumulação com reducer.
