"""Métricas sobre os traces das rodadas (§4.3) e o SLI do SLO de qualidade (§4.4).

Uso: python -m evals.metricas            (lê evals/resultados/*/traces.jsonl)
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "resultados"
SLO_ALVO = 90.0
# Término "bom": o agente concluiu o que lhe cabia. Parar para o humano não é término (não entra como válido).
TERMINOS_BONS = {"resposta_final", "agendamento_confirmado", "aprovacao_rejeitada"}


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(p / 100 * len(ordenados)) - 1)]


def carregar_spans() -> list[dict]:
    spans = []
    for arquivo in sorted(PASTA.glob("*/traces.jsonl")):
        spans += [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha.strip()]
    return spans


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    spans = carregar_spans()
    por_trace = defaultdict(list)
    for s in spans:
        por_trace[s["trace_id"]].append(s)

    versoes = defaultdict(lambda: {"exec": [], "lat": [], "custo": [], "motivos": Counter(), "ferr": Counter(), "ferr_erro": Counter(), "bons": 0, "validas": 0})
    for filhos in por_trace.values():
        raiz = next((s for s in filhos if s["nome"].startswith("invoke_agent")), None)
        if not raiz:
            continue
        v = versoes[raiz["atributos"]["sistema.versao"]]
        motivo = raiz["atributos"]["motivo_termino"]
        v["exec"].append(raiz)
        v["lat"].append(raiz["duracao_ms"])
        v["motivos"][motivo] += 1
        v["custo"].append(sum(s["atributos"].get("custo_usd", 0.0) for s in filhos if s["nome"].startswith("chat")))
        falhou_ferramenta = False
        for s in filhos:
            if s["nome"].startswith("execute_tool"):
                nome = s["atributos"]["gen_ai.tool.name"]
                v["ferr"][nome] += 1
                if not s["atributos"].get("ferramenta.ok", True):
                    v["ferr_erro"][nome] += 1
                    falhou_ferramenta = True
        if motivo != "aguardando_humano":
            v["validas"] += 1
            v["bons"] += motivo in TERMINOS_BONS and not falhou_ferramenta

    saida = ["# Métricas por versão do sistema", "", f"Fonte: {len(por_trace)} traces em `evals/resultados/*/traces.jsonl`. Cada `invoke_agent` é uma execução; uma retomada após aprovação humana é uma segunda execução.", ""]
    saida += ["| versão | execuções | latência p50 (ms) | latência p95 (ms) | custo médio (US$) |", "|---|---|---|---|---|"]
    for ver, v in sorted(versoes.items()):
        saida.append(f"| {ver} | {len(v['exec'])} | {percentil(v['lat'], 50):.1f} | {percentil(v['lat'], 95):.1f} | {sum(v['custo']) / len(v['custo']):.4f} |")
    saida += ["", "## Motivos de término", "", "| versão | motivo | n | % |", "|---|---|---|---|"]
    for ver, v in sorted(versoes.items()):
        for motivo, n in v["motivos"].most_common():
            saida.append(f"| {ver} | {motivo} | {n} | {100 * n / len(v['exec']):.0f}% |")
    saida += ["", "## Taxa de erro por ferramenta", "", "| versão | ferramenta | chamadas | erros | taxa |", "|---|---|---|---|---|"]
    for ver, v in sorted(versoes.items()):
        for nome, n in sorted(v["ferr"].items()):
            erros = v["ferr_erro"][nome]
            saida.append(f"| {ver} | {nome} | {n} | {erros} | {100 * erros / n:.1f}% |")
    saida += ["", "## SLI de qualidade", "", "SLI = execuções com término em {resposta_final, agendamento_confirmado, aprovacao_rejeitada} **e** nenhuma ferramenta com erro ÷ execuções que terminaram (exclui `aguardando_humano`).", "", f"| versão | bons | válidas | SLI | alvo | orçamento de erro consumido |", "|---|---|---|---|---|---|"]
    for ver, v in sorted(versoes.items()):
        sli = 100 * v["bons"] / v["validas"]
        orcamento = 100 - SLO_ALVO
        consumido = (100 - sli) / orcamento * 100
        estado = "VIOLADO" if sli < SLO_ALVO else "cumprido"
        saida.append(f"| {ver} | {v['bons']} | {v['validas']} | {sli:.1f}% ({estado}) | ≥{SLO_ALVO:.0f}% | {consumido:.0f}% |")
    texto = "\n".join(saida) + "\n"
    (PASTA / "metricas.md").write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
