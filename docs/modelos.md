# Análise de modelos — AgendeAkiAI

## 1. Objetivo

A escolha do modelo precisa considerar o problema do AgendeAkiAI: interpretar intenção em linguagem natural, extrair contexto, comparar opções de salão/profissional/horário e recomendar de forma útil sem exigir muito esforço do cliente. A decisão não é sobre “o modelo mais poderoso”, e sim sobre o modelo que melhor combina custo, robustez e adequação ao caso.

---

## 2. Modelos candidatos

Os candidatos considerados foram:

1. Mistral Small (`mistral-small-latest`)
2. GPT-4o-mini
3. Gemini 1.5 Flash

Os critérios escolhidos foram:

- capacidade de raciocínio e interpretação de contexto;
- suporte a tool calling e saída estruturada;
- custo por execução;
- latência para conversa em tempo real;
- compatibilidade com a biblioteca OpenAI via base_url.

### Comparação dos eixos

| Eixo | Mistral Small | GPT-4o-mini | Gemini 1.5 Flash |
|---|---|---|---|
| Raciocínio | Bom para instruções curtas e estruturadas | Muito bom para inferência e contexto | Bom, mas precisa ser verificado no caso |
| Tool calling | Sim | Sim | Sim |
| Saída estruturada | Boa | Excelente | Boa |
| Custo | Baixo e com uso incluído no Free mode, sujeito a limites | Baixo/médio | Médio |
| Latência | Boa | Boa | Boa |
| Adequação ao caso | Alta | Muito alta | Média/alta |
| Compatibilidade com a biblioteca `openai` | Sim, por endpoint compatível | Nativa | Exige uma camada compatível |

A Mistral documenta que sua API segue a estrutura de Chat Completions da OpenAI. Por isso o projeto pode cumprir a exigência de usar a biblioteca Python `openai` apenas alterando `base_url` e o nome do modelo. O alias `mistral-small-latest` é o equivalente sugerido pela própria Mistral para usos antes atendidos por `gpt-4o-mini`: [guia de migração da Mistral](https://docs.mistral.ai/resources/migration-guides).

---

## 3. Conta de custo por execução

Como a disciplina pede, a estimativa precisa ser feita a partir da chamada real do sistema. Para uma versão inicial do agente, o fluxo pode ter:

- 1 chamada para triagem/intenção;
- 1 chamada para extração de parâmetros;
- 1 chamada para recomendação final;
- 1 chamada opcional para revisão da resposta.

Uma estimativa simples é:

```text
custo por execução =
(token entrada total × preço entrada)
+ (token saída total × preço saída)
```

Exemplo ilustrativo:

```text
1. triagem: 800 tokens entrada + 200 tokens saída
2. extração: 1.200 tokens entrada + 300 tokens saída
3. recomendação: 1.600 tokens entrada + 500 tokens saída
4. revisão: 900 tokens entrada + 250 tokens saída

Total estimado: 4.500 tokens entrada + 1.250 tokens saída
```

Para o preço público do Mistral Small em 13/09/2026 — US$ 0,15 por milhão de tokens de entrada e US$ 0,60 por milhão de tokens de saída — a conta ilustrativa é:

```text
(4.500 × 0,15 / 1.000.000) + (1.250 × 0,60 / 1.000.000)
= US$ 0,001425 por execução

100 execuções = US$ 0,1425
9.000 execuções no semestre (100/dia × 90 dias) = US$ 12,825
```

Esses valores são uma estimativa pelo preço de tabela e devem ser refeitos com os tokens registrados nos logs. A demonstração com `python -m src.demo` usa o modelo mock e custa US$ 0. Para testar a API sem cobrança, o grupo deve manter a conta no **Free mode**, que oferece uso incluído sujeito a limites; a disponibilidade precisa ser conferida no painel: [uso e limites da Mistral](https://docs.mistral.ai/admin/billing-usage/usage-limits) e [preços atuais](https://docs.mistral.ai/inference/pricing).

Em termos práticos, para 100 execuções por dia, o custo cresce rapidamente, por isso a arquitetura v1 precisa manter limites claros de tokens e de passos.

---

## 4. Verificação mínima

A disciplina pede que os grupos rodem testes pequenos nos modelos candidatos com o mesmo prompt. Abaixo está o formato mínimo de verificação que será usado no projeto.

### Casos de teste

1. Casamento, orçamento baixo, visual elegante, clima quente.
2. Entrevista, corte profissional, rápido, sem gastar muito.
3. Formatura, maquiagem natural, local de evento em clima quente.
4. Cliente muda de ideia no meio da conversa.
5. Cliente pede um serviço fora do escopo ou sem dados suficientes.

### Critério de avaliação

Para cada modelo, avaliar:

- interpretação correta da ocasião;
- qualidade da extração de parâmetros;
- clareza da resposta;
- capacidade de pedir apenas o que falta;
- capacidade de sugerir opções melhores do que uma busca manual;
- consistência da resposta com regras de negócio.

---

## 5. Decisão

### Modelo escolhido

O modelo escolhido para esta primeira versão é o `mistral-small-latest`.

### Por que ele

- atende ao escopo curto de interpretação e recomendação da prova de conceito;
- suporta tool calling no endpoint de Chat Completions;
- é indicado pela Mistral para projetos sensíveis a custo;
- pode ser usado no Free mode com limites de uso e sem cartão, conforme a documentação atual;
- funciona com a biblioteca `openai` exigida pela disciplina por meio da `LLM_BASE_URL`.

### Quando mudar de ideia

A decisão pode ser revisada se:

- outro candidato superar o Mistral Small nos cinco casos executados com o mesmo prompt;
- o modelo falhar em tool calling ou no contrato de saída em mais de um dos cinco casos;
- o Free mode não comportar o volume da disciplina;
- o custo ou a latência medidos deixarem de atender ao limite do projeto.

---

## 6. Conclusão

Para a etapa atual, o `mistral-small-latest` oferece o equilíbrio desejado entre capacidade, compatibilidade e custo. A execução mock permite desenvolver e demonstrar sem consumo de API; a chamada real fica restrita à verificação do modelo e ao uso incluído no Free mode.
