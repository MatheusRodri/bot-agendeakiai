# Modelo — AgendeAkiAI

## Decisão

O modo padrão é mock determinístico e custa US$ 0. Gemini 3.8 Flash (`gemini-3.8-flash`) é uma opção para redigir a resposta final, acionada por `MODO=gemini`; não escolhe ferramentas, filtros, regras ou autorização. O código verifica as fontes e a suficiência antes da redação. Essa escolha mantém o custo fora do caminho padrão e dá um local claro para avaliar a qualidade de linguagem natural.

O projeto usa o SDK oficial `google-genai`. A chave é lida de `GEMINI_API_KEY` no `.env`, ignorado pelo Git. A avaliação Gemini tem cinco casos concluídos e está pausada pelo limite diário de requisições; ainda não há resultado comparativo de qualidade.

## Adequação e limites

| Eixo | Decisão atual |
|---|---|
| Interpretação de filtros | Código PT-BR simples identifica serviço, bairro e orçamento. Não foi delegado ao modelo |
| Recuperação de fatos | API mock estruturada para opções e busca lexical em Markdown para regras |
| Saída remota | Zero-shot; JSON com `resultado`, `fontes`, `suficiente`, validado por Pydantic e schema de resposta do Gemini |
| Segurança | O modelo recebe a resposta já verificada; código conserva as fontes e suficiência originais |
| Latência e tokens | Uma chamada final com timeout de 120 s e no máximo 400 tokens de saída; uso fica registrado no evento de modelo |
| Custo | Zero no mock; modo remoto recusa a chamada se o teto conservador por bytes exceder 4.000 tokens estimados ou US$ 0,01. As taxas por milhão devem vir da [página oficial de preços](https://ai.google.dev/gemini-api/docs/pricing); o custo real fica registrado pelo uso reportado pela API |

O modo remoto não deve ser tratado como garantia de correção: a validação Pydantic confere formato e tipos, não a verdade semântica do texto. Respostas de regras devem ser comparadas com o corpus e os logs.

## Escopo e custo consultado

A comparação prática de três modelos em cinco casos foi deixada fora do escopo por decisão do grupo. O projeto adotará o Gemini 3.8 Flash; esta decisão não afirma que ele tenha sido comparado ou que seja superior a outros modelos. A avaliação de qualidade do Gemini está parcial, com cinco casos concluídos.

Na tabela oficial consultada em 18/10/2026, o preço do plano pago do Gemini 3.8 Flash é:

| Período | Entrada por 1 milhão de tokens | Saída por 1 milhão de tokens |
|---|---:|---:|
| Até 31/12/2026 | US$ 0,75 | US$ 3,75 |
| A partir de 01/01/2027 | US$ 1,50 | US$ 7,50 |

O preço inclui tokens de pensamento na saída. A conta por execução depende dos tokens efetivamente consumidos; quando o modo Gemini for executado, o código registra o uso informado pela API. Fonte: [preços oficiais da API Gemini](https://ai.google.dev/gemini-api/docs/pricing).

O modo mock mede somente fluxo e segurança do código, não a qualidade do modelo. Uma avaliação do Gemini, se realizada depois, pode usar as perguntas em `dados/perguntas-rag.json` e os casos de conversa da demonstração, registrando prompt e hash, texto, fontes, suficiência, tokens, latência e acerto contra o gabarito.

## Quando rever a decisão

Reavaliar se as respostas Gemini mudarem fatos/fontes, falharem o contrato, trouxerem texto confuso ou excederem custo e latência aceitáveis. O modo mock continua adequado para testar gates e integração local independentemente da qualidade probabilística.
