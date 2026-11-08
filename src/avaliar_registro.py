"""Confere as perguntas de registro: filtros extraídos do texto + consulta estruturada (buscar_opcoes).

Uso: python -m src.avaliar_registro   (usa a API mock em memória; não usa modelo nem rede externa)
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .grafo import _filtros
from .mock_api import create_server
from .tools import ApiTools


ROOT = Path(__file__).resolve().parents[1]
PERGUNTAS = ROOT / "dados" / "perguntas-registro.json"
RESULTADO = ROOT / "dados" / "resultado-avaliacao-registro.json"


def main() -> int:
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    servidor = create_server("127.0.0.1", 0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    ferramentas = ApiTools(f"http://127.0.0.1:{servidor.server_address[1]}", "token-mock")
    casos = []
    for indice, item in enumerate(perguntas, start=1):
        filtros = _filtros(item["pergunta"])
        busca = ferramentas.buscar_opcoes(**filtros, cliente_id="cliente-001")
        obtidas = sorted(o["opcaoId"] for o in busca.get("opcoes", [])) if busca.get("ok") else None
        passou = obtidas == sorted(item["esperado_opcoes"])
        casos.append({"indice": indice, "pergunta": item["pergunta"], "filtros": filtros, "esperado": item["esperado_opcoes"], "obtido": obtidas, "passou": passou})
    servidor.shutdown()
    acertos = sum(c["passou"] for c in casos)
    RESULTADO.write_text(json.dumps({"executado_em": datetime.now(timezone.utc).isoformat(), "acertos": acertos, "total": len(casos), "casos": casos}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"REGISTRO: {acertos}/{len(casos)} casos no alvo; resultado salvo em {RESULTADO.relative_to(ROOT)}.")
    for c in casos:
        if not c["passou"]:
            print(f"Caso {c['indice']}: esperado={c['esperado']}, obtido={c['obtido']}, filtros={c['filtros']}")
    return 0 if acertos == len(casos) else 1


if __name__ == "__main__":
    raise SystemExit(main())
