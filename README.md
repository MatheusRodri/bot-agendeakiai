# AgendeAkiAI

## Visão geral

AgendeAkiAI é uma prova de conceito para descobrir e agendar serviços de beleza a partir de texto livre. O fluxo pode consultar o catálogo mock ou, em modo somente leitura, o backend do AgendeAki. Também busca regras em documentos Markdown e responde com um objeto Pydantic.

Os dados, salões, preços, horários e exceções são simulados. O modo padrão é local e não usa uma API de modelo.

## Rodar do zero

Requer Python 3.11 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Execute a demonstração e confira os logs:

```bash
python -m src.demo
python -m src.verificar
python conferir_grafo.py
python -m src.verificar_checkpoint
```

A demonstração inicia a API mock em `127.0.0.1:8765` e grava nove cenários em `logs/`. Ela também gera um cenário adicional de aprovação expirada. Os exemplos guardam o hash do código executado e a revisão base; como logs de um diretório de trabalho ainda não comprometido não podem apontar para um commit que contenha as alterações, atualize esse vínculo depois do primeiro commit da implementação.

## Como usar

Suba a API mock em um terminal:

```bash
python -m src.mock_api
```

Em outro terminal, inicie uma busca. O primeiro comando não agenda; ele responde com serviço, salão, profissional, horário, preço e `conversa_id`:

```bash
python -m src.main --cliente-id cliente-001 --conversa-id conversa-123 \
  --message "Quero penteado clássico para casamento no Centro até R$ 150. Confirmo."
```

Para um pedido de agendamento, o grafo pausa e mostra os dados exatos da reserva. Retome a mesma conversa após a decisão humana:

```bash
python -m src.main --cliente-id cliente-001 --conversa-id conversa-123 \
  --message "Quero penteado clássico para casamento no Centro até R$ 150. Confirmo."
python -m src.main --cliente-id cliente-001 --conversa-id conversa-123 --retomar aprovar
```

Use `--retomar rejeitar` para recusar ou `--editar-opcao-id opc-005` para trocar para uma opção que já apareceu na consulta. A aprovação dura 15 minutos. O `thread_id` é o identificador da conversa e o checkpoint fica em `dados/checkpoints.sqlite`.

O contrato completo, com entradas, saídas e exemplos copiados dos logs, está em [docs/io.md](docs/io.md).

### Consultar o backend real (somente leitura)

Copie `.env.example` para `.env` e preencha `API_BASE_URL`, `CLIENTE_EMAIL`, `CLIENTE_SENHA`, `LATITUDE` e `LONGITUDE`. `DATA_BUSCA` é opcional; sem ela, o terminal solicitará a data. O arquivo `.env` já está ignorado pelo Git.

Com o backend do AgendeAki em execução, inicie uma consulta assim:

```bash
python -m src.main \
  --backend agendeaki \
  --raio-km 5 \
  --conversa-id consulta-real-01 \
  --message "Quero maquiagem natural em Moema até R$ 150."
```

Se alguma coordenada ou credencial não estiver no `.env`, o terminal solicitará o valor; a senha digitada no terminal não aparece na tela. A senha e o token ficam em memória durante a execução, e a sessão é encerrada ao terminar. A execução real não grava memória nem checkpoint local e não cria agendamentos. Se a API estiver hospedada fora da máquina local, use uma URL `https://`. O modo consulta salões próximos, serviços, preços e horários para a data indicada, que deve estar entre hoje e os próximos 60 dias. Preferências de ocasião e estilo não existem como campos estruturados no backend atual. Aprovação e gravação de agendamento permanecem desabilitadas.

`MODO=mock` mantém desligada a chamada opcional ao Gemini. `--backend agendeaki` seleciona a fonte de dados real; `--api-base-url`, `--latitude`, `--longitude`, `--raio-km` e `--data` podem substituir os valores do `.env` para uma execução específica.

## Modo Gemini opcional

Copie `.env.example` para `.env`, preencha `GEMINI_API_KEY`, configure `LLM_MODELO` (por padrão, `gemini-3.8-flash`) e as taxas atuais de entrada/saída por milhão de tokens, e ajuste `MODO=gemini`. Há um limite local de US$ 0,01 e 4.000 tokens estimados por execução remota. A chamada opcional redige a resposta final com base na resposta verificada pelo código; a ferramenta de escrita continua protegida pela aprovação humana. A demonstração padrão não avalia o comportamento do modelo nem consome API.

## Remover dados locais

O comando a seguir remove preferências, episódios, checkpoints e logs do cliente indicado:

```bash
python -m src.esquecer --cliente-id cliente-001 --confirmar
```

Use somente com os identificadores simulados desta prova de conceito.

## Estrutura

- `src/grafo.py`: estado, nós, rotas, pausa humana e checkpointer SQLite;
- `src/mock_api.py` e `src/tools.py`: API mock e ferramentas locais;
- `src/agendeaki_api.py`: consultas somente de leitura ao backend real do AgendeAki;
- `src/recuperacao.py`: busca textual nas regras Markdown vigentes;
- `src/memoria.py` e `src/esquecer.py`: memória JSON e remoção local;
- `src/prompts/`: prompt carregado pelo modo Gemini opcional;
- `dados/`: catálogo, corpus, perguntas de avaliação e memória local ignorada pelo Git;
- `logs/`: execuções reproduzíveis da demonstração;
- `docs/`: case, arquitetura, decisões de projeto e evidências.

## Grupo

- Emily Oliveira
- Felipe Macena
- Matheus Rodrigues
