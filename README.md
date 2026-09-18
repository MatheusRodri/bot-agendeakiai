# AgendeAkiAI

## Grupo

- Emily Oliveira
- Felipe Macena
- Matheus Rodrigues

## Visão geral

O AgendeAkiAI é um assistente inteligente para recomendação e agendamento de serviços de beleza. A ideia principal do projeto vai além de marcar um horário: o agente também recomenda cortes, maquiagem, penteados e outros serviços conforme a ocasião do cliente, como casamento, formatura, entrevista, festa, viagem ou evento social.

O agente entende contexto relevante para a decisão, como:

- ocasião e tipo de evento;
- clima e estação do ano;
- data, horário e local do evento;
- orçamento disponível;
- região ou bairro preferido;
- estilo desejado;
- histórico do cliente;
- disponibilidade de salões e profissionais.

Com isso, ele consegue sugerir não apenas o serviço mais adequado, mas também o melhor salão, profissional e horário para aquele cenário específico.

## Problema de negócio

Hoje, o cliente que precisa se preparar para um evento costuma navegar entre vários salões, consultar diferentes profissionais, comparar preços e tentar entender o que combina com a ocasião. Esse processo exige esforço manual e muitas vezes não considera a intenção real do cliente, como a ocasião, o estilo desejado ou o clima do evento.

Exemplos comuns:

- "Vou para um casamento no fim de semana e quero algo elegante, mas sem exagerar no valor."
- "Preciso de uma maquiagem para formatura em clima quente e com acabamento natural."
- "Quero um corte para entrevista, profissional, rápido e bem arrumado."
- "Vou para uma festa à noite e quero um visual que combine com o vestido e com a estação."

Nesse contexto, o agente precisa:

- interpretar a ocasião e a intenção do cliente;
- identificar quais informações ainda faltam;
- consultar opções de serviços, profissionais e horários disponíveis;
- considerar clima, local, orçamento e estilo para recomendar uma solução útil;
- usar histórico e preferências do cliente para tornar a recomendação mais personalizadas;
- apresentar opções de forma clara e objetiva;
- solicitar confirmação antes de concluir o agendamento.

## Usuário principal

O usuário principal é o cliente final do AgendeAkiAI, que busca uma recomendação inteligente para se preparar para um evento e, ao mesmo tempo, deseja agendar o serviço com mais praticidade.

## Perfis envolvidos

- Cliente final: descreve a ocasião, responde às perguntas e confirma a escolha;
- Estabelecimento: oferece serviços, profissionais e agenda;
- Plataforma: disponibiliza dados de salão, agenda e histórico;
- Operação: acompanha casos de exceção e validação do processo.

## Proposta do agente

O agente será responsável por:

1. receber a solicitação em linguagem natural;
2. identificar a ocasião e as intenções do cliente;
3. coletar informações relevantes que ainda faltam;
4. consultar serviços, salões, profissionais e horários disponíveis;
5. considerar clima, orçamento, local e histórico do cliente;
6. sugerir as melhores opções com explicação curta e clara;
7. auxiliar na confirmação do agendamento final.

A recomendação não é automática. O agente apresenta alternativas confiáveis e o cliente decide a melhor opção.

## Exemplo de conversa

Cliente: "Vou para um casamento no fim de semana e quero algo elegante, com cabelo bonito, mas sem gastar muito."

Agente: "Entendi. Vou considerar que a ocasião é um casamento, com foco em visual elegante e valor moderado. Posso verificar opções de salão e profissionais próximos a você, além de horários disponíveis. Você prefere algo mais clássico ou mais moderno?"

Cliente: "Mais clássico e com clima quente."

Agente: "Tenho 3 opções compatíveis com seu perfil: Salon Bela, domingo às 15h, corte e styling, R$ 120; Studio Vale, sábado às 17h, visual elegante e mais leve, R$ 140; Glam Hair, domingo às 13h, com profissional especializada em eventos, R$ 110. Posso sugerir a melhor opção para a ocasião e confirmar o agendamento."

## Valor gerado

O agente entrega valor para o cliente e para a plataforma:

- menos fricção na busca por serviços e horários;
- recomendações mais relevantes para cada ocasião;
- redução de abandono no processo de agendamento;
- melhor conversão em atendimentos;
- maior personalização com base em estilo, clima e histórico do cliente;
- experiência mais útil do que uma busca simples por filtros.

## Sistema

O sistema será uma assistente conversacional para recomendação e agendamento de serviços de beleza. Ele recebe a solicitação em linguagem natural, interpreta a ocasião do cliente, coleta o que falta e sugere alternativas relevantes com base em contexto, histórico e disponibilidade.

### Arquitetura esperada

A versão inicial do projeto será baseada em um agente simples com:

- entrada em linguagem natural;
- extração da ocasião e dos parâmetros relevantes;
- consulta de dados de salão, profissionais e agenda;
- uso de memória de curto prazo e histórico do cliente;
- ranking de alternativas com justificativa;
- confirmação final pelo usuário.

A arquitetura evoluirá para uma solução mais robusta em etapas posteriores, incluindo memória, RAG, integração com software tradicional e orquestração multiagente.

## Estrutura do repositório

- `src/main.py`: laço do agente, estado, orçamento e três ferramentas;
- `src/mock_api.py`: API HTTP tradicional que simula o backend do AgendeAki;
- `src/demo.py`: execução automática dos quatro casos da entrega;
- `prompts/`: prompt versionado;
- `dados/`: catálogo e clientes simulados;
- `dados/conhecimento/`: documentos simulados para a futura base de conhecimento;
- `logs/`: trajetórias geradas pela demonstração;
- `docs/`: case, análise dos modelos e arquitetura.

## Status do projeto

A prova de conceito do item 4 está implementada com uma API mock. A próxima etapa será substituir a camada HTTP mock pelos endpoints do `monorepo-agendeaki`.

## Como rodar

Requer Python 3.11 ou superior. Na raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

O `.env` possui somente as três configurações do modelo:

```env
OPENAI_API_KEY=sua_chave_da_mistral
LLM_BASE_URL=https://api.mistral.ai/v1
LLM_MODELO=mistral-small-latest
```

Para uma demonstração totalmente local e sem consumir a API da Mistral:

```bash
python -m src.demo
```

Esse comando inicia a API mock em outro processo, roda os quatro casos obrigatórios e grava os resultados em `logs/`.

Depois, confira o verificador mínimo da entrega:

```bash
python -m src.verificar
```

Para conversar com o Mistral, inicie a API mock no primeiro terminal:

```bash
python -m src.mock_api
```

No segundo terminal, execute o agente sem a opção `--mock`:

```bash
python -m src.main \
  --cliente-id cliente-001 \
  --message "Quero um penteado clássico para casamento no Centro até R$ 150"
```

O mesmo comando pode ser testado sem chamada externa acrescentando `--mock`. A opção `--confirmar` autoriza uma escrita; sem ela, o código bloqueia qualquer tentativa de agendamento.

## Como usar

O usuário informa uma frase em linguagem natural no argumento `--message`. O agente consulta o histórico e as opções pela API HTTP, recomenda até três alternativas e somente confirma uma delas quando o comando inclui `--confirmar` e a própria mensagem contém esse pedido.

Exemplo completo sem custo:

```bash
# terminal 1
python -m src.mock_api

# terminal 2
python -m src.main --mock --cliente-id cliente-001 \
  --message "Quero penteado clássico para casamento no Centro até R$ 150"
```

Saída:

```text
Sua preferência atual foi priorizada sobre o histórico. Melhor opção: opc-001: Penteado clássico com Bianca no Studio Aurora, Centro, por R$ 120.00. Nenhum agendamento foi realizado.
[terminação=resposta_final; passos=3; tokens=493; custo_usd=0.00000000]
```

Internamente, o fluxo é:

1. o cliente descreve a ocasião e a necessidade em linguagem natural;
2. o modelo decide quais ferramentas consultar;
3. o código executa as consultas HTTP e devolve os resultados ao modelo;
4. o modelo recomenda uma opção;
5. o código só escreve se houver confirmação explícita.

O agente não inventa disponibilidade, não consulta dados reais nesta versão e não agenda sem confirmação. Se o cliente ou a opção não existir, o erro da ferramenta volta ao modelo com uma orientação para continuar com segurança.

## Critério de sucesso

O agente será considerado útil quando puder:

- entender corretamente a ocasião e a intenção do cliente;
- coletar apenas as informações que faltam;
- recomendar serviços e profissionais adequados ao evento;
- levar em conta clima, orçamento, local e estilo;
- sugerir opções de forma clara e objetiva;
- reduzir a fricção do processo de agendamento.

## Documentação principal

- [docs/case.md](docs/case.md)
- [docs/modelos.md](docs/modelos.md)
- [docs/arquitetura-v1.md](docs/arquitetura-v1.md)

## Observação

O projeto não é apenas um chatbot para marcar horário. O diferencial do AgendeAkiAI é recomendar serviços de beleza de acordo com a ocasião, com contexto real do evento e com maior personalização para o cliente.

Esse é o eixo principal do caso e da proposta de valor do sistema.


**Principal ganho esperado:** Tornar a descoberta e escolha de serviços mais rápida, simples e personalizada.

**Principal métrica:** Tempo necessário para encontrar e selecionar uma opção de agendamento adequada.
