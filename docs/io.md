# Contrato de entrada e saída

## Entrada

O cliente envia texto livre em português. O identificador do cliente e o da conversa acompanham a mensagem pela integração e não são digitados pelo cliente. `conversa_id` é usado como `thread_id` para persistir e retomar o grafo. `EntradaAgente` remove espaços nas pontas e rejeita texto, `cliente_id` ou `conversa_id` vazios; a CLI recebe a mensagem por `--message`.

## Saída

`SaidaAgente` é um modelo Pydantic com os campos obrigatórios:

| Campo | Tipo | Significado |
|---|---|---|
| `resultado` | `str` | Resposta ou decisão apresentada ao cliente |
| `fontes` | `list[str]` | Ferramenta, corpus ou entrada que sustenta a resposta |
| `suficiente` | `bool` | Se a base consultada permite responder. Recusa e pergunta de esclarecimento usam `false` |

Os exemplos abaixo foram serializados diretamente dos logs e executados em **2026-11-08 (UTC)**. Os logs guardam `executado_em`, `commit_base` e impressão SHA-256 de todos os arquivos Python em `src/` e do prompt ativo. Eles apontam para o commit `b6ef0d9f64827b84893755d4a9a00ba27d1057fc`; `arvore_de_trabalho_alterada: false` confirma que o código e o prompt correspondiam à revisão durante a execução.

## Exemplo 1 — caminho feliz

Entrada exata, caso `logs/01-caso-simples.json`:

```text
Quero um penteado clássico para casamento no Centro até R$ 150. Confirmo o agendamento da melhor opção encontrada.
```

Saída completa validada:

```json
{
  "resultado": "Agendamento agd-001 confirmado: Penteado clássico com Bianca no Studio Aurora, por R$ 120.00.",
  "fontes": ["API mock: catálogo de opções"],
  "suficiente": true
}
```

O log mostra uma aprovação humana antes da escrita e a confirmação de uma opção que veio do catálogo mock. Metadados da execução: `2026-11-08T20:00:32Z`, revisão `b6ef0d9f64827b84893755d4a9a00ba27d1057fc`.

## Exemplo 2 — recusa sem suporte no corpus

Entrada exata, caso `logs/05-fora-do-corpus.json`:

```text
Qual produto devo usar para tratar minha alergia na pele?
```

Saída completa validada:

```json
{
  "resultado": "Não encontrei uma regra suficiente no corpus para responder com segurança. Procure a operação do AgendeAki.",
  "fontes": [],
  "suficiente": false
}
```

O campo `suficiente` é falso e não há citação porque o corpus não traz orientação sobre alergias. Metadados da execução estão em `logs/05-fora-do-corpus.json`.

## Exemplo 3 — entrada incompleta

Entrada exata, caso `logs/07-incompleta.json`:

```text
Quero ajuda para me arrumar para um evento.
```

Saída completa validada:

```json
{
  "resultado": "Qual serviço você procura: penteado, maquiagem ou corte?",
  "fontes": ["entrada do cliente"],
  "suficiente": false
}
```

O grafo pede o serviço que falta e não executa busca de catálogo nem agendamento. A partir da versão `3.2.0`, a pergunta lista também `barba` e `unha` ("Qual serviço você procura: penteado, maquiagem, corte, barba ou unha?"); o log citado é anterior e mostra o texto antigo. Data, revisão base e impressão do código estão no log citado. Também há uma entrada ambígua em `logs/08-ambigua.json` e uma fora do escopo em `logs/09-fora-escopo.json`.

## Outros casos

- `logs/02-divergencia.json`: preferência atual clássica vence o histórico moderno, sem escrita.
- `logs/03-registro-inexistente.json`: o erro do histórico fica no log e a busca segue com o texto atual.
- `logs/04-sem-acao-principal.json`: comparação de maquiagem termina sem reserva.
- `logs/06-aprovacao-editada.json`: a pessoa troca `opc-001` por `opc-005`; uma chamada repetida retorna `ja_existia: true` e mantém um único agendamento.
- `logs/10-aprovacao-expirada.json`: uma aprovação vencida é rejeitada, sem escrita.

## Modo conversa (versão 3.2.0)

**Entrada.** Um texto livre por turno, digitado no `python -m src.main --chat` (ou passado a `Conversa.responder(texto)`, `src/conversa.py`). O `cliente_id` vem do login no backend real (ou é `cliente-simulado` offline); a conversa mantém, entre turnos, o salão, os serviços recomendados, o dia, o horário e se o cliente pediu explicitamente para agendar.

**Saída por turno.** Um dicionário com os três campos de `SaidaAgente` e o motivo do turno:

| Campo | Tipo | Significado |
|---|---|---|
| `resultado` | `str` | Texto mostrado ao cliente |
| `fontes` | `list[str]` | `"API AgendeAki: salões próximos, serviços e horários"`, a regra do corpus, ou vazio |
| `suficiente` | `bool` | `true` quando há resumo completo, agendamento ou regra encontrada |
| `motivo` | `str` | `aguardando_cliente`, `resposta_final`, `agendamento_confirmado`, `escrita_bloqueada`, `fora_do_escopo`, `erro_ferramenta` ou `suspenso` |

**Exemplo (salão simulado, `MODO=mock`, saída real de `Conversa.responder`, 2026-11-11).** Entrada do primeiro turno:

```text
Tenho uma reunião importante no trabalho com clientes de alto padrão, preciso me arrumar.
```

```text
Salão mais próximo: Barbearia Simulada (Unidade Santo Amaro), a 1,2 km — Rua Exemplo, 100 - Santo Amaro - São Paulo/SP.
Recomendo:
  • Corte de Cabelo Masculino Premium — R$ 80,00 (45 min)
  • Barba — R$ 30,00 (30 min)
  • Manicure — R$ 35,00 (30 min)
Total: R$ 145,00, cerca de 1h45. Pela ocasião, priorizei as versões mais completas de cada serviço.
Para qual dia você quer? (ex.: amanhã, sexta, 20/11)
```

`motivo = aguardando_cliente`, `suficiente = false`. Depois de "amanhã", "10h" e "pode agendar", o último turno termina com `motivo = agendamento_confirmado` e os códigos devolvidos pela API. Os casos `conv-*` de `evals/dataset.jsonl` cobrem as variações (`docs/evals.md` §4.2).

Para reproduzir e gerar novos tempos e impressões de código, rode `python -m src.demo`. Depois do commit da implementação, gere os logs mais uma vez para que a revisão comprometida corresponda aos exemplos.
