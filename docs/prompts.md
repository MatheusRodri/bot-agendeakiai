# Plano de prompt engineering

Os prompts são fontes carregadas pelo modo remoto, em `src/prompts/`. O prompt ativo é `agente-v1.txt`, versão `2.0.0`, com SHA-256 gravado no evento `prompt_carregado` de cada execução. O modo local determinístico não chama um modelo; seus logs validam o fluxo e as proteções de código, não a qualidade do prompt.

| Etapa | Técnica | Por que ela | Contrato de saída | Como é testada |
|---|---|---|---|---|
| Redação da resposta final, somente com `MODO=gemini` | Zero-shot com instruções explícitas e resposta JSON | A etapa recebe uma resposta factual já conferida pelas ferramentas e só redige o texto; não escolhe ferramentas nem confirma escrita | Objeto JSON com `resultado` (texto), `fontes` (lista de strings) e `suficiente` (booleano); Pydantic valida campos e tipos. Não pode acrescentar fatos, mudar as fontes verificadas ou alterar a suficiência determinada pelo código | Comparar as mesmas 10 perguntas com a frase presente e removida; avaliar fidelidade factual, schema, clareza e eventual exposição de raciocínio. Registrar a nova execução em `dados/resultado-avaliacao-prompt-cancelamento-livre.json` |

O retorno Gemini é validado por `SaidaAgente`. O código conserva as fontes e a suficiência calculadas localmente e usa somente o texto produzido pelo modelo. Se a API falhar ou o retorno não validar, a resposta factual do código permanece e o erro fica no log. A chamada é opcional e pode gerar custo; o mock segue como padrão.

## Regra da frase

Frase selecionada para o teste: **“Não exponha raciocínio interno.”** Ela pretende impedir que a resposta final revele a cadeia privada de inferência, que não é necessária para a decisão do cliente. **Decisão do grupo em 2026-10-25: manter a frase no prompt ativo**, porque a resposta ao cliente não deve expor raciocínio interno. A comparação histórica não mostrou diferença entre as versões; isso não prova que a frase seja eficaz por si só. Qualquer exposição observada deve reprovar a resposta na revisão.

Procedimento de comparação:

1. Rode `python -m src.avaliar_prompt`; o script usa uma cópia em memória do prompt sem a frase e não altera o prompt ativo.
2. São 20 casos planejados, com pré-validação de US$ 0,01 por tentativa e teto local de US$ 0,20 para o custo registrado. Em caso de HTTP 503, HTTP 504 ou timeout de rede, o avaliador tenta o mesmo caso até três vezes, com pausas de 5 e 10 segundos.
3. Compare aderência ao JSON, preservação dos fatos e suficiência, clareza e eventual exposição de raciocínio. Não use a demonstração mock como resultado desse experimento.
4. O script salva respostas, hashes dos prompts, data, modelo, tokens e custo no novo arquivo JSON indicado. O resultado anterior permanece preservado separadamente.

| Versão avaliada com a antiga regra de 48 horas | Frase | Resultado histórico | Data/modelo/tokens |
|---|---|---|---|
| 2.0.0 | Presente | 10 de 10 casos concluídos | 2026-10-19 e 2026-10-24; Gemini 3.8 Flash; 3.747 tokens de entrada, 512 de resposta e 2.010 de raciocínio registrados; US$ 0,01226775 registrado |
| 2.0.0-teste | Removida | 10 de 10 casos concluídos | 2026-10-24 e 2026-10-25; Gemini 3.8 Flash; 3.677 tokens de entrada, 526 de resposta e 2.138 de raciocínio registrados; US$ 0,01274775 registrado |

O registro técnico histórico está em `dados/resultado-avaliacao-prompt.json`: 20 casos concluídos, status `concluido` e gasto registrado de US$ 0,0250155. As 20 saídas têm o formato JSON esperado e preservam as fontes e a suficiência informadas pelo código. Nenhuma expôs raciocínio interno. Na revisão do texto, as duas versões formularam a primeira resposta de modo ambíguo: “com até 48 horas” podia inverter a regra antiga de antecedência **mínima** de 48 horas. A versão sem a frase também acrescentou “sem custos adicionais”, informação que não constava no corpus daquela execução. Essa execução não demonstrou melhora com a frase; o campo `avaliacao_humana` permanece sem preenchimento nos 20 casos.

Em 2026-10-25, o grupo informou que o cancelamento passou a ser possível a qualquer momento, sem taxa ou custo adicional. O corpus e o gabarito foram atualizados; as respostas históricas sobre 24 ou 48 horas não representam a regra atual. A nova comparação está em andamento no arquivo `dados/resultado-avaliacao-prompt-cancelamento-livre.json`, sem sobrescrever o registro antigo.

| Versão com a regra atual | Frase | Resultado até 2026-10-25 | Uso e custo registrados |
|---|---|---|---|
| 2.0.0 | Presente | 10 de 10 casos concluídos | 3.775 tokens de entrada, 514 de resposta e 2.361 de raciocínio; US$ 0,0136125 |
| 2.0.0-teste | Removida | 1 de 10 casos concluído; pausa por HTTP 429 (limite diário) | 372 tokens de entrada, 50 de resposta e 156 de raciocínio; US$ 0,0010515 |

O arquivo novo registra **11 de 20 casos** e US$ 0,014664 de gasto conhecido. As 11 respostas salvas têm JSON válido e preservam fontes e suficiência esperadas. A revisão textual completa e a comparação entre versões aguardam os nove casos restantes. Chamadas que falharam antes de retornar uso podem elevar o custo real acima do valor registrado. A execução pode ser retomada com o mesmo comando após a renovação da cota diária.

Na revisão humana, ler cada `saida.resultado` junto de `pergunta`, `resposta_esperada` e do trecho vigente do corpus. Marcar `avaliacao_humana` como aprovado ou revisar, com uma observação quando houver erro de fato, condição inventada, texto confuso ou exposição de raciocínio interno. Fontes, suficiência e formato já são conferidos pelo avaliador; a leitura humana verifica o conteúdo da frase entregue ao cliente. O campo permanece vazio até alguém efetivamente revisar cada resposta.

Os primeiros 16 casos usaram limite de 400 tokens de saída; os quatro últimos usaram 800 após duas respostas que não puderam ser lidas como JSON. O limite inclui tokens de raciocínio, segundo a [documentação do Gemini](https://ai.google.dev/gemini-api/docs/thinking/). Essa mudança de configuração limita a comparação. O primeiro caso não registrou tokens de raciocínio, e tentativas sem resposta válida não tiveram uso registrado; portanto, o gasto informado pode subestimar o consumo real.
