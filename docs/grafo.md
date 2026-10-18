# Grafo, padrões e estado

O grafo de produção local é declarado e compilado em `src/grafo.py`; `conferir_grafo.py` importa o mesmo objeto `GRAFO` e consulta `get_graph()`. Comando de conferência: `python conferir_grafo.py`.

## Saída observada do grafo

Saída observada em `2026-10-04`:

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

## O que o framework não forneceu pronto

| Responsabilidade | Implementação da POC |
|---|---|
| Motivo de término | `finalizar` atribui motivo; ver `src/grafo.py` |
| Detector de laço de negócio | Não há loop livre; `MAX_PASSOS` e `recursion_limit` limitam o grafo |
| Teto de tempo | `TEMPO_MAXIMO_SEGUNDOS`, verificado no nó terminal; timeout HTTP de 3 s |
| Teto de custo/tokens | Não se aplica ao mock. A redação Gemini opcional registra tokens e não dispara ferramentas |
| Erro recuperável/fatal | `ApiTools` converte falhas HTTP em objeto; erro de validação Pydantic interrompe a execução |
| Persistência de pausa | `SqliteSaver` escreve em `dados/checkpoints.sqlite`; a retomada usa o mesmo `thread_id` |

O `recursion_limit` do framework evita execução ilimitada por nós, mas não diagnostica intenção presa. A POC usa rotas finitas, então não há ciclo cuja qualidade dependa de um detector semântico. O padrão fica declarado em `MAX_PASSOS + 4`; alterá-lo requer atualizar documentos e demonstrar o novo limite.
