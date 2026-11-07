"""Controles aplicados em código (fora do prompt). Cada um tem teste em tests/."""

from __future__ import annotations

import re
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
