# Base de conhecimento v1 — AgendeAkiAI

## 1. Informação especializada necessária

O AgendeAkiAI precisa de dois tipos de conhecimento que não devem ser respondidos apenas pela memória de um modelo: regras de agendamento e critérios de recomendação por ocasião.

| Informação | Por que vem de fora do modelo | Uso pelo agente |
|---|---|---|
| Política de agendamento, remarcação, cancelamento, atraso e ausência | É específica da plataforma e pode mudar quando a operação alterar uma regra. | Responder dúvidas como “posso cancelar?” e impedir uma orientação incompatível com a política atual. |
| Guia de recomendação por ocasião | É uma curadoria específica do AgendeAkiAI: associações desejadas entre ocasião, estilo, clima e serviço. | Justificar recomendações de penteado, maquiagem e corte sem inventar uma regra da plataforma. |

O modelo já sabe conversar em português, reconhecer termos gerais como casamento, formatura e entrevista e produzir uma explicação curta. Isso não será indexado. Também não será pedido ao RAG que informe preço, disponibilidade, bairro, profissional, histórico ou identificador do cliente: esses dados dependem do estado atual da plataforma e devem vir de consulta estruturada.

## 2. Fontes, formato e acesso

Nesta v1, as duas fontes são simuladas e estão no repositório. Isso permite validar a decisão de recuperação sem expor dados reais de clientes ou salões.

| Fonte | Local e formato | Dono e atualização | Acesso |
|---|---|---|---|
| Política de agendamento | `dados/conhecimento/politica-agendamento.md`, Markdown | Operação da plataforma; atualiza quando uma regra mudar. | O grupo controla o documento mock. |
| Guia de recomendação por ocasião | `dados/conhecimento/guia-recomendacao-eventos.md`, Markdown | Curadoria da plataforma; atualiza quando serviços ou critérios mudarem. | O grupo controla o documento mock. |

Não há PDF escaneado, OCR ou fonte externa nesta etapa. Na integração real, esses documentos deverão ser substituídos por políticas aprovadas pela operação e por critérios definidos em conjunto com os salões; a fonte só entra no índice depois de a plataforma ter acesso e uma pessoa responsável definida.

## 3. Escopo do índice e consultas estruturadas

Entram no índice somente os dois documentos de conhecimento: cerca de 10 seções úteis, resultando em aproximadamente 10 a 12 chunks. É uma escala pequena; na implementação futura, uma lista em memória com embeddings e busca por similaridade será suficiente. Não há necessidade de banco vetorial nesta v1.

Ficam fora do índice:

- catálogo de serviços, preço, bairro, profissional e horário;
- histórico do cliente;
- identificador do cliente e estado do agendamento;
- dados pessoais reais;
- mensagens completas de conversas anteriores.

Esses itens são dados estruturados e mutáveis. O agente os obtém pela API do AgendeAki, usando filtros exatos. Exemplos: orçamento máximo usa `preço <= orçamento`; bairro usa igualdade; disponibilidade usa consulta de agenda; o histórico usa o identificador do cliente. Busca semântica não substitui essas regras.

| Pergunta do cliente | Fonte correta |
|---|---|
| “Posso cancelar amanhã?” | Recuperação semântica na política, combinada com a data estruturada do agendamento. |
| “Qual penteado combina com casamento no calor?” | Recuperação semântica no guia, seguida de busca estruturada no catálogo. |
| “Quais horários há no Centro até R$ 150?” | Consulta estruturada na API, sem RAG. |
| “O que costumo escolher?” | Consulta estruturada ao histórico do cliente, sem RAG. |

## 4. Estratégia de chunking

Os dois documentos são Markdown e têm unidades naturais. O corte será por seção com o título herdado no início de cada chunk. Assim, um trecho como “Cancelamento” continua compreensível fora do documento original e preserva a regra de 48 horas.

| Documento | Unidade de corte | Metadados | Justificativa |
|---|---|---|---|
| Política de agendamento | Cada seção: confirmação, remarcação, cancelamento, atraso/ausência e limites do agente. | `fonte`, `tipo=politica`, `topico`, `versao`, `atualizado_em`. | Cada regra deve ser recuperada isoladamente e citada pelo tópico correto. |
| Guia de recomendação | Cada ocasião e a seção de regras gerais. | `fonte`, `tipo=guia`, `ocasiao`, `estilos`, `versao`, `atualizado_em`. | Uma ocasião forma uma unidade de decisão completa; os metadados permitem filtrar casamento, formatura, entrevista ou festa. |

Não será usado corte por número fixo de caracteres, porque as seções já são curtas e semanticamente completas. Se um documento futuro for texto corrido sem seções, o plano é usar chunks de aproximadamente 800 caracteres com 100 de sobreposição e incluir o título do documento em cada trecho.

Esta é uma v1 deliberadamente pequena: ela separa conhecimento de domínio, que pode ser recuperado, de dados operacionais, que devem ser consultados na API. A escolha será revista quando a plataforma tiver documentos reais e volume suficiente para justificar uma infraestrutura vetorial.

