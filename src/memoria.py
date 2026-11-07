"""Memória local simples em JSON para episódios e preferências declaradas."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARQUIVO_MEMORIA = ROOT / "dados" / "memoria.json"


def carregar() -> dict[str, Any]:
    if not ARQUIVO_MEMORIA.exists():
        return {"episodios": [], "preferencias": {}}
    return json.loads(ARQUIVO_MEMORIA.read_text(encoding="utf-8"))


def salvar(memoria: dict[str, Any]) -> None:
    ARQUIVO_MEMORIA.parent.mkdir(exist_ok=True)
    ARQUIVO_MEMORIA.write_text(json.dumps(memoria, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def palavras(texto: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", texto.lower()))


def recuperar(cliente_id: str, texto: str) -> dict[str, Any]:
    memoria = carregar()
    episodios = [item for item in memoria["episodios"] if item["cliente_id"] == cliente_id]
    consulta = palavras(texto)
    melhor = None
    maior = 0.0
    for episodio in episodios:
        termos = palavras(episodio["texto"])
        similaridade = len(consulta & termos) / max(1, len(consulta | termos))
        if similaridade > maior:
            melhor, maior = episodio, similaridade
    return {"episodio": melhor if maior >= 0.15 else None, "preferencias": memoria["preferencias"].get(cliente_id, {})}


PADROES_BLOQUEADOS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "documento_ou_telefone": r"(?:\d[\s.\-()]*){9,}",
    "credencial": r"\b(?:senha|password|token|api[_ -]?key|bearer)\b",
    "instrucao_injetada": r"(?:ignore|desconsidere|esqueca|esqueça)\s+(?:todas?\s+)?(?:as\s+)?(?:instru|regras|ordens)|system prompt|prompt de sistema|voce agora e|você agora é",
}


def motivo_bloqueio(texto: str) -> str | None:
    """Controle de gravação: devolve o motivo se o texto não pode ir para a memória."""
    for motivo, padrao in PADROES_BLOQUEADOS.items():
        if re.search(padrao, texto, re.IGNORECASE):
            return motivo
    return None


def registrar(cliente_id: str, texto: str) -> str | None:
    """Grava o episódio. Fail-closed: se o filtro bloquear, nada é gravado e o motivo é devolvido."""
    motivo = motivo_bloqueio(texto)
    if motivo:
        return motivo
    memoria = carregar()
    agora = datetime.now(timezone.utc).isoformat()
    memoria["episodios"].append({"cliente_id": cliente_id, "texto": texto[:180], "criado_em": agora})
    preferencias = memoria["preferencias"].setdefault(cliente_id, {})
    texto_lower = re.sub(r"\s+", " ", texto.lower())
    formas = {
        "clássico": ("prefiro clássico", "gosto de clássico", "normalmente escolho algo clássico", "normalmente escolher algo clássico", "costumo escolher clássico", "minha preferência é clássico"),
        "moderno": ("prefiro moderno", "gosto de moderno", "normalmente escolho algo moderno", "normalmente escolher algo moderno", "costumo escolher moderno", "minha preferência é moderno"),
        "natural": ("prefiro natural", "gosto de natural", "normalmente escolho algo natural", "normalmente escolher algo natural", "costumo escolher natural", "minha preferência é natural"),
        "discreto": ("prefiro discreto", "gosto de discreto", "normalmente escolho algo discreto", "normalmente escolher algo discreto", "costumo escolher discreto", "minha preferência é discreto"),
        "elegante": ("prefiro elegante", "gosto de elegante", "normalmente escolho algo elegante", "normalmente escolher algo elegante", "costumo escolher elegante", "minha preferência é elegante"),
    }
    declaracoes = [(texto_lower.rfind(expressao), valor) for valor, expressoes in formas.items() for expressao in expressoes if expressao in texto_lower]
    if declaracoes:
        preferencias["estilo"] = {"valor": max(declaracoes)[1], "atualizado_em": agora}
    salvar(memoria)
    return None


def remover(cliente_id: str) -> None:
    memoria = carregar()
    memoria["episodios"] = [item for item in memoria["episodios"] if item["cliente_id"] != cliente_id]
    memoria["preferencias"].pop(cliente_id, None)
    salvar(memoria)
