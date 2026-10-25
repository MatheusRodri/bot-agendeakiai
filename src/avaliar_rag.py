"""Confere a recuperação lexical das dez perguntas do corpus atual."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .recuperacao import buscar_regra, normalizar


ROOT = Path(__file__).resolve().parents[1]
PERGUNTAS = ROOT / "dados" / "perguntas-rag.json"
CORPUS_VIGENTE = ROOT / "dados" / "corpus" / "regras-vigentes.md"
RESULTADO = ROOT / "dados" / "resultado-avaliacao-rag-cancelamento-livre.json"


def main() -> int:
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    casos = []
    for indice, item in enumerate(perguntas, start=1):
        trechos = buscar_regra(item["pergunta"])
        primeiro = trechos[0] if trechos else None
        suficiente = bool(primeiro and int(primeiro["pontos"]) >= 2 and "alergia" not in normalizar(item["pergunta"]))
        alvo = item["alvo"]
        passou = (
            suficiente
            and primeiro is not None
            and primeiro["titulo"] == alvo
            and primeiro["fonte"] == "dados/corpus/regras-vigentes.md"
        ) if alvo else not suficiente
        casos.append({
            "indice": indice,
            "pergunta": item["pergunta"],
            "resposta_esperada": item["resposta"],
            "alvo": alvo,
            "primeiro_trecho": primeiro,
            "suficiente": suficiente,
            "passou": passou,
        })

    acertos = sum(caso["passou"] for caso in casos)
    resultado = {
        "executado_em": datetime.now(timezone.utc).isoformat(),
        "corpus_sha256": hashlib.sha256(CORPUS_VIGENTE.read_bytes()).hexdigest(),
        "perguntas_sha256": hashlib.sha256(PERGUNTAS.read_bytes()).hexdigest(),
        "acertos": acertos,
        "total": len(casos),
        "casos": casos,
    }
    RESULTADO.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RAG: {acertos}/{len(casos)} casos no alvo; resultado salvo em {RESULTADO.relative_to(ROOT)}.")
    for caso in casos:
        if not caso["passou"]:
            titulo = caso["primeiro_trecho"]["titulo"] if caso["primeiro_trecho"] else "nenhum"
            print(f"Caso {caso['indice']}: esperado={caso['alvo'] or 'recusa'}, obtido={titulo}, suficiente={caso['suficiente']}.")
    return 0 if acertos == len(casos) else 1


if __name__ == "__main__":
    raise SystemExit(main())
