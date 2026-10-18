# Recuperação de regras (RAG lexical)

## Corpus do case

O corpus versionado está em `dados/corpus/`. `regras-vigentes.md` reúne cancelamento de 48 horas, remarcação sem custo e duas exceções marcadas como simuladas. `regras-revogada.md` conserva a regra antiga de 24 horas com `status: revogada`; o carregador exclui todo arquivo sem `status: vigente`.

As exceções são dados inventados para avaliar o comportamento da recuperação. Não resultam de entrevistas, clientes reais, contrato ou pesquisa com salões. `case.md` registra essa fronteira.

## Estratégia de busca

`buscar_regra` lê cada arquivo Markdown ativo, separa os trechos por título `##`, normaliza acentos, remove palavras comuns e ordena todos os trechos pela contagem de palavras da consulta presentes no trecho. Não usa embeddings, corte em chunks, banco vetorial nem parâmetro `k`: o corpus tem quatro seções curtas e é lido por inteiro. O limiar de suficiência do agente é pelo menos duas palavras de conteúdo coincidentes, além da regra de domínio que a pergunta não esteja explicitamente fora da cobertura.

O contrato estruturado de `buscar_opcoes` consulta catálogo/agenda na API mock usando serviço, bairro e preço máximo. A decisão mistura, portanto, recuperação lexical de regras com busca estruturada de opções, sem fingir que catálogo é documento vetorial.

## Perguntas de avaliação

As dez perguntas e respostas esperadas estão em `dados/perguntas-rag.json`.

| # | Pergunta | Alvo | Fonte/resultado esperado |
|---|---|---|---|
| 1 | Com quantas horas de antecedência posso cancelar? | regra vigente | 48 horas |
| 2 | A regra de cancelamento é de 24 horas? | regra revogada | recuperar a vigente de 48 h e ignorar a revogada |
| 3 | A remarcação tem custo? | regra vigente | não tem custo na POC |
| 4 | O que acontece se o salão cancelar? | exceção simulada | remarcação sem custo ou reembolso |
| 5 | Fiquei doente no dia, posso remarcar? | exceção simulada | uma remarcação sem custo com operação |
| 6 | Qual é a regra para atraso? | sem resposta | recusar e encaminhar à operação |
| 7 | O salão devolve o valor se cancelar? | exceção simulada | reembolso integral simulado |
| 8 | Posso remarcar sem pagar uma taxa? | regra vigente | sem custo |
| 9 | Quantas horas antes devo cancelar a reserva? | regra vigente | 48 horas |
| 10 | Qual produto é seguro para minha alergia? | fora do corpus | recusar sem recomendação de produto |

As respostas esperadas definem o gabarito. A execução `python -m src.avaliar_rag`, em `2026-10-04`, marcou **10/10 no alvo lexical** e salvou os trechos efetivamente recuperados em `dados/resultado-avaliacao-rag.json`. A pergunta 10 também aparece como execução integral em `logs/05-fora-do-corpus.json`. Esse resultado mede correspondência do recuperador lexical ao gabarito, não a qualidade de um modelo gerador. A avaliação opcional de redação Gemini requer execução separada e não foi inventada.

## Cegueiras e justificativa

Busca lexical falha com sinônimos sem palavras compartilhadas (“devolução” versus “reembolso”), erros de digitação, negação sutil e perguntas que combinam exceções. Um trecho com palavras comuns pode parecer relevante mesmo sem responder à pergunta; por isso há remoção de palavras comuns, limiar simples e um bloqueio explícito para alergias. A exceção de doença e de cancelamento pelo salão está marcada e é pequena o bastante para inspeção manual.

O corte escolhido é não cortar e ler os poucos documentos por inteiro. Em um corpus tão pequeno, segmentar ou ajustar `k` acrescentaria parâmetros sem reduzir contexto ou custo. Se o corpus crescer, medir precisão/recall em perguntas rotuladas antes de escolher chunk e corte.
