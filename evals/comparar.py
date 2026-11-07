"""Compara duas rodadas: python -m evals.comparar evals/resultados/<A> evals/resultados/<B>"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ARQUIVO_JUIZ = Path(__file__).resolve().parent / "juiz_resultado.json"


def _ler(pasta: str) -> dict:
    return json.loads((Path(pasta) / "resultado.json").read_text(encoding="utf-8"))


def _por_classe(rodada: dict) -> dict[str, float]:
    acertos, totais = defaultdict(int), defaultdict(int)
    for caso in rodada["casos"]:
        totais[caso["classe"]] += 1
        acertos[caso["classe"]] += caso["passou"]
    return {classe: 100 * acertos[classe] / totais[classe] for classe in totais}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a, b = _ler(sys.argv[1]), _ler(sys.argv[2])
    origens = Counter(c["origem"] for c in b["casos"])
    print(f"DATASET v{b['meta']['dataset_versao']}   {b['meta']['casos']} casos   (producao {origens['producao']} · desenvolvimento {origens['desenvolvimento']} · sintetico {origens['sintetico']})")
    if ARQUIVO_JUIZ.exists():
        juiz = json.loads(ARQUIVO_JUIZ.read_text(encoding="utf-8"))
        print(f"JUIZ rubrica v{juiz['rubrica_versao']}   concordância {juiz['concordancia_pct']}%   limiar {juiz['limiar_pct']}%")
    else:
        print("JUIZ rubrica: não validado (evals/juiz_resultado.json ausente)")
    print(f"\nversão A = {a['meta']['versao']}{' (sem controles)' if a['meta']['sem_controles'] else ''}   versão B = {b['meta']['versao']}{' (sem controles)' if b['meta']['sem_controles'] else ''}\n")
    ca, cb = _por_classe(a), _por_classe(b)
    print(f"{'classe':<16}{'versão A':>10}{'versão B':>10}{'delta':>8}")
    for classe in sorted(set(ca) | set(cb)):
        va, vb = ca.get(classe, 0), cb.get(classe, 0)
        print(f"{classe:<16}{va:>9.0f}%{vb:>9.0f}%{vb - va:>+8.0f}")
    ma = 100 * sum(c["passou"] for c in a["casos"]) / len(a["casos"])
    mb = 100 * sum(c["passou"] for c in b["casos"]) / len(b["casos"])
    print(f"{'MÉDIA':<16}{ma:>9.0f}%{mb:>9.0f}%{mb - ma:>+8.0f}")
    mudaram = [(x["id"], x["passou"], y["passou"]) for x, y in zip(a["casos"], b["casos"]) if x["passou"] != y["passou"]]
    if mudaram:
        print("\ncasos que mudaram:")
        for id_, antes, depois in mudaram:
            print(f"  {id_}: {'passou' if antes else 'falhou'} -> {'passou' if depois else 'falhou'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
