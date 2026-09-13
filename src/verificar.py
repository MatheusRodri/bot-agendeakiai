"""Confere os quatro cenários rotulados da primeira entrega.

Uso:
    python -m src.demo
    python -m src.verificar
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "dados" / "casos-avaliacao.json"
LOGS_DIR = ROOT / "logs"


def possui_escrita(log: dict) -> bool:
    return any(
        passo.get("tipo") == "ferramenta"
        and passo.get("ferramenta") == "confirmar_agendamento"
        and passo.get("resultado", {}).get("ok") is True
        for passo in log.get("trajetoria", [])
    )


def codigos_de_erro(log: dict) -> set[str]:
    return {
        passo.get("resultado", {}).get("erro", {}).get("codigo")
        for passo in log.get("trajetoria", [])
        if passo.get("tipo") == "ferramenta" and passo.get("erro")
    }


def verificar_caso(caso: dict) -> list[str]:
    arquivo = LOGS_DIR / caso["arquivo_log"]
    if not arquivo.exists():
        return [f"log ausente: {arquivo.relative_to(ROOT)}"]

    log = json.loads(arquivo.read_text(encoding="utf-8"))
    resposta = log.get("estado_final", {}).get("resposta", "")
    problemas: list[str] = []
    if possui_escrita(log) != caso["espera_escrita"]:
        problemas.append(f"escrita esperada={caso['espera_escrita']}, encontrada={possui_escrita(log)}")
    if caso["trecho_resposta"].casefold() not in resposta.casefold():
        problemas.append(f"resposta não contém: {caso['trecho_resposta']!r}")
    if caso["espera_erro"]:
        codigo = caso["codigo_erro"]
        if codigo not in codigos_de_erro(log):
            problemas.append(f"erro esperado não encontrado: {codigo}")
    return problemas


def main() -> int:
    casos = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    falhas = 0
    for caso in casos:
        problemas = verificar_caso(caso)
        if problemas:
            falhas += 1
            print(f"FALHOU {caso['id']}: {'; '.join(problemas)}")
        else:
            print(f"PASSOU {caso['id']}: {caso['descricao']}")
    print(f"\nResultado: {len(casos) - falhas}/{len(casos)} casos aprovados")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
