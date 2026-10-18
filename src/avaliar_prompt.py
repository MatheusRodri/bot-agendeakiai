"""Compara a redação Gemini com e sem a frase selecionada do prompt."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .modelo import MAX_CUSTO_USD, ROOT, responder_com_gemini


FRASE = "Não exponha raciocínio interno."
TETO_TOTAL_USD = 0.20
ARQUIVO_PROMPT = ROOT / "src" / "prompts" / "agente-v1.txt"
ARQUIVO_PERGUNTAS = ROOT / "dados" / "perguntas-rag.json"
ARQUIVO_RESULTADO = ROOT / "dados" / "resultado-avaliacao-prompt.json"
FONTES = ["dados/corpus/regras-vigentes.md"]


def _caso(item: dict[str, str]) -> tuple[str, list[str], bool]:
    sem_suporte = item["tipo"] in {"sem resposta", "fora do corpus"}
    return item["resposta"], [] if sem_suporte else FONTES.copy(), not sem_suporte


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _salvar(resultado: dict[str, Any]) -> None:
    ARQUIVO_RESULTADO.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    prompt = ARQUIVO_PROMPT.read_text(encoding="utf-8")
    if prompt.count(FRASE) != 1:
        raise ValueError("A frase selecionada deve aparecer exatamente uma vez no prompt ativo.")
    prompt_sem_frase = prompt.replace(FRASE, "")
    perguntas = json.loads(ARQUIVO_PERGUNTAS.read_text(encoding="utf-8"))
    modelo = os.getenv("LLM_MODELO") or "gemini-3.8-flash"
    resultado: dict[str, Any] = {
        "executado_em": datetime.now(timezone.utc).isoformat(),
        "modelo": modelo,
        "frase_comparada": FRASE,
        "hash_prompt_com_frase": _hash(prompt),
        "hash_prompt_sem_frase": _hash(prompt_sem_frase),
        "teto_total_usd": TETO_TOTAL_USD,
        "gasto_usd": 0.0,
        "casos": [],
        "status": "em_andamento",
    }
    _salvar(resultado)

    try:
        for rotulo, variante in (("presente", prompt), ("removida", prompt_sem_frase)):
            for indice, item in enumerate(perguntas, start=1):
                resposta, fontes, suficiente = _caso(item)
                restante = TETO_TOTAL_USD - float(resultado["gasto_usd"])
                if restante <= 0:
                    resultado["status"] = "interrompido_teto_total"
                    _salvar(resultado)
                    print(f"Interrompido no teto total de US$ {TETO_TOTAL_USD:.2f}.")
                    return 2
                saida, uso = responder_com_gemini(
                    item["pergunta"], resposta, fontes, suficiente,
                    prompt_override=variante,
                    custo_maximo_usd=min(MAX_CUSTO_USD, restante),
                )
                custo = float(uso["custo_usd"])
                resultado["gasto_usd"] = round(float(resultado["gasto_usd"]) + custo, 8)
                resultado["casos"].append({
                    "variante": rotulo,
                    "indice": indice,
                    "pergunta": item["pergunta"],
                    "resposta_esperada": resposta,
                    "fontes_esperadas": fontes,
                    "suficiente_esperado": suficiente,
                    "saida": saida,
                    "tokens_entrada": int(uso["tokens_entrada"]),
                    "tokens_saida": int(uso["tokens_saida"]),
                    "custo_usd": custo,
                    "avaliacao_humana": None,
                })
                _salvar(resultado)
                print(f"{rotulo} {indice}/10 concluído; custo acumulado: US$ {resultado['gasto_usd']:.6f}")
        resultado["status"] = "concluido"
    except Exception as exc:
        # Registra apenas o tipo do erro; mensagens de SDK podem conter detalhes de requisição.
        resultado["status"] = "bloqueado_ou_falha"
        resultado["erro_tipo"] = type(exc).__name__
        _salvar(resultado)
        print(f"Avaliação interrompida ({type(exc).__name__}); resultado parcial salvo sem detalhes de configuração.")
        return 1

    _salvar(resultado)
    print(f"Avaliação concluída: {len(resultado['casos'])} chamadas; custo total US$ {resultado['gasto_usd']:.6f}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
