# Plano de prompt engineering

Os prompts são fontes carregadas pelo modo remoto, em `src/prompts/`. O prompt ativo é `agente-v1.txt`, versão `2.0.0`, com SHA-256 gravado no evento `prompt_carregado` de cada execução. O modo local determinístico não chama um modelo; seus logs validam o fluxo e as proteções de código, não a qualidade do prompt.

| Etapa | Técnica | Por que ela | Contrato de saída | Como é testada |
|---|---|---|---|---|
| Redação da resposta final, somente com `MODO=gemini` | Zero-shot com instruções explícitas e resposta JSON | A etapa recebe uma resposta factual já conferida pelas ferramentas e só redige o texto; não escolhe ferramentas nem confirma escrita | Objeto JSON com `resultado` (texto), `fontes` (lista de strings) e `suficiente` (booleano); Pydantic valida campos e tipos. Não pode acrescentar fatos, mudar as fontes verificadas ou alterar a suficiência determinada pelo código | Comparar as mesmas 10 perguntas com a frase presente e removida; avaliar fidelidade factual, schema, clareza e eventual exposição de raciocínio. Registrar respostas e uso em `dados/resultado-avaliacao-prompt.json` |

O retorno Gemini é validado por `SaidaAgente`. O código conserva as fontes e a suficiência calculadas localmente e usa somente o texto produzido pelo modelo. Se a API falhar ou o retorno não validar, a resposta factual do código permanece e o erro fica no log. A chamada é opcional e pode gerar custo; o mock segue como padrão.

## Regra da frase

Frase selecionada para o teste: **“Não exponha raciocínio interno.”** Ela pretende impedir que a resposta final revele a cadeia privada de inferência, que não é necessária para a decisão do cliente.

Procedimento de comparação:

1. Rode `python -m src.avaliar_prompt`; o script usa uma cópia em memória do prompt sem a frase e não altera o prompt ativo.
2. São 20 casos planejados, com pré-validação de US$ 0,01 por tentativa e teto local de US$ 0,20 para o custo registrado. Em caso de HTTP 503, HTTP 504 ou timeout de rede, o avaliador tenta o mesmo caso até três vezes, com pausas de 5 e 10 segundos.
3. Compare aderência ao JSON, preservação dos fatos e suficiência, clareza e eventual exposição de raciocínio. Não use a demonstração mock como resultado desse experimento.
4. O script salva respostas, hashes dos prompts, data, modelo, tokens e custo no arquivo JSON indicado.

| Versão | Frase | Resultado real | Data/modelo/tokens |
|---|---|---|---|
| 2.0.0 | Presente | 10 de 10 casos concluídos | 2026-10-19 e 2026-10-24; Gemini 3.8 Flash; 3.747 tokens de entrada, 512 de resposta e 2.010 de raciocínio registrados; US$ 0,01226775 registrado |
| 2.0.0-teste | Removida | 7 de 10 casos concluídos; pausa por HTTP 429 (RPD) | 2026-10-24; Gemini 3.8 Flash; 2.582 tokens de entrada, 383 de resposta e 1.412 de raciocínio; US$ 0,00866775 registrado |

O registro técnico está em `dados/resultado-avaliacao-prompt.json`: 17 casos concluídos, gasto registrado de US$ 0,0209355 e status `falha_chamada` com HTTP 429 por limite diário. O próximo comando retoma no oitavo caso da versão sem a frase após a renovação da cota. As 17 saídas salvas são JSON válido e preservaram as fontes e a suficiência esperadas. Nenhuma expôs raciocínio interno. A revisão textual ainda é necessária: por exemplo, “com até 48 horas” pode inverter o sentido do prazo mínimo, e “sem custos adicionais” foi acrescentado à resposta sem base explícita naquele caso. Não há evidência suficiente para concluir que uma versão do prompt é melhor.

Os primeiros 16 casos usaram limite de 400 tokens de saída; o caso 17 usou 800 após duas respostas que não puderam ser lidas como JSON. O limite inclui tokens de raciocínio, segundo a [documentação do Gemini](https://ai.google.dev/gemini-api/docs/thinking/). Essa mudança de configuração limita a comparação dos casos posteriores. O primeiro caso não registrou tokens de raciocínio, e tentativas sem resposta válida não tiveram uso registrado; portanto, o gasto informado pode subestimar o consumo real.
