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
| 2.0.0 | Presente | 5 de 10 casos concluídos; pausa por HTTP 429, com RPD esgotado no AI Studio | 2026-10-19; Gemini 3.8 Flash; US$ 0,005013 registrado, com o primeiro caso sem contagem de tokens de raciocínio |
| 2.0.0-teste | Removida | Ainda não executada | — |

O registro técnico está em `dados/resultado-avaliacao-prompt.json`: cinco casos concluídos e status `falha_chamada` com HTTP 429. O usuário confirmou no AI Studio que o limite diário de requisições (RPD) foi esgotado. O próximo comando retoma no sexto caso após a renovação da cota. As cinco respostas preservaram os fatos, as fontes e a suficiência esperados, mas a comparação entre versões continua pendente. O custo do primeiro caso pode estar subestimado porque a versão usada naquela chamada não registrava tokens de raciocínio.
