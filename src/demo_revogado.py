"""Experimento do documento revogado: o que a busca devolve SEM a curadoria (status: revogada)?

Copia o corpus para uma pasta temporária, troca `status: revogada` por `status: vigente` na cópia
e compara a resposta da busca com e sem essa curadoria. O corpus do repositório não é alterado.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import recuperacao


PERGUNTAS = ["Com quantas horas de antecedência posso cancelar?", "A regra de cancelamento é de 24 horas?"]


def _melhor(pergunta: str) -> str:
    trechos = recuperacao.buscar_regra(pergunta)
    return f'{trechos[0]["fonte"]}#{trechos[0]["titulo"]} ({trechos[0]["pontos"]} pts)' if trechos else "nenhum trecho"


def main() -> int:
    print("COM curadoria (corpus do repositório):")
    for pergunta in PERGUNTAS:
        print(f"  {pergunta} -> {_melhor(pergunta)}")
    original = recuperacao.CORPUS
    with tempfile.TemporaryDirectory(dir=recuperacao.ROOT / "dados") as pasta:
        copia = Path(pasta) / "corpus"
        shutil.copytree(original, copia)
        revogada = copia / "regras-revogada.md"
        revogada.write_text(revogada.read_text(encoding="utf-8").replace("status: revogada", "status: vigente"), encoding="utf-8")
        recuperacao.CORPUS = copia
        try:
            print("SEM curadoria (documento revogado marcado como vigente):")
            for pergunta in PERGUNTAS:
                print(f"  {pergunta} -> {_melhor(pergunta)}")
        finally:
            recuperacao.CORPUS = original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
