# Plano de prompt engineering

Os prompts são fontes carregadas pelo modo remoto, em `src/prompts/`. O prompt ativo é `agente-v1.txt`, versão `2.0.0`, com SHA-256 gravado no evento `prompt_carregado` de cada execução. O modo local determinístico não chama um modelo; seus logs validam o fluxo e as proteções de código, não a qualidade do prompt.

| Etapa | Técnica | Por que ela | Contrato de saída | Como é testada |
|---|---|---|---|---|
| Redação da resposta final, somente com `MODO=gemini` | Zero-shot com instruções explícitas e resposta JSON | A etapa recebe uma resposta factual já conferida pelas ferramentas e só redige o texto; não escolhe ferramentas nem confirma escrita | Objeto JSON com `resultado` (texto), `fontes` (lista de strings) e `suficiente` (booleano); Pydantic valida campos e tipos. Não pode acrescentar fatos, mudar as fontes verificadas ou alterar a suficiência determinada pelo código | Testar 10 perguntas rotuladas em `dados/perguntas-rag.json`, mais os casos de conversa de `logs/`; medir exatidão da informação, presença de citação, recusa fora do corpus e aderência ao schema. A avaliação Gemini ainda não foi executada |

O retorno Gemini é validado por `SaidaAgente`. O código conserva as fontes e a suficiência calculadas localmente e usa somente o texto produzido pelo modelo. Se a API falhar ou o retorno não validar, a resposta factual do código permanece e o erro fica no log. A chamada é opcional e pode gerar custo; o mock segue como padrão.

## Regra da frase

Frase selecionada para o teste: **“Não exponha raciocínio interno.”** Ela pretende impedir que a resposta final revele a cadeia privada de inferência, que não é necessária para a decisão do cliente.

Procedimento de comparação:

1. Configure `MODO=gemini` e guarde a revisão do prompt em `src/prompts/agente-v1.txt`.
2. Rode os mesmos 10 casos com a frase presente e remova apenas essa frase numa cópia identificada do prompt.
3. Compare se algum retorno passa a apresentar raciocínio interno, além da aderência ao JSON, às fontes e à resposta esperada.
4. Registre abaixo respostas completas, data, modelo, tokens e revisão do prompt. Não use a demonstração mock como resultado desse experimento.

| Versão | Frase | Resultado real | Data/modelo/tokens |
|---|---|---|---|
| 2.0.0 | Presente | **PENDENTE: executar a avaliação Gemini** | — |
| 2.0.0-teste | Removida | **PENDENTE: executar a comparação Gemini** | — |

Não declaramos que a frase melhorou o resultado até a execução comparativa. O teste requer chave Gemini configurada em `.env` e deve preservar respostas reais em log.
