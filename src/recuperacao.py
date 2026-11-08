"""Busca textual direta no corpus ativo de regras, sem embeddings ou cortes."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "dados" / "corpus"
PALAVRAS_COMUNS = {"a", "ao", "as", "com", "como", "da", "das", "de", "do", "dos", "e", "é", "em", "essa", "esse", "esta", "este", "eu", "minha", "no", "nos", "o", "os", "para", "posso", "qual", "que", "se", "um", "uma", "voce"}


def normalizar(texto: str) -> str:
    return "".join(letra for letra in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(letra))


def _raiz_simples(termo: str) -> str:
    if termo.startswith("cancel"):
        return "cancel"
    if termo.startswith("remarc"):
        return "remarc"
    if termo.startswith(("doenc", "doent")):
        return "doenca"
    if termo.startswith(("taxa", "pag", "cobr", "cust")):
        return "custo"
    if termo.startswith(("reembols", "devolv")):
        return "reembolso"
    return termo


def buscar_regra(pergunta: str) -> list[dict[str, str]]:
    consulta = {_raiz_simples(termo) for termo in re.findall(r"[a-z0-9]+", normalizar(pergunta))} - PALAVRAS_COMUNS
    resultados = []
    for caminho in sorted(CORPUS.glob("*.md")):
        conteudo = caminho.read_text(encoding="utf-8")
        if "status: vigente" not in conteudo.lower():
            continue
        for trecho in re.split(r"\n(?=## )", conteudo):
            termos = {_raiz_simples(termo) for termo in re.findall(r"[a-z0-9]+", normalizar(trecho))} - PALAVRAS_COMUNS
            pontos = len(consulta & termos)
            if pontos:
                titulo = next((linha[3:].strip() for linha in trecho.splitlines() if linha.startswith("## ")), caminho.stem)
                resultados.append({"fonte": caminho.relative_to(ROOT).as_posix(), "trecho": trecho.strip(), "titulo": titulo, "pontos": str(pontos)})
    resultados.sort(key=lambda item: int(item["pontos"]), reverse=True)
    return resultados
