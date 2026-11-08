# Recuperação de regras (RAG lexical)

## Corpus do case

O corpus versionado está em `dados/corpus/`. `regras-vigentes.md` informa que o cancelamento pode ocorrer a qualquer momento, sem taxa ou custo adicional, além de reunir a remarcação sem custo e duas exceções marcadas como simuladas. `regras-revogada.md` conserva os antigos prazos de 24 e 48 horas com `status: revogada`; o carregador exclui todo arquivo sem `status: vigente`.

As exceções são dados inventados para avaliar o comportamento da recuperação. Não resultam de entrevistas, clientes reais, contrato ou pesquisa com salões. `case.md` registra essa fronteira.

O grupo mantém os documentos simulados no repositório. Eles são revistos quando uma regra ou trecho de avaliação muda; não há calendário de atualização porque não representam regras oficiais de estabelecimentos.

## Estratégia de busca

`buscar_regra` lê cada arquivo Markdown ativo, separa os trechos por título `##`, normaliza acentos, remove palavras comuns e ordena todos os trechos pela contagem de palavras da consulta presentes no trecho. Não usa embeddings, corte em chunks, banco vetorial nem parâmetro `k`: o corpus tem quatro seções curtas e é lido por inteiro. O limiar de suficiência do agente é pelo menos duas palavras de conteúdo coincidentes, além da regra de domínio que a pergunta não esteja explicitamente fora da cobertura.

O contrato estruturado de `buscar_opcoes` consulta catálogo/agenda na API mock usando serviço, bairro e preço máximo. A decisão mistura, portanto, recuperação lexical de regras com busca estruturada de opções, sem fingir que catálogo é documento vetorial.

## Formas usadas

| Forma usada | Com o quê | O que ela responde no seu case |
|---|---|---|
| busca textual (lexical) | `src/recuperacao.py` sobre `dados/corpus/*.md`; sem embedding, sem banco vetorial | as perguntas de **regra**: cancelamento, remarcação, exceções (perguntas 1–10) |
| consulta estruturada | `buscar_opcoes` (API mock) sobre `dados/catalogo.json`, por serviço, bairro e teto de preço | as perguntas de **registro**: que opções existem, quanto custa, em que bairro (perguntas R1–R4) |

**Não usados:** busca vetorial (o corpus tem quatro seções curtas, lidas inteiras; não há ganho que justifique um índice) e grafo (não há relações a atravessar entre documentos). Por isso **não há corte nem `k`** neste sistema. A resposta à pergunta "o seu RAG é vetorial ou é banco de dados?" é: **os dois, sem vetor** — texto para a regra, consulta estruturada para o registro.

## Classificação das perguntas e integração ao fluxo

As dez perguntas de regra abaixo usam busca textual lexical; a 6 e a 10 passam pela busca, mas são recusadas por estarem fora do corpus. Como todas as dez saíram do mesmo índice, o conjunto foi ampliado com **quatro perguntas de registro** (R1–R4, `dados/perguntas-registro.json`), escritas a partir do que o cliente pergunta ao agendar, e que a busca textual não responde: a resposta é um registro do catálogo, e a forma adequada é a consulta estruturada. Nenhuma pergunta exige busca vetorial, grafo ou agregação.

`consultar_fontes` é uma **etapa fixa** depois do contexto (`src/grafo.py:131`): executa uma consulta por execução, `buscar_regra` para temas de regra ou `buscar_opcoes` para serviço. A escolha é defendida assim: a decisão de buscar é por palavras-chave em código, sem modelo no laço; "ferramenta do agente" só faria sentido se um modelo decidisse quando buscar, e hoje o modelo apenas redige o texto final. Entradas incompletas e fora do escopo terminam antes da busca. **Chamadas de recuperação por execução: 1** (ou 0 nas entradas que terminam antes). Na avaliação das dez perguntas de regra, houve dez buscas: oito tiveram suporte suficiente e **duas foram inúteis para responder** (atraso e alergia), e terminaram em recusa correta. O modo não decide dinamicamente se deve pesquisar; se o sistema ganhar um modelo no laço, rever esta escolha.

## Perguntas de avaliação

As dez perguntas e respostas esperadas estão em `dados/perguntas-rag.json`.

| # | Pergunta | Forma de recuperação | Alvo | Fonte/resultado esperado |
|---|---|---|---|---|
| 1 | Com quantas horas de antecedência posso cancelar? | busca textual | regra vigente | a qualquer momento, sem antecedência mínima |
| 2 | A regra de cancelamento é de 24 horas? | busca textual | regra revogada | negar o prazo de 24 h e recuperar a regra vigente |
| 3 | A remarcação tem custo? | busca textual | regra vigente | não tem custo na POC |
| 4 | O que acontece se o salão cancelar? | busca textual | exceção simulada | remarcação sem custo ou reembolso |
| 5 | Fiquei doente no dia, posso remarcar? | busca textual | exceção simulada | uma remarcação sem custo com operação |
| 6 | Qual é a regra para atraso? | busca textual; recusa por falta de suporte | sem resposta | recusar e encaminhar à operação |
| 7 | O salão devolve o valor se cancelar? | busca textual | exceção simulada | reembolso integral simulado |
| 8 | Posso remarcar sem pagar uma taxa? | busca textual | regra vigente | sem custo |
| 9 | Posso cancelar com menos de 48 horas de antecedência sem custo extra? | busca textual | regra revogada | sim; sem prazo mínimo nem custo adicional pelo cancelamento |
| 10 | Qual produto é seguro para minha alergia? | busca textual; recusa fora do corpus | fora do corpus | recusar sem recomendação de produto |

As respostas esperadas definem o gabarito. Em **2026-10-25**, `python -m src.avaliar_rag` marcou **10/10 no alvo lexical** com a regra atual; o resultado e os hashes do corpus e das perguntas estão em `dados/resultado-avaliacao-rag-cancelamento-livre.json`. Os casos 1, 2 e 9 recuperaram a seção vigente de cancelamento, que informa ausência de prazo mínimo e de custo adicional. Os casos 6 e 10 ficaram sem suporte suficiente. O registro em `dados/resultado-avaliacao-rag.json` é histórico: marcou 10/10 em 2026-10-04 com a regra antiga de 48 horas. A pergunta 10 também aparece como execução integral em `logs/05-fora-do-corpus.json`. Este teste mede a escolha do trecho e a suficiência lexical, não a qualidade da redação Gemini.

### Perguntas de registro (consulta estruturada)

| # | Pergunta | Forma | Registro que responde | Esperado |
|---|---|---|---|---|
| R1 | Quais opções de penteado existem no Centro até R$ 150? | consulta estruturada | `opc-001`, `opc-005` em `dados/catalogo.json` | as duas opções |
| R2 | Qual o preço da maquiagem natural no Centro? | consulta estruturada | `opc-002` (R$ 140) | uma opção |
| R3 | Existe corte em Moema até R$ 100? | consulta estruturada | `opc-003` (R$ 75) | uma opção |
| R4 | Tem penteado em Moema? | consulta estruturada | nenhum registro | lista vazia: o sistema diz que não há opção |

`python -m src.avaliar_registro` extrai os filtros do texto, consulta `buscar_opcoes` e compara com o esperado: **4/4 no alvo**, resultado em `dados/resultado-avaliacao-registro.json` (2026-11-08). Isso mede a extração de filtros e a consulta, não a redação.

## O documento revogado, no corpus de propósito

`python -m src.demo_revogado` copia o corpus para uma pasta temporária, troca `status: revogada` por `status: vigente` na cópia e repete duas perguntas (1 e 2). Resultado em 2026-11-08:

| Pergunta | Com a curadoria (`status: revogada` excluído) | Sem a curadoria |
|---|---|---|
| Com quantas horas de antecedência posso cancelar? | `regras-vigentes.md#Cancelamento` (3 pontos) | `regras-revogada.md#Cancelamento — versão antiga` (3 pontos) |
| A regra de cancelamento é de 24 horas? | `regras-vigentes.md#Cancelamento` (4 pontos) | `regras-revogada.md#Cancelamento — versão antiga` (4 pontos) |

O trecho revogado empata em pontos com o vigente e vence só pela ordem alfabética dos arquivos (`regras-revogada` vem antes de `regras-vigentes`): nenhuma técnica de recuperação sabe que ele não vale mais. **O achado é de curadoria:** o campo `status` e a revisão do corpus são a defesa, e o carregador que exclui o que não é vigente é o único controle. Se um documento for marcado como vigente por engano, o sistema responderá com o prazo antigo.

## Cegueiras e justificativa

Busca lexical falha com sinônimos sem palavras compartilhadas (“devolução” versus “reembolso”), erros de digitação, negação sutil e perguntas que combinam exceções. Um trecho com palavras comuns pode parecer relevante mesmo sem responder à pergunta; por isso há remoção de palavras comuns, limiar simples e um bloqueio explícito para alergias. A exceção de doença e de cancelamento pelo salão está marcada e é pequena o bastante para inspeção manual.

O corte escolhido é não cortar e ler os poucos documentos por inteiro. Em um corpus tão pequeno, segmentar ou ajustar `k` acrescentaria parâmetros sem reduzir contexto ou custo. Se o corpus crescer, medir precisão/recall em perguntas rotuladas antes de escolher chunk e corte.
