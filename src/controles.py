"""Controles aplicados em código (fora do prompt). Cada um tem teste em tests/."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def verificar_escrita(estado: dict[str, Any]) -> str | None:
    """Controle 2 (ASI02/ASI09): a escrita só ocorre com aprovação humana, opção
    já consultada e no máximo uma vez por execução. Devolve o motivo do bloqueio."""
    decisao = estado.get("decisao", {})
    if not decisao.get("aprovada"):
        return "sem_aprovacao_humana"
    opcao = decisao.get("opcao") or {}
    consultadas = estado.get("aprovacao_pendente", {}).get("opcoes_consultadas", [])
    if opcao.get("opcaoId") not in consultadas:
        return "opcao_nao_consultada"
    ja_escreveu = bool(estado.get("agendamento")) or any(
        e.get("tipo") == "ferramenta" and e.get("ferramenta") == "confirmar_agendamento" for e in estado.get("eventos", [])
    )
    if ja_escreveu:
        return "limite_de_uma_escrita_por_execucao"
    return None


_ID = re.compile(r"\bopc-\d+\b", re.IGNORECASE)
_PRECO = re.compile(r"R\$\s*\d+(?:[.,]\d+)?")
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:\-+]+)?")
_AFIRMA_ESCRITA = re.compile(r"agendamento (?:foi )?(?:confirmado|realizado|registrado)|reservei|agendei|reserva (?:foi )?confirmada", re.IGNORECASE)
_NEGA_ESCRITA = re.compile(r"nenhum agendamento|n[aã]o (?:foi|realizei|fiz)", re.IGNORECASE)


def _valores(texto: str) -> set[float]:
    """Valores em R$ como número, para 'R$ 120,00' e 'R$ 120.00' valerem o mesmo."""
    return {float(m.group(0).replace("R$", "").strip().replace(",", ".")) for m in _PRECO.finditer(texto)}


def validar_saida_modelo(resposta_base: str, candidata: str, agendou: bool) -> str | None:
    """Controle 3 (ASI01/ASI09): a redação do modelo não pode introduzir id, preço ou
    horário fora da resposta verificada, nem afirmar escrita que não aconteceu.
    Devolve o motivo da rejeição; None se aceita."""
    for nome, padrao in (("id_inventado", _ID), ("horario_inventado", _DATA)):
        if set(padrao.findall(candidata)) - set(padrao.findall(resposta_base)):
            return nome
    if _valores(candidata) - _valores(resposta_base):
        return "preco_inventado"
    if not agendou and _AFIRMA_ESCRITA.search(candidata) and not _NEGA_ESCRITA.search(candidata):
        return "afirma_escrita_inexistente"
    return None


# --- Modo conversa (src/conversa.py) ---

def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c))


_PEDE_AGENDAR = (
    re.compile(r"\bpode(?:s|ria)?\s+(?:ja\s+|sim\s+)?(?:agendar|marcar|reservar|confirmar|fechar)\b"),
    re.compile(r"\b(?:agende|agenda|marque|marca|reserve|reserva)\s+(?:isso\s+|tudo\s+)?(?:pra|para)\s+mim\b"),
    re.compile(r"\b(?:agende|marque|reserve)\b"),
    re.compile(r"\b(?:quero|vou|gostaria\s+de)\s+(?:agendar|marcar|reservar)\b"),
    re.compile(r"\bja\s+(?:agenda|marca|reserva)\b"),
    re.compile(r"\bconfirmo\b"),
)
_NEGA_AGENDAR = re.compile(r"\bnao\s+(?:\w+\s+){0,3}?(?:agend|marc|reserv|confirm)\w*|\bsem\s+agendar\b")


def pedido_explicito_de_agendamento(texto: str) -> bool | None:
    """Lê o texto digitado pelo cliente: True = pediu para agendar; False = negou
    ("não agende", "sem agendar"); None = não disse nada sobre agendar."""
    frase = _sem_acento(texto)
    if _NEGA_AGENDAR.search(frase):
        return False
    if any(padrao.search(frase) for padrao in _PEDE_AGENDAR):
        return True
    return None


def validar_recomendacao(ids: list[int], catalogo: list[dict[str, Any]], maximo: int = 3) -> str | None:
    """Controle 3b: o modelo só pode recomendar serviços do catálogo consultado."""
    if not ids:
        return "recomendacao_vazia"
    if len(ids) > maximo:
        return "recomendacao_excede_limite"
    if len(set(ids)) != len(ids):
        return "recomendacao_repetida"
    if set(ids) - {int(s["idServico"]) for s in catalogo}:
        return "servico_inventado"
    return None


def verificar_escrita_conversa(
    pedido_explicito: bool,
    plano: list[dict[str, Any]],
    ids_recomendados: list[int],
    horarios_consultados: set[tuple[int, str]],
    ja_agendou: bool,
) -> str | None:
    """Controle 5 (ASI02/ASI09): no modo conversa a escrita só ocorre se o próprio
    cliente pediu para agendar, com serviços recomendados, horários consultados na
    API e no máximo uma vez por conversa. Devolve o motivo do bloqueio."""
    if not pedido_explicito:
        return "sem_pedido_explicito"
    if not plano:
        return "plano_vazio"
    if any(int(item["idServico"]) not in ids_recomendados for item in plano):
        return "servico_nao_recomendado"
    if any((int(item["idServico"]), item["dataHoraInicio"]) not in horarios_consultados for item in plano):
        return "horario_nao_consultado"
    if ja_agendou:
        return "limite_de_uma_escrita_por_conversa"
    return None
