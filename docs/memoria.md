# Memória e conversa

## Fronteiras

| Estrutura | Guarda | Vida útil | Não guarda |
|---|---|---|---|
| Checkpoint SQLite | Estado da conversa e aprovação interrompida para retomar o grafo | Entre processos, até remoção explícita | Preferências globais consolidadas como memória semântica |
| Memória JSON | Episódios curtos e preferências explicitamente declaradas | Entre execuções | Respostas inferidas como preferência ou regras do corpus |
| Corpus Markdown | Regras consultáveis, com status vigente/revogado | Versionado no repositório | Dados de conversa e escolhas pessoais |
| Log JSON | Evidência da execução demonstrativa | Arquivo em `logs/` | Segredos ou dados de clientes reais |

O checkpoint é endereçado por `conversa_id`/`thread_id` e fica em `dados/checkpoints.sqlite`. O JSON fica em `dados/memoria.json` (ignorado pelo Git). Não há decaimento automático porque o volume desta POC é pequeno; a remoção é explícita e cobre memória, checkpoints e logs.

## Política de escrita e recuperação

Ao concluir uma execução, `registrar` acrescenta no máximo um episódio, reduzido a 180 caracteres. A recuperação compara conjuntos de palavras por Jaccard simples e usa o episódio de maior similaridade se o índice for pelo menos `0.15`. Não há embedding, vetor ou garantia semântica; é uma heurística lexical para a amostra.

Preferência semântica só é escrita se o cliente usar linguagem explícita (por exemplo, “prefiro clássico” ou “gosto de natural”). A estrutura é chave/valor por cliente e guarda horário de atualização. Uma atualização posterior substitui o valor anterior. O catálogo remoto continua como fonte de verdade para preferência persistida na conta; a memória local funciona como personalização da POC.

O pedido atual prevalece sobre histórico e memória. A rotina de recomendação detecta quando existe um estilo explícito atual e não aplica o estilo guardado. A expressão `maquiagem natural` é tratada como nome de serviço, não como declaração de preferência.

## Conversa e limite de contexto

O campo `mensagens` recebe apenas a mensagem da execução atual; mensagens anteriores não são anexadas ao contexto enviado ao Gemini. O checkpoint SQLite preserva o estado necessário para retomar uma aprovação interrompida, não um histórico conversacional crescente. Assim, esta POC não enche a janela de contexto e não aplica truncamento ou resumo; nada é descartado da lista de mensagens porque ela contém somente a entrada atual. Se o produto passar a acumular turnos, será necessário definir retenção e descarte antes de ampliar o contexto. Ao fim da execução, sobrevive na memória de longo prazo no máximo um episódio de até 180 caracteres, além de uma preferência explicitamente declarada.

## Remoção

Execute `python -m src.esquecer --cliente-id cliente-001 --confirmar`. O código remove episódios e preferências do JSON, localiza checkpoints pelo `cliente_id` guardado no estado, apaga threads correspondentes e remove logs cujo campo de entrada referencia o cliente. A confirmação explícita evita executar a exclusão por engano.

`python -m src.verificar_memoria` cria estruturas temporárias identificadas por `verificacao-remocao-local`, remove-as e confere as três superfícies. A verificação não apaga dados de demonstração.

## Limites

A amostra tem identificadores simulados e fica em disco sem criptografia própria. Não guardar dados reais nesta prova de conceito. Em produção, aplicar política de retenção, controle de acesso, autenticação do cliente e remoção coordenada dos armazenamentos reais.
