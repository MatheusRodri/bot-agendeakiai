"""Mede a recuperação das dez perguntas avaliáveis do corpus."""

from _future_ import annotations

import json
from pathlib import Path

from .recuperacao import buscar_regra


ROOT = Path(_file_).resolve().parents[1]
ESPERADOS = [
    "Cancelamento", "Cancelamento", "Remarcação", "Exceção por cancelamento do salão",
    "Exceção por doença no dia", None, "Exceção por cancelamento do salão",
    "Remarcação", "Cancelamento", None,
]


def main() -> int:
    perguntas = json.loads((ROOT / "dados" / "perguntas-rag.json").read_text(encoding="utf-8"))
    resultados = []
    for pergunta, esperado in zip(perguntas, ESPERADOS):
        trechos = buscar_regra(pergunta["pergunta"])
        primeiro = trechos[0] if trechos else None
        if esperado is None:
            passou = primeiro is None or int(primeiro["pontos"]) < 2
        else:
            passou = bool(primeiro and primeiro["titulo"] == esperado and primeiro["fonte"].endswith("regras-vigentes.md"))
        resultados.append({"pergunta": pergunta["pergunta"], "esperado": esperado or "recusa/sem suporte suficiente", "primeiro_trecho": primeiro, "passou": passou})
    destino = ROOT / "dados" / "resultado-avaliacao-rag.json"
    destino.write_text(json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(item["passou"] for item in resultados)
    print(f"Avaliação lexical: {total}/{len(resultados)} perguntas no alvo. Resultado salvo em dados/resultado-avaliacao-rag.json")
    for indice, item in enumerate(resultados, start=1):
        print(f"{indice}. {'PASSOU' if item['passou'] else 'FALHOU'} — {item['pergunta']}")
    return 0 if total == len(resultados) else 1


if _name_ == "_main_":
    raise SystemExit(main())
