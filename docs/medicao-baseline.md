# Protocolo de medição da linha de base

Uma comparação válida entre os dois sistemas ainda não foi realizada. Os tempos registrados foram medidos manualmente em testes feitos pelo grupo: o fluxo tradicional foi observado no frontend do `monorepo-agendeaki`, enquanto o agente foi executado em `MODO=mock`, usando a API local simulada e o catálogo da POC. São observações reais desses testes, não dados simulados; porém, não medem o agente integrado ao backend do AgendeAki e usam interfaces diferentes. Portanto, não devem ser apresentados como resultado comparativo nem como medida de desempenho do Gemini.

## Procedimento

1. Abrir o frontend do `monorepo-agendeaki` em uma sessão limpa.
2. Entregar um dos dez cenários abaixo à pessoa que fará o teste.
3. Cronometrar do primeiro filtro até a seleção de uma opção; registrar também telas visitadas e filtros preenchidos.
4. Para uma consulta com dados reais, repetir o cenário na CLI do agente com `--backend agendeaki`, usando a mesma área e data. A CLI pede login e coordenadas; não confirmar nem gravar reserva.
5. O agente ainda usa a CLI, não uma interface de chat. Registre seu tempo como latência técnica e não o compare como esforço de uso com o frontend. Uma comparação de experiência exige interfaces equivalentes.

| Caso | Cenário | Tempo tradicional (s) | Telas/filtros tradicionais | Tempo agente (s) | Trocas com agente | Concluiu? |
|---|---|---:|---:|---:|---:|---|
| 01 | Penteado clássico, casamento, Centro, até R$ 150 | 20 | — | 1 | 1 | sim |
| 02 | Maquiagem natural, formatura, até R$ 150 | 20 | — | 1 | 1 | sim |
| 03 | Corte profissional, entrevista, Moema, até R$ 100 | 20 | — | — | — | — |
| 04 | Comparar opções sem reservar | — | — | — | — | — |
| 05 | Preferência atual contradiz histórico | N/A | N/A — o frontend não usa histórico para priorizar preferências | — | — | — |
| 06 | Serviço sem opção no orçamento | — | — | — | — | — |
| 07 | Bairro sem opção para o serviço | N/A | N/A — o frontend não oferece busca por bairro | — | — | — |
| 08 | Pedido incompleto, precisa informar orçamento | N/A | N/A — o frontend não recebe pedidos em texto livre | — | — | — |
| 09 | Cliente sem histórico | N/A | N/A — o frontend não usa histórico para personalizar a busca | — | — | — |
| 10 | Pedido fora do escopo de beleza | N/A | N/A — o frontend não recebe pedidos em texto livre | — | — | — |

## Cálculo

Para tempo de experiência, use `(mediana tradicional − mediana agente) / mediana tradicional × 100` apenas quando os dois fluxos tiverem interfaces e cenários comparáveis. Os tempos da CLI podem ser reportados separadamente como latência técnica. Exclua `N/A` e valores não medidos.

Para esforço, informe separadamente a quantidade de telas/filtros tradicionais e de trocas com o agente; essas medidas têm unidades diferentes. O resultado só deve entrar no `case.md` depois da coleta dos cenários comparáveis.
