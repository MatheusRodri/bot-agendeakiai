# Case — AgendeAkiAI

## 1. Tema e contexto

O AgendeAkiAI é um projeto focado em recomendação e agendamento de serviços de beleza, com atenção especial à ocasião do cliente. A ideia central é criar um agente inteligente que ajude o usuário a escolher cortes, maquiagem, penteados e outros serviços conforme a natureza do evento, como casamento, formatura, entrevista, festa, viagem ou compromisso social.

O sistema não atua apenas como agenda. Ele também interpreta contexto relevante para a decisão, como clima, data, horário, local do evento, orçamento, estilo desejado, região e histórico de preferências do cliente. A partir disso, sugere opções de serviço, profissional e salão que tenham maior probabilidade de corresponder ao cenário real.

## 2. Problema em uma frase

Como recomendar e agendar serviços de beleza em linguagem natural, considerando a ocasião do cliente, as condições do evento, o clima, o orçamento e o histórico de preferências?

## 3. Quem sofre com o problema hoje

O problema afeta principalmente o cliente final, que precisa se preparar para um evento importante e costuma enfrentar dificuldades para escolher o serviço ideal. Em geral, ele precisa navegar entre vários salões, comparar opções de profissionais, verificar preços e ainda lidar com a incerteza de saber o que combina melhor com a ocasião.

Além disso, o negócio também sofre com a fricção do processo: menos conversão, maior abandono e menor recorrência de agendamentos.

## 4. Contexto de uso

O agente será usado no chat da plataforma AgendeAki, no momento em que o cliente procura um serviço para uma ocasião. O cliente inicia a conversa com texto livre; o agente consulta o catálogo e o histórico simulado, devolve até três opções e o cliente decide se quer confirmar uma delas.

Antes dele, o cliente percorre filtros de serviço, bairro, preço e horário, abre perfis de salões e compara as opções manualmente. Depois dele, a recomendação ou o agendamento confirmado segue para a API do AgendeAki; nesta entrega a API é mockada. As regras mínimas são: não inventar disponibilidade, respeitar o orçamento informado e nunca criar agendamento sem confirmação explícita.

Os casos difíceis da primeira entrega são: preferência atual que contradiz o histórico; identificador de cliente inexistente; e uma consulta que pede recomendação, mas não autorização para agendar.

## 5. Usuários e perfis

| Perfil | O que deseja | O que sabe | O que pode fazer |
|---|---|---|---|
| Cliente final | encontrar um visual adequado para a ocasião e agendar facilmente | conhece sua necessidade, gosto e evento | descreve a demanda, responde perguntas e confirma ou recusa o agendamento |
| Estabelecimento | receber clientes compatíveis e otimizar a agenda | conhece sua disponibilidade e equipe | informa horários, serviços e regras do salão |
| Operação da plataforma | reduzir abandono e melhorar conversão | conhece métricas e comportamento do usuário | acompanha exceções e atende casos que o agente não consegue resolver |

### Usuário principal

O usuário principal é o cliente final, pois ele vive a dor de decidir entre muitas opções sem saber qual é a melhor combinação para a ocasião e para o seu perfil.

## 6. Como será a interação

A interação acontece por chat, pois o cliente já descreve ocasião e estilo naturalmente. O cliente inicia a conversa; em média são duas ou três trocas: pedido inicial, pergunta opcional sobre uma preferência e recomendação. A saída é texto curto com até três opções ou uma mensagem de erro orientando o próximo passo.

Exemplo de conversa:

Cliente: "Vou para um casamento no fim de semana e quero um visual elegante, com clima quente e orçamento até R$ 150."

Agente: "Entendi. A ocasião é um casamento, então vou considerar um visual elegante e confortável para calor. Posso verificar salões próximos com horários e profissionais compatíveis. Você prefere um estilo mais clássico ou mais moderno?"

Cliente: "Mais clássico."

Agente: "Tenho 3 opções compatíveis: Salon Bela, sábado às 15h, corte e styling, R$ 120; Studio Vale, domingo às 12h, visual elegante e leve, R$ 140; Glam Hair, domingo às 13h, especialista em eventos, R$ 110. Posso sugerir a melhor alternativa para o seu caso."

A conversa termina com uma recomendação sem escrita, com um agendamento confirmado pelo cliente ou com encaminhamento para a operação quando não houver opção válida ou a API estiver indisponível.

## 7. Complexidade do caso

O problema exige interação real e não pode ser resolvido apenas com formulário. O agente precisa lidar com:

- informações incompletas na primeira mensagem;
- contexto implícito, como "casamento", "entrevista", "evento com clima quente" ou "festa à noite";
- preferências que mudam ao longo da conversa;
- comparação entre diferentes salões, profissionais e agendamentos;
- casos em que o cliente quer algo similar a um serviço usado antes, mas sem ficar preso ao histórico;
- situações em que nenhuma opção atende tudo ao mesmo tempo e o agente precisa propor alternativas.

A preferência atual vence o histórico: se o histórico indicar estilo moderno e o cliente pedir clássico, o agente recomenda clássico. Ele já tem informação suficiente quando há pelo menos uma opção dentro do serviço, bairro e orçamento pedidos; sem isso, pede uma preferência ou encaminha o caso à operação.

## 8. Workflow do agente

O workflow inicial tem sete etapas:

```text
1. ENTRADA       cliente descreve a necessidade no chat                 [CÓDIGO]
2. DECISÃO       modelo escolhe consultar, recomendar ou pedir detalhe  [MODELO]
3. CONSULTA      código chama a API mock de histórico e opções           [CÓDIGO]
4. RECUPERAÇÃO   código devolve erro da API como dado para o modelo       [CÓDIGO + MODELO]
5. RECOMENDAÇÃO  modelo compara pedido atual e opções retornadas          [MODELO]
6. CONFIRMAÇÃO   cliente autoriza; código cria agendamento                [HUMANO + CÓDIGO; ESCRITA, reversível]
7. RETORNO       código registra o motivo de parada e mostra a resposta  [CÓDIGO]
```

## 9. O sistema

O sistema é um assistente conversacional de recomendação e agendamento para serviços de beleza. Ele atua como ponte entre a intenção do cliente e os dados da plataforma, interpretando a ocasião, o contexto do evento, o histórico do cliente e a disponibilidade real de salões e profissionais.

A função central do sistema é transformar uma demanda em linguagem natural em uma recomendação útil, priorizada e capaz de conduzir a um agendamento com baixa fricção.

## 10. Nível de autonomia

Este caso exige um agente, e não apenas um formulário. O cliente não informa tudo de forma estruturada e a recomendação depende de interpretar intenção, contexto e ocasião. Um fluxo rígido seria insuficiente para esse tipo de decisão.

No entanto, a autonomia precisa ser controlada. O agente não deve decidir sozinho a reserva final. Ele deve recomendar, validar e apoiar a decisão final do cliente.

## 11. Ferramentas esperadas

| Ferramenta | Função | Leitura / escrita | Reversível | Contra o que conversa |
|---|---|---|---|---|
| `consultar_historico` | recupera preferências e agendamentos anteriores | Leitura | Sim | API mock; depois, API do monorepo |
| `buscar_opcoes` | lista serviço, salão, profissional, preço e horário | Leitura | Sim | API mock; depois, API do monorepo |
| `confirmar_agendamento` | cria a reserva de uma opção consultada | Escrita, com confirmação | Sim, por cancelamento | API mock; depois, API do monorepo |

## 12. Justificativa de negócio

### Por que um agente e não software comum

Um formulário simples não resolve bem cenários em que a demanda do cliente depende de contexto, ocasião, clima, estilo e intenção expressa em linguagem natural. O agente é útil porque ele consegue interpretar a necessidade real da pessoa e transformar isso em recomendações mais relevantes.

### Ganho esperado

Nesta primeira entrega, o grupo acompanhará somente **tempo para encontrar uma opção adequada**. Conversão e abandono continuam como hipóteses para as próximas etapas, não como promessa desta v1.

Para registrar a linha de base, cada integrante cronometra dez buscas manuais no catálogo mock, da leitura do pedido até a escolha de uma opção. Depois repete o mesmo conjunto com o agente. A planilha de medições será adicionada antes da demonstração; nenhum valor é declarado como medido antes disso.

Quando houver as medições, a conta será apresentada assim:

```text
média manual de X min para média com agente de Y min
redução = (X - Y) / X × 100
impacto diário = redução × N buscas por dia
```

O ganho do negócio é reduzir o tempo de descoberta por busca; o ganho do cliente é encontrar opções compatíveis sem abrir vários perfis e comparar horários manualmente. A tensão é que uma recomendação muito rápida pode esconder alternativas relevantes; por isso a v1 mostra até três opções e mantém a escolha com o cliente.

O custo de desenvolvimento é o tempo do grupo. O custo de execução mock é US$ 0; com o Mistral real, a estimativa está em `docs/modelos.md`. O risco assumido é recomendar uma opção pouco adequada; nesse caso, o cliente não confirma e pode pedir nova busca ou ser encaminhado à operação.

### Ganho para o usuário

Para o cliente, o ganho é menor esforço, menos navegabilidade e uma resposta mais personalizada para a ocasião. Para a plataforma, o ganho é melhor conversão, maior retenção e melhor experiência de compra.

## 13. Verificador

O verificador construído para a v1 é `src/verificar.py`, que confere os quatro casos rotulados em `dados/casos-avaliacao.json` contra os logs gerados por `python -m src.demo`.

Ele verifica: escrita somente no caso confirmado; preferência atual acima do histórico; erro estruturado para cliente inexistente; e ausência de escrita quando o cliente apenas compara opções.

```bash
python -m src.demo
python -m src.verificar
```

## 14. Critério de sucesso

O critério mínimo da Parte 1 é aprovar os **4 de 4 casos rotulados**. Além disso, o caso sem confirmação não pode criar agendamento e o caso de registro inexistente não pode encerrar o processo sem tentar buscar opções.

## 15. Dados, privacidade e próximos passos

Os dados são simulados e vivem em `dados/catalogo.json`. Eles preservam a dificuldade do domínio com uma divergência de estilo, um cliente inexistente e um pedido de comparação que não deve escrever. Não há dados pessoais reais no repositório nem no contexto enviado ao modelo.

- [ ] **RAG (Parte 2):** políticas de serviços, duração, restrições e regras de cancelamento dos salões.
- [ ] **MCP (Parte 2):** a API mock de catálogo e agendamento será reescrita como servidor MCP.
- [ ] **LangChain/LangGraph (Parte 2):** o laço manual com estado será comparado a um grafo de estado.
- [ ] **Multiagente (Parte 3):** um agente recomendador e um agente de agenda só serão separados se os testes mostrarem necessidade real.

## 16. Maior risco

O maior risco é o catálogo mock não representar disponibilidade e políticas reais dos salões. O plano B é manter o mock apenas para a avaliação da disciplina e adaptar a camada HTTP aos endpoints e regras do `monorepo-agendeaki` antes de qualquer integração real.

## 17. Conclusão

O AgendeAkiAI é um caso relevante para agentes de IA porque combina linguagem natural, recomendação contextualizada e agendamento em um domínio real. A diferenciação principal está em tratar a ocasião como parte essencial da decisão, e não apenas o serviço em si.

Esse eixo torna o projeto mais interessante para a disciplina e mais forte para o TCC, porque ele conecta uso de IA com problema de negócio real, recomendação personalizada e experiência do usuário.


**Principal ganho esperado:** Tornar a descoberta e escolha de serviços mais rápida, simples e personalizada.

**Principal métrica:** Tempo necessário para encontrar e selecionar uma opção de agendamento adequada.
