# Grafo, padrões e estado

O grafo de produção local é declarado e compilado em `src/grafo.py`; `conferir_grafo.py` importa o mesmo objeto `GRAFO` e consulta `get_graph()`. Comando de conferência: `python conferir_grafo.py`.

## Saída observada do grafo

Saída observada em `2026-11-08` (versão `3.1.0`; idêntica à de `2026-10-04`, e repetida em [arquitetura.md](arquitetura.md), junto do desenho):

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

O grafo contém o ciclo `decidir_proxima_acao` → `consultar_fontes` → `decidir_proxima_acao`. A decisão é em código e o ciclo atual faz uma consulta antes de encerrar ou pedir aprovação. Atualize o bloco se a saída do script mudar.

## Padrões e estado

A defesa dos padrões e a tabela campo/tipo/escritores/leitores/origem estão em [arquitetura.md](arquitetura.md), junto das arestas condicionais. Em resumo, o fluxo usa sequência com portão, router em código e um ciclo curto de ferramenta. Sectioning, voting, orquestrador-trabalhador e avaliador-otimizador não foram necessários para o catálogo local.

`eventos` usa `operator.add`: sem reducer, os registros novos não poderiam ser acumulados por vários nós. Em `2026-10-04`, `python -m src.demo_reducer` produziu `com reducer: ['A', 'B']`; sem reducer, o LangGraph `1.2.12` levantou `InvalidUpdateError` para as duas escritas paralelas no campo `valor`. O framework instalado rejeita a colisão em vez de sobrescrever silenciosamente. Mensagens guardam a fala do cliente; decisões, opções, contadores, preferência e identificadores têm campos próprios ou ficam em armazenamento dedicado. Não há segundo agente.

## O que o framework não forneceu pronto (e o que custou)

Contagem das linhas que a reimplementação sobre o grafo custou, em `src/grafo.py` e `src/tools.py` (versão `3.1.0`; recontar se o código mudar):

| Responsabilidade | Onde | Linhas |
|---|---|---|
| Motivo de término: o nó terminal diz que acabou, não por quê | `finalizar`, `src/grafo.py:260-263` e `:268`; atributo na raiz `:321` | 6 |
| Teto de passos de negócio (`MAX_PASSOS`) | `:34`; `decidir_proxima_acao` `:174-176`; `finalizar` `:264-265`; `recursion_limit` `:342` | 7 |
| Teto de tempo | `TEMPO_MAXIMO_SEGUNDOS` `:35`; `finalizar` `:266-267`; timeout HTTP de 3 s em `src/tools.py` (campo `timeout_seconds`) | 4 |
| Erro recuperável × fatal | `src/tools.py:47-75` (erro HTTP, API fora do ar e JSON inválido viram objeto `ok: false` com `como_continuar`); `agendar` `src/grafo.py:226-230` | ≈ 33 |
| Detector de laço | não existe | 0 |
| **Total** | | **≈ 50** |

**O que o framework cobriu inteiro (não precisamos escrever):**

- persistência da pausa: `SqliteSaver` e `thread_id` (`src/grafo.py:67-69`, `compile(checkpointer=…)` em `:296`);
- a pausa e a retomada: `interrupt(apresentacao)` (`:197`) e `Command(resume=…)` (`:345`); a função continua da linha seguinte sem código nosso;
- o roteamento: `add_edge` e `add_conditional_edges` com mapa de destinos explícito (`:287-295`);
- a mesclagem do estado entre nós, inclusive o reducer `operator.add` de `eventos`.

**Detector de laço.** `recursion_limit` limita o dano e não detecta: um agente preso na primeira volta gastaria o teto inteiro e devolveria o diagnóstico errado. Aqui o ciclo `decidir_proxima_acao` → `consultar_fontes` → `decidir_proxima_acao` faz no máximo uma consulta, porque `consultar_fontes` sempre deixa `resultado` preenchido. Por isso o detector não é necessário hoje. Se o ciclo virar livre (o modelo escolhendo ferramenta), o detector passa a ser obrigatório: comparar ferramenta e argumentos com os da volta anterior e encerrar com um motivo próprio.

**Tetos.** Dos quatro tetos da Aula 05, o framework cobre só o de passos (e apenas como `GraphRecursionError`, sem motivo de término). O de tempo é nosso e é verificado no fim de `finalizar` (não interrompe um nó em andamento; medido: com o Gemini lento, a execução passou dos 30 s e terminou como `limite_de_tempo`, ver [observabilidade.md](observabilidade.md)). O de custo está em `src/modelo.py` (US$ 0,01 e 4.000 tokens por chamada). Repetição: sem laço livre, não se aplica.

## A decisão que virou parâmetro

**`recursion_limit`.** *A decisão:* quantas voltas o grafo pode dar antes de ser interrompido. *Como estava justificada quando era explícita:* `MAX_PASSOS = 8`, acima do caminho mais longo (validar → contexto → decidir → fontes → decidir → preparar aprovação → aprovar → registrar → finalizar: 9 execuções de nó, e a contagem de `passos` chega a 6) mais uma margem para nós de suporte (`MAX_PASSOS + 4 = 12`). *O que acontece se o padrão da biblioteca mudar numa atualização:* o LangGraph tem um limite padrão próprio quando nenhum é passado (valor não verificado aqui e sujeito a mudar entre versões); um padrão menor que 12 derrubaria execuções legítimas com `GraphRecursionError`, e um maior deixaria um laço gastar mais antes de parar, sem que nada no nosso código avisasse. *O que fizemos:* o valor está declarado em `config` (`src/grafo.py:342`), mesmo que coincida com algum padrão, e o teto de negócio `MAX_PASSOS` encerra com o motivo `limite_de_passos` antes de o framework agir.

**Segundo exemplo.** `LANGGRAPH_STRICT_MSGPACK=true` (`src/grafo.py:16`): a desserialização estrita dos checkpoints era um padrão que podia mudar; hoje é declarada antes de o saver ser carregado.

O `recursion_limit` do framework evita execução ilimitada por nós, mas não diagnostica intenção presa. Alterá-lo requer atualizar estes documentos e demonstrar o novo limite.
