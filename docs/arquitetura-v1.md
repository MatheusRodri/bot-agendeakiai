# Arquitetura v1 — AgendeAkiAI

## Contexto

O problema do AgendeAkiAI é recomendar serviços de beleza e auxiliar no agendamento com base na ocasião do cliente, no estilo desejado, no clima, no orçamento, na localização e no histórico de preferências. A arquitetura precisa resolver uma combinação de interpretação em linguagem natural, consulta a dados estruturados e recomendação contextualizada.

Nesta primeira versão, o sistema é um agente simples e controlado, com poucas ferramentas e uma decisão clara: o modelo interpreta a intenção e o código faz consultas e validações. Não é um multiagente, e não é um workflow puro, porque parte da decisão depende da linguagem natural do cliente e da comparação entre opções.

---

## 1. Entrada

### O que chega ao sistema

A entrada principal é uma mensagem em texto livre do cliente, por exemplo:

- "Vou para um casamento no fim de semana e quero algo elegante e confortável para calor."
- "Preciso de uma maquiagem para formatura, perto da minha casa, até R$ 150."
- "Quero um corte para entrevista, profissional e rápido."

### De onde vem

A entrada vem do canal conversacional do cliente dentro da plataforma ou de um chat embutido no sistema. O usuário inicia a conversa, e o agente responde em contexto real de tempo de execução.

### Heterogeneidade da entrada

A entrada é maioritariamente homogênea em formato (texto livre), mas varia muito em intenção e grau de detalhamento. Em geral:

- ~70% das mensagens são pedidos de recomendação e agendamento;
- ~20% envolvem ajuste de preferências ou mudança de contexto;
- ~10% são casos ambíguos, sem informação suficiente ou com pedido fora do escopo.

Essa proporção justifica uma etapa de triagem, mas não exige arquitetura complexa de roteamento.

---

## 2. System

### System prompt

"Você é um assistente de beleza e agendamento que recomenda serviços adequados à ocasião do cliente, considerando estilo, clima, orçamento, localização, disponibilidade e preferências históricas, e nunca confirma um agendamento sem autorização explícita do cliente."

### Ferramentas

| Ferramenta | O que faz | Tipo | Reversível? | Integração HTTP |
|---|---|---|---|---|
| `consultar_historico` | recupera preferências e agendamentos anteriores | Leitura | Sim | `GET /api/clientes/agendamentos/historico` |
| `buscar_opcoes` | busca serviço, salão, profissional, preço e horário em uma consulta | Leitura | Sim | `GET /api/clientes/opcoes` no mock; depois adaptará as consultas do monorepo |
| `confirmar_agendamento` | cria o agendamento de uma opção já consultada | Escrita, exige confirmação | Sim, por cancelamento | `POST /api/clientes/agendamentos` |

### Estado

O estado precisa sobreviver de um passo ao seguinte e guardar:

- mensagem do cliente;
- identificador do cliente;
- flag de confirmação explícita;
- contadores de passos, tokens e custo;
- histórico consultado;
- opções encontradas;
- agendamento criado, quando houver;
- trajetória de decisões e ferramentas;
- resposta e motivo da terminação.

### Orçamento

Para esta primeira versão, o orçamento deve ser explícito:

- máximo de 6 chamadas ao modelo por execução;
- máximo de 4.000 tokens de entrada + saída;
- máximo de 120 segundos por execução;
- teto estimado de US$ 0,01 quando o Mistral é usado;
- máximo de 3 alternativas sugeridas ao cliente.

Esses limites evitam que o agente fique vagueando ou gastando tokens sem necessidade.

---

## 3. Processamento

### Fluxo proposto

```text
1. ENTRADA       recebe texto, cliente e flag de confirmação              [CÓDIGO]
2. DECISÃO       escolhe consultar, recomendar ou pedir detalhe           [AGENTE; máx. 6 passos]
3. CONSULTA      chama histórico e/ou busca de opções pela API HTTP        [CÓDIGO]
4. RECUPERAÇÃO   transforma erro da API em dado acionável                  [AGENTE; mesmo orçamento]
5. RECOMENDAÇÃO  compara o pedido atual, o histórico e até 3 opções        [AGENTE; mesmo orçamento]
6. CONFIRMAÇÃO   cria somente uma opção já consultada                      [HUMANO + CÓDIGO; ESCRITA]
7. TÉRMINO       registra resposta, erro ou orçamento esgotado             [CÓDIGO]
```

### O que sai de cada etapa

```text
2. DECISÃO
   entra:  mensagem + estado explícito da execução
   sai:    tool call tipada ou resposta final

3. CONSULTA
   entra:  {"servico": "penteado", "bairro": "Centro", "orcamento_max": 150}
   sai:    {"ok": true, "opcoes": [{"opcaoId": "opc-001", "salao": "Studio Aurora", ...}]}

4. RECUPERAÇÃO
   sai:    {"ok": false, "erro": {"codigo": "CLIENTE_NAO_ENCONTRADO", ...}, "como_continuar": "Continue sem personalização..."}

5. RECOMENDAÇÃO
   sai:    texto de até 5 frases com somente dados retornados pela API

6. CONFIRMAÇÃO
   entra:  opcaoId já consultado + confirmação externa verdadeira
   sai:    agendamento criado ou erro estruturado

7. TÉRMINO
   sai:    motivo, passos, tokens, custo estimado, trajetória e resposta
```

### Saída final que o usuário vê

> "Melhor opção: opc-001, Penteado clássico com Bianca no Studio Aurora, Centro, por R$ 120. Nenhum agendamento foi realizado."

---

## 4. Justificativa da arquitetura

### Por que este padrão

A arquitetura escolhida é um agente com triagem e recomendação contextualizada, porque a decisão principal depende de:

- interpretação do texto livre do cliente;
- extração de parâmetros implícitos;
- consulta a dados reais de serviços e agenda;
- comparação entre múltiplas alternativas;
- personalização com base no histórico e no contexto da ocasião.

Esse tipo de tarefa exige decisão em tempo de execução e não é bem resolvida por um formulário ou por um workflow rígido.

O único padrão autônomo desta v1 é **agente com ferramentas**. Ele é necessário porque o cliente pode descrever a mesma necessidade de muitas formas e o modelo decide, em tempo de execução, se precisa do histórico, de opções ou de uma pergunta de complemento. Um roteador ou multiagente seria mais complexo sem resolver uma necessidade presente nesta entrega.

### Por que não usar uma arquitetura mais simples

Um workflow simples não seria suficiente, porque o cliente não entrega toda a informação de forma estruturada. A intenção pode vir como "vou para um casamento", "quero algo mais leve", "vou para um evento no calor" ou "quero algo elegante sem gastar muito". Isso exige inferência, interpretação e comparação entre opções.

### Por que não usar multiagente agora

A versão atual não precisa de multiagente porque existe uma única jornada principal: entender a ocasião, consultar dados e recomendar. O problema ainda é resolvido com um único agente + ferramentas, e a disciplina pede usar a menor autonomia que resolve o problema.

---

## 5. Resumo executivo

A arquitetura v1 do AgendeAkiAI é uma solução de agente simples, com:

- entrada em texto livre;
- triagem por intenção;
- extração de contexto da ocasião;
- perguntas de complemento apenas quando necessário;
- consulta de dados e histórico;
- ranqueamento de opções;
- recomendação curta e objetiva;
- confirmação final do cliente antes da ação escrita definitiva.

Essa arquitetura resolve o problema principal do projeto sem exagerar em autonomia ou complexidade, mantendo o alinhamento com a disciplina e com a lógica de evolução futura do sistema.
