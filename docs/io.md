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

Os exemplos abaixo foram serializados diretamente dos logs e executados em **2026-10-18 (UTC)**. Os logs guardam `executado_em`, `commit_base` e impressão SHA-256 de todos os arquivos Python em `src/` e do prompt ativo. Eles apontam para o commit `01f0b54978bff9a5040973fbb5deb4e910e7f2ca`; `arvore_de_trabalho_alterada: false` confirma que o código e o prompt correspondiam à revisão durante a execução.

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

O log mostra uma aprovação humana antes da escrita e a confirmação de uma opção que veio do catálogo mock. Metadados da execução: `2026-10-18T19:17:36Z`, revisão `01f0b54978bff9a5040973fbb5deb4e910e7f2ca`.

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

O grafo pede o serviço que falta e não executa busca de catálogo nem agendamento. Data, revisão base e impressão do código estão no log citado. Também há uma entrada ambígua em `logs/08-ambigua.json` e uma fora do escopo em `logs/09-fora-escopo.json`.

## Outros casos

- `logs/02-divergencia.json`: preferência atual clássica vence o histórico moderno, sem escrita.
- `logs/03-registro-inexistente.json`: o erro do histórico fica no log e a busca segue com o texto atual.
- `logs/04-sem-acao-principal.json`: comparação de maquiagem termina sem reserva.
- `logs/06-aprovacao-editada.json`: a pessoa troca `opc-001` por `opc-005`; uma chamada repetida retorna `ja_existia: true` e mantém um único agendamento.
- `logs/10-aprovacao-expirada.json`: uma aprovação vencida é rejeitada, sem escrita.

Para reproduzir e gerar novos tempos e impressões de código, rode `python -m src.demo`. Depois do commit da implementação, gere os logs mais uma vez para que a revisão comprometida corresponda aos exemplos.
