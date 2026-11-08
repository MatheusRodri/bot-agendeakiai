# Modelo — AgendeAkiAI

## Decisão

O modo padrão é mock determinístico e custa US$ 0. Gemini 3.8 Flash (`gemini-3.8-flash`) é uma opção para redigir a resposta final, acionada por `MODO=gemini`; não escolhe ferramentas, filtros, regras ou autorização. O código verifica as fontes e a suficiência antes da redação. Essa escolha mantém o custo fora do caminho padrão e dá um local claro para avaliar a qualidade de linguagem natural.

O projeto usa o SDK oficial `google-genai`. A chave é lida de `GEMINI_API_KEY` no `.env`, ignorado pelo Git. A avaliação Gemini concluiu 20 casos com a antiga regra de cancelamento: dez com a frase selecionada do prompt e dez sem ela. O resultado histórico não demonstrou melhora com a frase. Com a regra atual, 12 de 20 casos estão salvos; a comparação foi pausada pelo limite diário de requisições. Veja `docs/prompts.md`.

## Adequação e limites

| Eixo | Decisão atual |
|---|---|
| Interpretação de filtros | Código PT-BR simples identifica serviço, bairro e orçamento. Não foi delegado ao modelo |
| Recuperação de fatos | API mock estruturada para opções e busca lexical em Markdown para regras |
| Saída remota | Zero-shot; JSON com `resultado`, `fontes`, `suficiente`, validado por Pydantic e schema de resposta do Gemini |
| Segurança | O modelo recebe a resposta já verificada; código conserva as fontes e suficiência originais |
| Latência e tokens | Uma chamada final com timeout de 120 s e no máximo 800 tokens de saída, incluindo raciocínio; uso fica registrado no evento de modelo |
| Custo | Zero no mock; modo remoto recusa a chamada se o teto conservador por bytes exceder 4.000 tokens estimados ou US$ 0,01. As taxas por milhão devem vir da [página oficial de preços](https://ai.google.dev/gemini-api/docs/pricing); o custo real fica registrado pelo uso reportado pela API |

O modo remoto não deve ser tratado como garantia de correção: a validação Pydantic confere formato e tipos, não a verdade semântica do texto. Respostas de regras devem ser comparadas com o corpus e os logs.

## Escopo e custo consultado

A comparação prática com outros modelos não foi feita. Os planos gratuitos dos demais provedores têm limite zero ou muito baixo, e o grupo não tem orçamento para pagar vários provedores apenas para comparar. O Gemini foi o único que permitiu rodar as avaliações (20 casos de prompt, juiz, suíte) dentro do teto de US$ 0,01 por execução. Esta decisão não afirma que ele seja superior a outros modelos; afirma que foi o único viável para o grupo. É um desvio assumido em relação à Parte 1 (§3, três candidatos). A comparação histórica de duas versões do prompt concluiu 20 casos antes da mudança da regra de cancelamento; a nova comparação está parcial, com 12 casos concluídos.

Na tabela oficial consultada em 18/10/2026, o preço do plano pago do Gemini 3.8 Flash é:

| Período | Entrada por 1 milhão de tokens | Saída por 1 milhão de tokens |
|---|---:|---:|
| Até 31/12/2026 | US$ 0,75 | US$ 3,75 |
| A partir de 01/01/2027 | US$ 1,50 | US$ 7,50 |

O preço inclui tokens de pensamento na saída. A conta por execução depende dos tokens efetivamente consumidos; quando o modo Gemini for executado, o código registra o uso informado pela API. Fonte: [preços oficiais da API Gemini](https://ai.google.dev/gemini-api/docs/pricing).

O modo mock mede somente fluxo e segurança do código, não a qualidade do modelo. A avaliação do prompt usou as perguntas em `dados/perguntas-rag.json` e registrou prompt e hash, texto, fontes, suficiência, tokens e custo. Não mediu latência nem incluiu uma avaliação humana preenchida.

## Biblioteca

O enunciado sugere a biblioteca `openai` com `base_url`. O grupo usa o SDK oficial `google-genai` (versão fixada no `requirements.txt`), com autorização do professor para usar outros modelos. Trocar o modelo continua sendo trocar variáveis de ambiente (`LLM_MODELO`, `GEMINI_API_KEY`); trocar de provedor exigiria reescrever apenas `src/modelo.py`.

## Quando rever a decisão

Reavaliar se algum provedor oferecer cota gratuita suficiente para repetir os cinco casos (refazer então a comparação), ou se as respostas Gemini mudarem fatos/fontes, falharem o contrato, trouxerem texto confuso ou excederem custo e latência aceitáveis. O modo mock continua adequado para testar gates e integração local independentemente da qualidade probabilística.


## Termos do provedor

**Fonte:** Termos Adicionais da API Gemini, <https://ai.google.dev/gemini-api/terms> (redireciona para <https://aistudio.google.com/docs/terms>). **Consultado em:** 2026-11-08, em português, com os trechos relevantes transcritos abaixo (omiti os parágrafos sobre licença e ajuste de modelos; corrigi só um espaço no link do Adendo de Tratamento de Dados).

**Modelo usado:** Gemini 3.8 Flash (`gemini-3.8-flash`). **Plano:** cota não paga (gratuita). O grupo confirmou em 2026-11-08, por Matheus Rodrigues, que o projeto da chave não tem faturamento (Cloud Billing) ativo; vale, portanto, o trecho de Serviços Não Pagos.

### Serviços Não Pagos (o que vale para a chave do grupo)

> Quando você usa Serviços Não Pagos, incluindo, por exemplo, o Google AI Studio e a cota não paga na API Gemini, o Google usa o conteúdo que você envia aos Serviços e qualquer resposta gerada para fornecer, aprimorar e desenvolver produtos, serviços e tecnologias de aprendizado de máquina, inclusive recursos, produtos e serviços corporativos do Google, de acordo com nossa Política de Privacidade.
> Para fins de qualidade e aprimoramento dos nossos produtos, revisores humanos podem ler, fazer anotações e tratar suas entradas e saídas das APIs. O Google toma medidas para proteger sua privacidade como parte desse processo. Isso inclui desassociar esses dados da sua Conta do Google, chave de API e projeto do Cloud antes que sejam vistos ou anotados por revisores. Não envie informações sensíveis, confidenciais ou pessoais para os Serviços Não Pagos.

> Se você estiver no Espaço Econômico Europeu, na Suíça ou no Reino Unido, os termos de "Como o Google usa seus dados" em "

### Serviços Pagos (para comparação)

> Ao ativar uma conta do Cloud Billing, todo uso da API Gemini e do Google AI Studio é um "Serviço Pago" com relação a como o Google usa seus dados, mesmo ao usar Serviços oferecidos sem custo financeiro, como o Google AI Studio e a cota não paga da API Gemini.

> Quando você usa os Serviços Pagos, incluindo, por exemplo, a cota paga da API Gemini, o Google não usa seus comandos (incluindo instruções do sistema, conteúdo armazenado em cache e arquivos como imagens, vídeos ou documentos associados) ou respostas para aperfeiçoar os produtos. Seus comandos e respostas serão tratados de acordo com o [Adendo de Tratamento de Dados para produtos em que o Google é um operador de dados](https://business.safety.google/processorterms/). Para Serviços Pagos, o Google armazena comandos e respostas por um período limitado, exclusivamente com o propósito de detectar e prevenir violações da Política de Uso Proibido para manter a segurança dos Serviços e qualquer exigência legal ou divulgações regulatórias. Esses dados podem ser armazenados temporariamente ou em cache em qualquer país em que o Google ou seus agentes tenham instalações.

### O que isso significa para o AgendeAkiAI

| Tema | Conclusão | Evidência |
|---|---|---|
| Treino e melhoria de produtos | Na cota não paga, o Google usa o que o sistema envia e as respostas. Só dados fictícios podem ser enviados. | trecho acima, "Como o Google usa seus dados" |
| Revisão humana | Na cota não paga, revisores podem ler entradas e saídas, desassociadas da conta. | idem |
| Aviso do próprio provedor | "Não envie informações sensíveis, confidenciais ou pessoais para os Serviços Não Pagos." O sistema só envia texto fictício (`dados/`). | idem |
| Retenção | Para Serviços Não Pagos, os termos **não informam prazo**. Para Pagos, "período limitado", só para detectar violações. | trechos acima |
| Região | Os termos **não garantem região**: dados "podem ser armazenados temporariamente ou em cache em qualquer país em que o Google ou seus agentes tenham instalações". | trecho de Serviços Pagos |
| Exceção EEE, Suíça e Reino Unido | Nesses locais os termos de Serviços Pagos valem também para a cota não paga. | trecho do EEE |

**Limite desta seção:** é a leitura dos termos de 2026-11-08, não uma auditoria da configuração da conta. Eles podem mudar; para dado real, a conclusão precisa ser refeita com o plano pago e a decisão sobre região (**LACUNA**, `docs/model-card.md`).
