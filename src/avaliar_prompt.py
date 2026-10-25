"""Compara a redação Gemini com e sem a frase selecionada do prompt."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from .modelo import MAX_CUSTO_USD, MAX_TOKENS_SAIDA, ROOT, responder_com_gemini


FRASE = "Não exponha raciocínio interno."
TETO_TOTAL_USD = 0.20
ARQUIVO_PROMPT = ROOT / "src" / "prompts" / "agente-v1.txt"
ARQUIVO_PERGUNTAS = ROOT / "dados" / "perguntas-rag.json"
ARQUIVO_RESULTADO = ROOT / "dados" / "resultado-avaliacao-prompt-cancelamento-livre.json"
FONTES = ["dados/corpus/regras-vigentes.md"]


def _caso(item: dict[str, str]) -> tuple[str, list[str], bool]:
    sem_suporte = item["tipo"] in {"sem resposta", "fora do corpus"}
    return item["resposta"], [] if sem_suporte else FONTES.copy(), not sem_suporte


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _salvar(resultado: dict[str, Any]) -> None:
    ARQUIVO_RESULTADO.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _consultar_com_retentativas(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, int | float]]:
    for tentativa in range(3):
        try:
            return responder_com_gemini(*args, **kwargs)
        except Exception as exc:
            codigo = getattr(exc, "code", None)
            transitorio = codigo in (503, 504) or isinstance(exc, httpx.TimeoutException)
            if not transitorio or tentativa == 2:
                raise
            espera = 5 * (2 ** tentativa)
            diagnostico = f"HTTP {codigo}" if codigo else type(exc).__name__
            print(f"{diagnostico}; nova tentativa do mesmo caso em {espera} segundos.")
            time.sleep(espera)
    raise RuntimeError("Tentativas esgotadas.")


def main() -> int:
    load_dotenv(ROOT / ".env")
    prompt = ARQUIVO_PROMPT.read_text(encoding="utf-8")
    if prompt.count(FRASE) != 1:
        raise ValueError("A frase selecionada deve aparecer exatamente uma vez no prompt ativo.")
    prompt_sem_frase = prompt.replace(FRASE, "")
    perguntas = json.loads(ARQUIVO_PERGUNTAS.read_text(encoding="utf-8"))
    tarefas = [
        (rotulo, variante, indice, item)
        for rotulo, variante in (("presente", prompt), ("removida", prompt_sem_frase))
        for indice, item in enumerate(perguntas, start=1)
    ]
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
    if ARQUIVO_RESULTADO.exists():
        anterior = json.loads(ARQUIVO_RESULTADO.read_text(encoding="utf-8"))
        casos_salvos = anterior.get("casos")
        if not isinstance(casos_salvos, list):
            print("Resultado parcial inválido; arquivo preservado.")
            return 1
        if casos_salvos:
            campos = ("modelo", "frase_comparada", "hash_prompt_com_frase", "hash_prompt_sem_frase", "teto_total_usd")
            mesma_avaliacao = all(anterior.get(campo) == resultado[campo] for campo in campos)
            mesma_ordem = len(casos_salvos) <= len(tarefas) and all(
                isinstance(caso, dict)
                and caso.get("variante") == tarefa[0]
                and caso.get("indice") == tarefa[2]
                and caso.get("pergunta") == tarefa[3]["pergunta"]
                for caso, tarefa in zip(casos_salvos, tarefas)
            )
            if not mesma_avaliacao or not mesma_ordem:
                print("Resultado parcial incompatível com o modelo, prompt ou perguntas atuais; arquivo preservado.")
                return 1
            resultado = anterior

    concluidos = len(resultado["casos"])
    for caso_salvo in resultado["casos"]:
        caso_salvo.setdefault("limite_tokens_saida", 400)
    if concluidos == len(tarefas):
        resultado["status"] = "concluido"
        _salvar(resultado)
        print(f"Avaliação já concluída: {concluidos} chamadas; nenhuma nova chamada feita.")
        return 0
    if concluidos:
        print(f"Retomando avaliação após {concluidos} caso(s) salvo(s).")
    if any("tokens_pensamento" not in caso for caso in resultado["casos"]):
        resultado["aviso_custo"] = "Casos anteriores não registraram tokens de raciocínio; gasto_usd pode estar subestimado."
    resultado["status"] = "em_andamento"
    for campo in ("erro_tipo", "erro_http", "erro_status_api", "erro_limite"):
        resultado.pop(campo, None)
    _salvar(resultado)

    try:
        for posicao, (rotulo, variante, indice, item) in enumerate(tarefas):
            if posicao < concluidos:
                continue
            resposta, fontes, suficiente = _caso(item)
            restante = TETO_TOTAL_USD - float(resultado["gasto_usd"])
            if restante <= 0:
                resultado["status"] = "interrompido_teto_total"
                _salvar(resultado)
                print(f"Interrompido no teto total de US$ {TETO_TOTAL_USD:.2f}.")
                return 2
            saida, uso = _consultar_com_retentativas(
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
                "tokens_pensamento": int(uso["tokens_pensamento"]),
                "limite_tokens_saida": MAX_TOKENS_SAIDA,
                "custo_usd": custo,
                "avaliacao_humana": None,
            })
            _salvar(resultado)
            print(f"{rotulo} {indice}/10 concluído; custo acumulado: US$ {resultado['gasto_usd']:.6f}")
        resultado["status"] = "concluido"
    except Exception as exc:
        # Registra só metadados seguros da API, nunca o corpo ou a mensagem da requisição.
        resultado["status"] = "bloqueado_prevalidacao" if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else "falha_chamada"
        resultado["erro_tipo"] = type(exc).__name__
        codigo_http = getattr(exc, "code", None)
        status_api = getattr(exc, "status", None)
        if isinstance(codigo_http, int):
            resultado["erro_http"] = codigo_http
        if isinstance(status_api, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,40}", status_api):
            resultado["erro_status_api"] = status_api
        if codigo_http == 429:
            mensagem = str(getattr(exc, "message", "") or "").lower()
            if any(termo in mensagem for termo in ("per day", "perday", "daily", "rpd")):
                resultado["erro_limite"] = "diario"
            elif any(termo in mensagem for termo in ("per minute", "perminute", "rpm", "tpm")):
                resultado["erro_limite"] = "por_minuto"
            elif any(termo in mensagem for termo in ("spend-based", "spend limit", "spend rate", "monthly spend")):
                resultado["erro_limite"] = "gasto"
            else:
                resultado["erro_limite"] = "nao_identificado"
        _salvar(resultado)
        diagnostico = f"HTTP {resultado['erro_http']} {resultado.get('erro_status_api', '')}".strip() if "erro_http" in resultado else type(exc).__name__
        if codigo_http == 429:
            diagnostico += f"; limite={resultado['erro_limite']}"
        print(f"Avaliação interrompida ({resultado['status']}: {diagnostico}); diagnóstico seguro salvo.")
        return 1

    _salvar(resultado)
    print(f"Avaliação concluída: {len(resultado['casos'])} chamadas; custo total US$ {resultado['gasto_usd']:.6f}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
