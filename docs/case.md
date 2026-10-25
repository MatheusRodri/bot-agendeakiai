# Case — AgendeAkiAI

## Problema e contexto

**Problema em uma frase:** o cliente que procura um serviço de beleza para uma ocasião precisa combinar manualmente ocasião, estilo, orçamento, localização e disponibilidade antes de conseguir escolher um horário.

O usuário que sofre diretamente é o **cliente final que precisa se preparar para um evento** e ainda não sabe qual serviço, profissional ou horário atende melhor à sua necessidade. O agente é acionado pelo cliente, no chat da área do cliente do AgendeAki, durante a descoberta de um serviço e antes da tela convencional de confirmação.

Hoje o cliente navega por filtros de serviço, salão, profissional, preço e horário; compara resultados e reinicia a busca quando uma combinação não existe. A entrada é uma mensagem em linguagem natural e a saída é uma recomendação de até três opções, seguida de confirmação explícita antes de qualquer agendamento. Depois da confirmação, a plataforma registra o agendamento e o cliente recebe a identificação dele.

As regras desta primeira versão são: orçamento máximo e bairro restringem a busca; o pedido atual prevalece sobre o histórico; só se confirma uma opção retornada na consulta da sessão; o cancelamento pode ocorrer a qualquer momento, sem antecedência mínima nem custo adicional; e a remarcação não tem custo. Não há, por enquanto, regra definida para atraso, falta ou lembrete de confirmação — esses casos são encaminhados para a operação humana.

Os casos difíceis são: preferência atual que contradiz o histórico, cliente inexistente, não haver uma opção compatível e o cliente querer somente comparar, sem autorizar escrita.

## Usuários e interação

| Perfil | O que quer | O que sabe | O que pode fazer |
|---|---|---|---|
| Cliente final — usuário principal | Escolher e agendar um serviço adequado | Sabe a necessidade e as preferências; não conhece catálogo ou disponibilidade | Descrever, corrigir preferências, escolher e confirmar o próprio agendamento |
| Estabelecimento/profissional | Manter serviços e horários corretos | Conhece sua agenda e capacidade | Atualizar catálogo e disponibilidade; não confirma em nome do cliente |
| Operação AgendeAki | Resolver exceções e proteger a experiência | Conhece regras e dados operacionais | Analisar exceções, corrigir dados e tratar cancelamento, atraso ou falta |

O canal é um chat dentro da plataforma Web: ele permite que a pessoa descreva uma ocasião sem conhecer os filtros disponíveis. O cliente inicia a conversa. A primeira mensagem descreve o que procura; em geral são de duas a quatro trocas, até que o agente tenha serviço, bairro e orçamento suficientes ou reconheça que precisa de ajuda humana. A resposta é texto curto com opções estruturadas (serviço, profissional, salão, horário e preço) e, se houver escolha explícita, uma confirmação de agendamento.

Quando uma regra ainda não existe, há conflito que o agente não consegue esclarecer, ou nenhuma opção atende aos filtros mesmo após uma flexibilização oferecida ao cliente, o fluxo termina sem escrita e chama a Operação AgendeAki.

### Diálogo de referência

> Cliente: Quero um penteado clássico para casamento no Centro, até R$ 150.
>
> Agente: Encontrei penteado clássico com Bianca no Studio Aurora, às 15h, por R$ 120. Quer confirmar esta opção?
>
> Cliente: Sim, confirmo.
>
> Agente: Agendamento confirmado. Se quiser cancelar, você pode fazer isso a qualquer momento, sem custo adicional pelo cancelamento.

O cliente normalmente não informa todos os filtros na primeira mensagem. O agente pergunta apenas pelo filtro que impede a busca; se o histórico disser “moderno” e o cliente pedir “clássico”, usa o pedido atual e informa essa priorização. Só considera que sabe o suficiente quando serviço e os filtros disponíveis permitem consultar opções. A confirmação é uma decisão do cliente, nunca uma inferência do modelo.

## Workflow

1. **ENTRADA** — recebe texto livre, identificador do cliente e da conversa. **[decide: CÓDIGO]**
2. **CONTEXTO** — consulta histórico e memória; se o cliente não existir, registra o erro e segue sem personalização. **[decide: CÓDIGO]**
3. **RECUPERAÇÃO** — encaminha a pergunta às regras Markdown ou consulta catálogo e agenda estruturados. **[decide: CÓDIGO]**
4. **ESCLARECIMENTO/RESPOSTA** — pergunta o serviço que falta, desambigua bairro, recusa regra ausente ou mostra opções. **[decide: CÓDIGO; redação Gemini opcional]**
5. **APROVAÇÃO** — antes de escrever, apresenta serviço, profissional, horário, preço e alternativas; espera decisão do cliente final. **[interrupt; 15 min]**
6. **AGENDAMENTO** — grava a reserva após aprovação, usando chave idempotente. **[ESCRITA — somente após aprovação] [decide: CÓDIGO]**
7. **TÉRMINO** — registra o motivo, resposta e episódio curto. **[decide: CÓDIGO]**

## Sistema e autonomia

O sistema recebe o pedido em texto, identifica filtros, consulta histórico, catálogo e regras e pede aprovação antes de gravar uma reserva. Preços, horários e regras vêm das fontes consultadas; o código controla a escrita.

A implementação é um **workflow com roteamento em código**. O Gemini é opcional e apenas redige a resposta final. Na Parte 2, vamos avaliar se o modelo pode interpretar melhor pedidos incompletos ou ambíguos, mantendo filtros, validação de regras e aprovação sob controle do código.

| Ferramenta | O que faz | Leitura ou escrita? | Reversível? | Contra o que conversa |
|---|---|---|---|---|
| `consultar_historico` | Retorna preferências e agendamentos do cliente | Leitura | Sim | API HTTP mock do AgendeAki |
| `buscar_opcoes` | Retorna opções por serviço, bairro e orçamento | Leitura | Sim | API HTTP mock do AgendeAki |
| `buscar_regra` | Pesquisa trechos dos documentos Markdown vigentes | Leitura | Sim | `dados/corpus/` |
| `confirmar_agendamento` | Registra a opção aprovada pelo cliente com chave idempotente | Escrita | Não nesta POC | API HTTP mock do AgendeAki |

## Justificativa de negócio

Esta POC testa se descrever a ocasião e as preferências em texto livre ajuda o cliente a encontrar uma opção com menos ações do que preencher filtros. Um formulário pode ser suficiente; a comparação vai mostrar se a conversa traz vantagem.

O benefício esperado para o cliente é informar o que procura em linguagem natural. Para o negócio, a hipótese é reduzir o esforço de busca sem diminuir a taxa de conclusão. Ainda não temos medições reais, então não afirmamos que esses ganhos já ocorreram.

A linha de base será coletada no frontend do `monorepo-agendeaki`, comparando os mesmos dez cenários no fluxo atual e no agente. Vamos registrar tempo, telas ou filtros usados, trocas e conclusão. O ganho será calculado pela diferença percentual entre as medianas de ações; os resultados e o volume mensal serão usados para estimar o impacto. O cliente continuará escolhendo e aprovando a reserva; casos sem suporte serão encaminhados à operação.

O modo mock custa US$ 0. Para o Gemini 3.8 Flash, a estimativa de tokens e custo está em [modelos.md](modelos.md). O custo de construção é o tempo da equipe. A perda mais importante é uma recomendação inadequada ou reserva indevida; a POC mitiga a segunda com confirmação explícita, mas não promete eliminar a primeira.

## Verificador e sucesso

O verificador construído é `src/verificar.py`. Ele confere os dez logs de `src/demo.py`: contrato de saída Pydantic, ausência de escrita fora da aprovação, erro de cliente inexistente, recusa sem suporte, aprovação editada/repetida e rejeição por expiração. A execução é `python -m src.verificar` depois de `python -m src.demo`.

**Verificação observada em 2026-10-04:** os **10 de 10** logs passaram; nenhum cenário sem aprovação realizou escrita; a aprovação editada repetida manteve um único identificador; a aprovação expirada terminou sem reserva. A avaliação lexical foi repetida com a regra atual em 2026-10-25 e marcou **10/10 no alvo**. Os resultados testam a POC mock, não comportamento com clientes reais.

## Dados e privacidade

Os dados são simulados e vivem em `dados/catalogo.json`. Para preservar dificuldade, incluem: divergência entre histórico “moderno” e pedido atual “clássico”; `cliente-inexistente`; consulta sem reserva; e duas opções de penteado para possibilitar aprovação editada. Os casos estão em `src/demo.py` e seus logs em `logs/`.

O domínio normalmente toca dados pessoais (nome, histórico e preferências). Nesta POC todos são fictícios. Dados reais não devem entrar no repositório nem no contexto do modelo; em produção, o identificador do cliente e o mínimo necessário devem ser buscados sob autenticação pela integração da plataforma.

## Próximas evoluções

- **MCP:** a API HTTP mock de histórico, busca e agendamento é candidata a servidor MCP na integração com `monorepo-agendeaki`; isso não faz parte desta implementação.
- **Multiagente (Parte 3):** separar recomendação e operação somente se regras e revisão humana crescerem; ainda não há justificativa.

## Complemento aprendido durante a consolidação

Nesta POC, a palavra **opção** designa um conjunto já consultado de serviço, unidade, profissional, horário e preço. A recomendação só pode escolher entre essas opções; a aprovação humana mostra todos esses dados antes da escrita. Uma edição da aprovação pode trocar para outra opção da mesma consulta, e a API mock usa a mesma chave de idempotência se a aprovação for repetida.

O catálogo é filtrado por nome de serviço, bairro e teto de preço. A frase “maquiagem natural”, por exemplo, nomeia um serviço e não é tratada automaticamente como preferência pessoal. Preferências semânticas só entram na memória quando o cliente as explicita com termos como “prefiro” ou “gosto”. O pedido atual ainda prevalece sobre histórico e memória.

O cancelamento a qualquer momento e sem custo adicional é a regra informada pelo grupo para esta POC. A remarcação sem custo e duas exceções — cancelamento pelo salão e doença no dia — foram usadas para avaliar recuperação e citação. Não houve entrevista nem pesquisa com clientes reais, salões ou operação. Os antigos prazos de 24 e 48 horas estão no corpus apenas como regras revogadas e não podem fundamentar respostas.

O agente não sabe responder sobre atraso, alergias, falta ou lembretes porque o corpus não contém orientação aprovada para esses assuntos. A lacuna produz uma recusa com orientação à operação. A busca por catálogo e por regras é lexical e pequena; ela não mede adequação estética de um serviço a uma ocasião.

O checkpoint de conversa guarda o estado necessário para retomar uma aprovação. A memória JSON guarda somente episódios curtos e preferências declaradas. O corpus de regras é conhecimento estático e separado dos dados de conversa. O comando `python -m src.esquecer --cliente-id ID --confirmar` apaga as estruturas locais vinculadas ao cliente.

## Maior risco

O maior risco é o catálogo/agenda real não expor dados consistentes o bastante para uma recomendação confiável, especialmente quando há mudança de disponibilidade entre busca e confirmação. O plano B é tratar a API do `monorepo-agendeaki` como fonte de verdade, revalidar a opção no momento da escrita e encaminhar a falha de disponibilidade ao cliente sem confirmar a reserva.
