# Memória e conversa

## Fronteiras

| Estrutura | Guarda | Vida útil | Não guarda |
|---|---|---|---|
| Checkpoint SQLite | Estado da conversa e aprovação interrompida para retomar o grafo | Entre processos, até remoção explícita | Preferências globais consolidadas como memória semântica |
| Memória JSON | Episódios curtos e preferências explicitamente declaradas | Entre execuções | Respostas inferidas como preferência ou regras do corpus |
| Corpus Markdown | Regras consultáveis, com status vigente/revogado | Versionado no repositório | Dados de conversa e escolhas pessoais |
| Log JSON e trace JSONL | Evidência da execução (demonstração e registro da decisão) | Arquivo em `logs/`; o trace guarda a entrada completa e o `cliente_id` | Segredos ou dados de clientes reais |
| Memória procedural | Regras de "como fazer", em texto, no system prompt (`src/prompts/memoria-procedural.txt`) | Versionada no repositório | Qualquer dado de titular |

O checkpoint é endereçado por `conversa_id`/`thread_id` e fica em `dados/checkpoints.sqlite`. O JSON fica em `dados/memoria.json` (ignorado pelo Git).

## Curto e longo prazo

| | curto prazo (a execução) | longo prazo (atravessa execuções) |
|---|---|---|
| o que ocupa a célula neste case | system prompt, texto do cliente, opções consultadas, `aprovacao_pendente`, decisão | episódio (até 180 caracteres), preferência de estilo declarada, regras procedurais |
| persistido como | checkpoint SQLite (estado íntegro) | `dados/memoria.json` (índice por similaridade e chave-valor) e arquivo de texto no prompt |
| ciclo de vida | acaba com a execução; o checkpoint permanece até a remoção explícita | acumula até a remoção do titular |

**O que o checkpoint precisa conter para retomar sem repetir efeito colateral:** `cliente_id`, `opcoes` e `aprovacao_pendente` (para reapresentar e validar a opção editada), `decisao`, `agendamento` e `eventos` (o controle `verificar_escrita` consulta `eventos` e `agendamento` para saber se já houve escrita). A reserva usa chave de idempotência derivada de `cliente_id|opcaoId|dataHoraInicio`; por isso retomar duas vezes a mesma aprovação não cria segunda reserva (`docs/humano.md`).

**Ordem de descarte quando o contexto não cabe** (declarada; hoje o contexto enviado ao modelo é pequeno e nada é descartado): 1º sai o episódio recuperado da memória; 2º as opções além das três mostradas; 3º o histórico bruto da API. **Nunca saem:** o system prompt (com a memória procedural), o texto atual do cliente, a resposta verificada pelo código e a opção em aprovação. Cortar o fim do contexto é proibido, porque é nele que está o pedido mais recente.

## As três memórias

| Tipo | O que guarda neste case | Estrutura | Onde |
|---|---|---|---|
| episódica | o que o cliente pediu em execuções passadas | índice por similaridade (Jaccard de palavras, limiar 0,15) | `memoria.recuperar`, `dados/memoria.json` |
| semântica | fato sobre a entidade cliente: estilo declarado | chave-valor por `cliente_id`, com `atualizado_em` | `preferencias.<cliente>.estilo` |
| procedural | como agir (priorizar o pedido atual, perguntar só o serviço que falta, recusar sem corpus) | texto no *system prompt* | `src/prompts/memoria-procedural.txt`, concatenado em `src/modelo.py` |

A similaridade lexical é uma heurística: não há embedding. O fato semântico não é buscado por similaridade, porque uma chave resolve. A memória procedural é escrita por pessoa, em revisão de código, nunca pelo agente, e não pode citar titular — por isso a remoção do titular não precisa alcançá-la. Ela só é anexada ao prompt no modo Gemini (`src/modelo.py`); o prompt usado na avaliação de frase (`src/avaliar_prompt.py`) não a inclui, para não alterar o experimento.

## Política de escrita

Escolha: **o código extrai por regra**, com **barreira de segurança em código** (controle 1, `docs/seguranca.md`). O agente não decide o que guardar. Preço dessa escolha: perde o que a regra não previu (uma preferência dita com outras palavras não é aprendida).

- **Volume por execução:** no máximo **um episódio de até 180 caracteres** e **uma preferência** (chave-valor). Cada episódio ocupa algumas centenas de bytes no JSON.
- **O que entra:** só o texto digitado pelo próprio cliente. Resultados de ferramentas e trechos do corpus nunca são gravados.
- **Idempotência:** `memoria.registrar` deriva `chave = sha256(cliente_id|texto[:180])` e devolve `{"gravado", "ja_existia", "bloqueado"}`. Repetir a mesma mensagem devolve `ja_existia: true` e não grava de novo (testes `test_memoria_repetir_o_mesmo_texto_nao_duplica` e `test_memoria_mesmo_texto_de_outro_cliente_nao_colide`). Episódios gravados antes da versão 3.1.0 não têm `chave` e não são reconhecidos como repetição.
- **Preferência semântica:** só é escrita com linguagem explícita ("prefiro clássico", "gosto de natural"). `maquiagem natural` é nome de serviço, não preferência. O pedido atual prevalece sobre o histórico e sobre a memória.

## O que a recuperação por relevância traz que serializar tudo não traria

Serializar o estado de todas as execuções produziria um arquivo morto: o texto completo de todas as conversas (custo e privacidade), sem nenhuma busca que o use. A recuperação por relevância traz **um** episódio parecido com o pedido atual e a preferência declarada, e deixa o resto de fora. O que ela deixa para trás: o episódio que usa sinônimos (a similaridade é lexical), qualquer detalhe além de 180 caracteres e o que a regra de extração não previu.

## Como o agente esquece

| Causa | Escolhida? | O que faz neste sistema |
|---|---|---|
| contradição | **sim** | Uma preferência nova substitui a anterior (`atualizado_em` registra quando). A decisão é na escrita, não na leitura, porque só há um valor por chave. O pedido atual vence o histórico em qualquer caso. |
| decaimento | **não** | O volume é pequeno (um episódio de 180 caracteres por execução) e o catálogo muda pouco. Reavaliar se a memória passar de cerca de 1.000 episódios ou se houver dado real. Sem decaimento, a memória cresce de forma monotônica e uma memória envenenada só sai pela remoção por titular. |
| remoção | **sim** | `python -m src.esquecer --cliente-id ID --confirmar`. |

**Estruturas que a remoção alcança** (a lista que cobre o dado, e não só as que vêm à lembrança):

1. `dados/memoria.json`: episódios e preferências do cliente;
2. checkpoint SQLite: threads cujo estado guarda o `cliente_id`;
3. `logs/*.json`: logs de demonstração com o `cliente_id` na entrada;
4. `logs/traces.jsonl`: o trace guarda a entrada completa e os argumentos das ferramentas; `remover_traces` apaga todo trace cuja raiz é do cliente (teste `test_esquecer_remove_traces_do_cliente_e_preserva_os_outros`);
5. memória procedural: **não aplicável**, porque não cita titular (regra de revisão);
6. **fora do alcance, declarado:** `evals/resultados/*/traces.jsonl` são evidência commitada de execuções com clientes simulados (`cliente-001`, `cliente-002`); se um dia entrarem dados reais ali, o arquivo precisa entrar na rotina. O destino `TRACES_ARQUIVO` diferente do padrão também não é varrido.

**Verificação independente:** `python -m src.verificar_memoria` grava um cliente temporário (memória, checkpoint e log), confere que a preferência mais recente venceu, remove e confere que nada sobrou. Para a varredura final, procurar o identificador em `dados/`, `logs/` e `evals/`.

## Conversa e limite de contexto

**O que identifica a conversa.** `thread_id = conversa_id`, gerado pela integração por sessão. Duas conversas simultâneas da mesma pessoa têm `conversa_id` diferentes: checkpoints independentes. A memória de longo prazo é por `cliente_id`, então as duas compartilham preferências e episódios; em escrita simultânea a última vence na preferência. Compor `cliente_id:conversa_id` no `thread_id` só seria necessário se a integração reutilizasse `conversa_id` entre pessoas.

**Onde o checkpoint é gravado.** Em arquivo SQLite local (`dados/checkpoints.sqlite`), sem criptografia de aplicação; sobrevive ao encerramento do processo (`python -m src.verificar_checkpoint`).

**Quando a janela enche.** O campo `mensagens` recebe apenas a mensagem da execução atual; mensagens anteriores não são anexadas ao contexto enviado ao Gemini. O checkpoint preserva o estado necessário para retomar uma aprovação, não um histórico crescente. Assim, nada é truncado ou resumido. Se o produto passar a acumular turnos, a política recomendada é sumarizar o trecho antigo e descartar primeiro os retornos de ferramenta já usados (perde-se o detalhe literal), mantendo as mensagens recentes, e deve ser definida antes de ampliar o contexto.

**O que passa da conversa para a memória de longo prazo.** No máximo um episódio de até 180 caracteres e uma preferência explicitamente declarada. Todo o resto da conversa morre com o checkpoint.

## Limites

A amostra tem identificadores simulados e fica em disco sem criptografia própria. Não guardar dados reais nesta prova de conceito. Em produção, aplicar política de retenção, controle de acesso, autenticação do cliente e remoção coordenada dos armazenamentos reais.
