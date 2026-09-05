# Case — Agente Inteligente do Agende Aki

## 1. O case: indústria e problema

### 1.1 Indústria

O projeto está inserido no setor de serviços de beleza e cuidados pessoais, especificamente no contexto de plataformas digitais de agendamento para salões de beleza.

O Agende Aki é uma plataforma Web que conecta clientes a estabelecimentos de beleza, permitindo a busca por estabelecimentos, serviços e profissionais, além da realização de agendamentos de acordo com datas e horários disponíveis.

Nesse contexto, propõe-se a criação de um agente LLM responsável pela interação com o cliente final durante o processo de descoberta e agendamento de serviços.

Além de auxiliar o cliente no momento atual, o agente utilizará o histórico de utilização da plataforma para identificar padrões de preferência e oferecer recomendações cada vez mais contextualizadas.

### 1.2 Problema

Durante a busca por um serviço de beleza, o cliente pode possuir diferentes necessidades e preferências relacionadas a:

- serviço desejado;
- estabelecimento;
- localização;
- profissional;
- faixa de preço;
- data;
- período do dia;
- horário disponível.

Essas informações nem sempre são fornecidas de maneira completa no início da interação.

Um cliente pode informar, por exemplo:

> "Quero cortar o cabelo sábado à tarde."

Embora exista uma intenção clara, ainda podem existir informações relevantes que precisam ser identificadas para que uma recomendação adequada seja realizada.

Além disso, no processo tradicional, as preferências demonstradas pelo cliente em utilizações anteriores podem não ser consideradas durante uma nova busca.

Dessa forma, o problema abordado pelo agente consiste em compreender as necessidades do cliente, identificar informações ausentes, consultar as opções disponíveis e utilizar o histórico de utilização para realizar recomendações mais adequadas ao seu perfil.

**Problema em uma frase:**

> Como auxiliar o cliente a encontrar serviços, estabelecimentos, profissionais e horários adequados às suas necessidades atuais, utilizando também seu histórico de utilização para personalizar as recomendações?

### 1.3 Proposta do agente

O Agente Inteligente do Agende Aki será responsável pela interação com o cliente final durante o processo de descoberta e escolha de serviços.

O cliente poderá informar suas necessidades utilizando linguagem natural, enquanto o agente interpretará a solicitação e identificará as informações necessárias para realizar a busca.

O agente poderá recomendar:

- serviços;
- estabelecimentos;
- profissionais;
- datas;
- horários disponíveis.

As recomendações considerarão dois tipos principais de informação:

**Contexto atual:** informações fornecidas pelo cliente durante a interação atual.

**Contexto histórico:** informações provenientes das utilizações anteriores do cliente e dos padrões de preferência identificados.

Por exemplo, caso um cliente tenha utilizado repetidamente determinado profissional e normalmente realize seus agendamentos aos sábados durante a tarde, essas informações poderão ser consideradas na ordenação das recomendações futuras.

O histórico não determinará obrigatoriamente a escolha do cliente. Ele será utilizado como contexto para priorizar alternativas potencialmente mais relevantes.

### 1.4 Por que utilizar um agente LLM?

O problema possui características que dificultam sua solução exclusivamente por meio de um fluxo fixo de formulários e regras.

O usuário pode fornecer informações incompletas e expressar suas necessidades de diferentes maneiras utilizando linguagem natural.

Por exemplo:

> "Quero fazer a unha depois do trabalho essa semana e queria algo perto."

Nesse caso, o agente precisa interpretar expressões como "depois do trabalho", identificar informações que ainda são necessárias e decidir quais consultas devem ser realizadas.

Além disso, quando nenhuma alternativa atende completamente às preferências informadas, o agente poderá decidir quais flexibilizações podem ser propostas.

Por exemplo:

> "Não encontrei horários com o profissional que você costuma escolher na sexta-feira à noite. Ele possui disponibilidade sábado às 10h. Também encontrei outro profissional disponível sexta-feira às 19h. Qual opção você prefere?"

Portanto, o agente terá como responsabilidades:

- interpretar solicitações em linguagem natural;
- identificar informações ausentes;
- realizar perguntas ao cliente quando necessário;
- consultar dados da plataforma;
- utilizar o histórico do cliente como contexto;
- identificar padrões de preferência;
- comparar alternativas;
- recomendar opções;
- adaptar a busca quando não encontrar uma correspondência adequada.

A confirmação final de qualquer agendamento continuará sendo responsabilidade do cliente.

### 1.5 Casos reais da indústria

Nesta etapa serão pesquisados casos reais de empresas que utilizam agentes ou inteligência artificial para atendimento, recomendação, personalização ou agendamento de serviços.

Para cada caso serão analisados:

- empresa;
- problema enfrentado;
- solução adotada;
- resultados ou métricas divulgadas;
- provável padrão arquitetural utilizado;
- limitações das informações divulgadas.

#### Caso 1 — [A pesquisar]

**Empresa:**  
**Problema:**  
**Solução:**  
**Resultados divulgados:**  
**Padrão arquitetural provável:**  
**Análise crítica:**

#### Caso 2 — [A pesquisar]

**Empresa:**  
**Problema:**  
**Solução:**  
**Resultados divulgados:**  
**Padrão arquitetural provável:**  
**Análise crítica:**

#### Caso 3 — [Opcional / a pesquisar]

**Empresa:**  
**Problema:**  
**Solução:**  
**Resultados divulgados:**  
**Padrão arquitetural provável:**  
**Análise crítica:**

---

## 2. Os usuários e como será a interação

### 2.1 Usuário principal

O principal usuário do agente será o cliente final do Agende Aki.

O agente funcionará como uma interface inteligente entre o cliente e os recursos disponíveis na plataforma, auxiliando na descoberta e escolha de serviços, estabelecimentos, profissionais e horários.

### 2.2 Interação com o agente

A interação ocorrerá por meio de uma interface conversacional integrada à plataforma Web do Agende Aki.

O cliente poderá iniciar uma solicitação utilizando linguagem natural.

Exemplo:

> **Cliente:** Quero cortar o cabelo sábado à tarde.

O agente deverá interpretar a solicitação e verificar as informações disponíveis sobre o cliente.

Caso exista histórico suficiente, ele poderá utilizá-lo para melhorar a recomendação.

> **Agente:** Você costuma realizar seus cortes com o profissional João aos sábados à tarde. Ele possui horários disponíveis às 14h e às 16h. Deseja uma dessas opções ou prefere consultar outros profissionais?

O cliente também poderá alterar suas preferências a qualquer momento.

> **Cliente:** Dessa vez quero conhecer outro profissional e gastar no máximo R$ 60.

Nesse caso, o agente deverá considerar as novas informações como prioritárias para aquela interação e realizar uma nova busca.

### 2.3 Fluxo esperado

O fluxo básico será:

1. O cliente informa sua necessidade utilizando linguagem natural.
2. O agente interpreta a solicitação.
3. O agente consulta o contexto e o histórico disponível do cliente.
4. O agente identifica informações relevantes que ainda estão ausentes.
5. Quando necessário, o agente realiza perguntas ao cliente.
6. O agente consulta serviços, estabelecimentos, profissionais e horários disponíveis.
7. O agente compara as alternativas encontradas.
8. O agente utiliza as preferências atuais e históricas para priorizar as opções.
9. O agente apresenta uma ou mais recomendações.
10. O cliente seleciona uma alternativa.
11. O agente prepara o agendamento.
12. O cliente confirma a realização do agendamento.
13. A interação e a escolha realizada passam a contribuir para o histórico de utilização do cliente.

### 2.4 Histórico e identificação de padrões

O agente utilizará o histórico de utilização para identificar padrões relacionados às escolhas do cliente.

Entre as informações que poderão ser analisadas estão:

- serviços realizados com maior frequência;
- estabelecimentos utilizados;
- profissionais escolhidos;
- dias da semana mais utilizados;
- períodos e horários preferidos;
- faixa de preço das escolhas realizadas;
- frequência de utilização de determinados serviços;
- recomendações anteriormente aceitas.

Essas informações poderão ser utilizadas para personalizar futuras recomendações.

Por exemplo:

> Um cliente que normalmente realiza corte de cabelo aos sábados durante a tarde e frequentemente escolhe determinado profissional poderá receber inicialmente opções que correspondam a esse padrão.

Os padrões identificados não serão tratados como regras obrigatórias. As informações fornecidas pelo cliente na interação atual terão prioridade sobre preferências identificadas anteriormente.

### 2.5 Memória do agente

A memória poderá ser dividida em dois contextos principais.

**Memória de curto prazo**

Representa as informações da conversa atual, como:

- serviço solicitado;
- localização desejada;
- orçamento;
- data;
- horário;
- preferências informadas durante a conversa.

**Memória de longo prazo**

Representa informações obtidas a partir do histórico de utilização, como:

- serviços frequentemente utilizados;
- profissionais recorrentes;
- estabelecimentos preferidos;
- horários mais escolhidos;
- faixas de preço recorrentes;
- padrões identificados ao longo das utilizações.

A combinação desses dois contextos permitirá que o agente considere tanto a necessidade atual quanto o comportamento anterior do cliente.

### 2.6 Autonomia e confirmação

O agente terá autonomia para:

- interpretar solicitações;
- consultar o histórico;
- identificar padrões;
- realizar perguntas;
- consultar serviços;
- consultar estabelecimentos;
- consultar profissionais;
- consultar horários;
- comparar alternativas;
- recomendar opções.

Entretanto, o agente não deverá realizar automaticamente uma ação que efetive um agendamento sem a autorização do cliente.

Antes da conclusão, o agente deverá apresentar as informações selecionadas e solicitar confirmação.

Exemplo:

> "Encontrei um horário para corte com João, no Salão X, sábado às 14h, por R$ 55. Deseja confirmar esse agendamento?"

Somente após a confirmação do cliente o processo poderá prosseguir.

---

## 3. Ganhos esperados

### 3.1 Objetivo

O principal objetivo do agente é tornar o processo de descoberta e escolha de serviços mais simples e personalizado.

No fluxo tradicional, o cliente precisa procurar e combinar manualmente informações relacionadas a estabelecimentos, serviços, profissionais e horários.

Com o agente, o cliente poderá descrever sua necessidade utilizando linguagem natural e receber recomendações baseadas tanto na solicitação atual quanto em seu histórico de utilização.

### 3.2 Ganhos esperados

Espera-se que o agente proporcione:

- redução do esforço necessário para encontrar um agendamento adequado;
- redução do tempo gasto durante a busca;
- diminuição da quantidade de etapas manuais;
- recomendações personalizadas;
- aproveitamento do histórico de utilização do cliente;
- identificação de padrões de preferência;
- maior facilidade para encontrar alternativas;
- experiência de atendimento mais contextualizada ao longo do tempo.

### 3.3 Métrica principal

A principal métrica proposta será:

**Tempo necessário para encontrar e selecionar uma opção de agendamento adequada às necessidades do cliente.**

Serão comparados dois cenários:

**Fluxo tradicional**

O cliente utiliza os recursos convencionais da plataforma para procurar estabelecimento, serviço, profissional, data e horário.

**Fluxo com agente**

O cliente descreve sua necessidade em linguagem natural e recebe recomendações do agente considerando suas preferências atuais e, quando disponível, seu histórico de utilização.

### 3.4 Métricas complementares

Além do tempo necessário para encontrar uma opção, poderão ser avaliadas:

- quantidade de interações necessárias até uma escolha;
- taxa de conclusão dos cenários;
- quantidade de recomendações aceitas;
- capacidade do agente de identificar corretamente preferências do cliente;
- capacidade de recomendar alternativas quando a primeira opção não estiver disponível.

### 3.5 Linha de base

A linha de base será obtida experimentalmente.

Serão definidos cenários de utilização e registrado o tempo necessário para concluir cada cenário utilizando o fluxo tradicional do Agende Aki.

Posteriormente, os mesmos cenários serão realizados utilizando o agente.

Exemplos:

- encontrar um serviço específico em determinada data;
- encontrar um serviço dentro de determinada faixa de preço;
- encontrar um serviço considerando localização e período do dia;
- encontrar um profissional já utilizado anteriormente;
- encontrar uma alternativa quando a preferência principal estiver indisponível.

Os valores quantitativos serão definidos somente após a realização dos testes, evitando a utilização de estimativas sem evidências.

---

## Resumo do case

**Projeto:** Agende Aki  
**Agente:** Agente Inteligente do Agende Aki  
**Indústria:** Serviços de beleza e cuidados pessoais  
**Usuário principal:** Cliente final  
**Interface:** Conversacional integrada à plataforma Web  

**Responsabilidade principal:** Interagir com o cliente e recomendar serviços, estabelecimentos, profissionais, datas e horários de acordo com suas necessidades e preferências.

**Memória:** Manter contexto da interação atual e utilizar o histórico de utilização para identificar padrões de preferência.

**Personalização:** Utilizar padrões históricos para priorizar recomendações futuras sem impedir que o cliente altere suas preferências.

**Autonomia:** Consultar informações, analisar alternativas e realizar recomendações.

**Ação que exige confirmação:** Efetivação do agendamento.

**Principal ganho esperado:** Tornar a descoberta e escolha de serviços mais rápida, simples e personalizada.

**Principal métrica:** Tempo necessário para encontrar e selecionar uma opção de agendamento adequada.