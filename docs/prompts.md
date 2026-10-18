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
2. O limite é de US$ 0,01 por chamada e US$ 0,20 no total para as 20 chamadas.
3. Compare aderência ao JSON, preservação dos fatos e suficiência, clareza e eventual exposição de raciocínio. Não use a demonstração mock como resultado desse experimento.
4. O script salva respostas, hashes dos prompts, data, modelo, tokens e custo no arquivo JSON indicado.

| Versão | Frase | Resultado real | Data/modelo/tokens |
|---|---|---|---|
| 2.0.0 | Presente | Bloqueada antes da primeira chamada pela pré-validação local; nenhuma resposta avaliada | 2026-10-18; Gemini 3.8 Flash; 0 tokens; US$ 0,00 |
| 2.0.0-teste | Removida | Bloqueada antes da primeira chamada pela pré-validação local; nenhuma resposta avaliada | 2026-10-18; Gemini 3.8 Flash; 0 tokens; US$ 0,00 |

O registro técnico está em `dados/resultado-avaliacao-prompt.json`: status `bloqueado_prevalidacao`, erro `ValueError`, zero chamadas e custo zero. O detalhe da configuração não foi exposto. A comparação continua pendente até a validação local permitir a chamada; não há evidência de que a frase melhore o resultado.
