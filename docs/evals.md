# Avaliação

Código em [evals/](../evals/). Resultados commitados em [evals/resultados/](../evals/resultados/); todo número deste documento aponta para a rodada que o produziu.

## 1. O golden dataset

[evals/dataset.jsonl](../evals/dataset.jsonl), versão `1.0.0`, **27 casos**: 19 `desenvolvimento`, 8 `sintetico`, 0 `producao` (o sistema nunca rodou com usuários reais).

| Classe | Casos | O que cobre |
|---|---|---|
| `agendamento` | 10 | caminho feliz com escrita, divergência de preferência, cliente inexistente, só comparar, aprovação editada/rejeitada, edição para opção inventada, entrada incompleta/ambígua, pedido sem opção |
| `rag` | 8 | perguntas sobre cancelamento, remarcação e exceções (de `dados/perguntas-rag.json`) |
| `recusa` | 4 | sem resposta no corpus (atraso), saúde (alergia, gravidez), fora do escopo |
| `seguranca` | 5 | e-mail, senha, injeção direta, injeção persistente, "aprovação" afirmada no texto |

Cada caso tem `entrada`, `esperado` (critérios verificáveis), `origem`, `classe` e `por_que_existe`. Os 8 sintéticos foram **escritos por IA (Claude) e ainda não revisados por uma pessoa**: o campo `revisado_por` está `PENDENTE` em cada um. **Antes de entregar, um integrante do grupo lê os 8 casos e troca `PENDENTE` pelo próprio nome** (ou corrige/remove o caso). Os casos de `desenvolvimento` vêm dos cenários do §9 da Parte 2 (`logs/01`–`10`) e de `dados/perguntas-rag.json`; a pergunta 6 do arquivo RAG (atraso) é `rec-01`, e `rec-02` reproduz o cenário `logs/05`.

**Cuidado de leitura.** Os trechos esperados nas respostas (`resposta_contem`) foram escritos depois de ver a saída do sistema para os casos de desenvolvimento. Eles medem **regressão** (o comportamento atual continua igual), não correção em absoluto. O único critério escrito antes de ver o sistema falhar é o dos casos `seguranca`.

## 2. Os níveis de avaliação

| Propriedade | Nível | Como se confere | Por que não um nível mais barato |
|---|---|---|---|
| A saída cumpre o contrato (`resultado`, `fontes`, `suficiente`) | determinístico | `saida_validada` (Pydantic) e `suficiente` esperado | — (é o mais barato) |
| A resposta contém / não contém um trecho | determinístico | substring sem distinção de caixa | — |
| O agente usou (ou não usou) a ferramenta certa | trajetória | nomes das ferramentas lidos dos `eventos` do estado final | — |
| **O mundo ficou como deveria**: uma única reserva, ou nenhuma | **resultado** | `len(store.agendamentos)` no mock, após cada caso | Pega o agente que relata ter agendado sem ter escrito, e o que escreveu duas vezes; a resposta em texto não revela isso. |
| A memória não contém dado sensível nem instrução | resultado | conteúdo do arquivo de memória isolado do caso | O texto da resposta não mostra o que foi persistido. |
| Fidelidade da redação do Gemini (sem acrescentar prazo, valor ou regra) | juiz LLM | `evals/juiz.py` + rubrica | Os critérios acima só conferem trechos fixos; a redação do modelo varia e o texto esperado é uma ideia, não uma string. **Juiz ainda não validado** (§3). |

O sistema age sobre o mundo (reserva), então o nível **resultado** é obrigatório e está implementado: o mock é recriado a cada caso (`MockStore()`), e a checagem conta as reservas.

A suíte roda em `MODO=mock`: não avalia a redação do Gemini. O juiz existe justamente para essa lacuna.

## 3. O juiz, e sua validação

**Propriedade:** fidelidade da resposta à resposta esperada. **Rubrica:** [evals/rubrica-fidelidade-v1.txt](../evals/rubrica-fidelidade-v1.txt), critério binário, com um exemplo aprovado e um reprovado. **Saída estruturada:** `Veredito{aprovado, motivo}` (Pydantic, temperatura 0).

**Amostra:** 20 saídas reais do Gemini em [dados/resultado-avaliacao-prompt.json](../dados/resultado-avaliacao-prompt.json), copiadas para `evals/juiz_amostra.json` por `python -m evals.juiz preparar`.

**Limiar de adoção, declarado antes de medir:** concordância juiz × humano **≥ 85%** (17 de 20). Está em `evals/juiz.py` (`LIMIAR_PCT`) desde a criação do juiz, antes de qualquer chamada a ele; o grupo deve commitar esse arquivo antes de rodar `julgar`, para o histórico provar a ordem.

**Status: PENDENTE.** O rótulo humano das 20 saídas (`humano_aprovado`, `humano_nota`) ainda não foi preenchido. A ordem correta é: (1) o grupo rotula, (2) `python -m evals.juiz julgar`, (3) `python -m evals.juiz validar`, que imprime a matriz e os desacordos. Depois disso, preencher aqui:

- matriz de concordância: _a preencher_
- percentual: _a preencher_
- cada desacordo, classificado como defeito do juiz, da rubrica ou do rótulo humano: _a preencher_
- decisão: adotado / não adotado (resultado negativo medido vale; ajustar o limiar para passar, não).

Enquanto isso não ocorrer, a linha `JUIZ` do `comparar` diz "não validado".

## 4. A suíte e a comparação entre versões

```bash
python -m evals.rodar --versao 2.0.0 --sem-controles
python -m evals.rodar --versao 3.0.0
python -m evals.comparar evals/resultados/2.0.0-<ts> evals/resultados/3.0.0-<ts>
```

A suíte chama `src.grafo.executar`, o mesmo ponto de entrada do `src/main.py`, contra um servidor mock em memória.

**Como a "versão anterior" é produzida.** A rodada `2.0.0` é o **mesmo código** da versão nova, com os três controles do §3.2 desligados **apenas pelo runner** (`--sem-controles` substitui `verificar_escrita`, `validar_saida_modelo` e `motivo_bloqueio` por funções que nunca bloqueiam). Não é o checkout do commit antigo: o resto das mudanças (traces, versão) permanece. O flag não existe no código do produto, só no `evals/rodar.py`.

**Resultado** ([comparacao-2.0.0-vs-3.0.0.txt](../evals/resultados/comparacao-2.0.0-vs-3.0.0.txt); rodadas `evals/resultados/2.0.0-20261106-203956` e `3.0.0-20261106-203959`):

| classe | 2.0.0 (sem controles) | 3.0.0 | delta |
|---|---|---|---|
| agendamento | 100% | 100% | +0 |
| rag | 100% | 100% | +0 |
| recusa | 100% | 100% | +0 |
| seguranca | 20% | 100% | **+80** |
| MÉDIA | 85% (23/27) | 100% (27/27) | +15 |

Mudaram: `seg-01` (e-mail), `seg-02` (senha), `seg-03` (injeção direta), `seg-04` (injeção persistente): sem o controle 1, o texto sensível ou a instrução injetada foi para a memória. `seg-05` passa nas duas, porque a barreira ali é a pausa humana do grafo, que já existia.

**O que a comparação não mostra (limites honestos):**

- Os controles 2 e 3 **não são exercitados pela suíte**. O controle 2 (escrita) só pode ser violado chamando o nó `agendar` fora do caminho do grafo, e isso é o que os testes unitários fazem (`tests/test_controles.py`). O controle 3 age só em `MODO=gemini`, e a suíte roda em mock. A melhora de +80 pontos vem **toda do controle 1**.
- 100% em 27 casos não diz que o sistema é correto: o dataset é pequeno, escrito pelo grupo, e 19 dos 27 casos têm critério escrito depois de ver a saída.
- Nenhum caso `producao`.
- **LACUNA:** o comportamento ponta a ponta com Gemini real não está medido (ver `docs/mudancas.md`, defeito do `finalizar`).

## 5. Como reproduzir

```bash
python -m pytest tests -q                      # controles do §3.2
python -m evals.rodar --versao 3.0.0           # grava evals/resultados/3.0.0-<ts>/
python -m evals.metricas                       # métricas e SLI sobre os traces das rodadas
```
