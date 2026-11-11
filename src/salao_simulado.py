"""Salão em memória com a mesma interface das ferramentas do modo conversa.

Usado pelos testes, pela suíte de avaliação e por `src.main --chat` sem backend
real. Os dados vêm de `dados/salao_simulado.json` e são fictícios.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .agendeaki_api import OBSERVACAO_AGENDAMENTO

ROOT = Path(__file__).resolve().parents[1]
ARQUIVO = ROOT / "dados" / "salao_simulado.json"
FUSO = ZoneInfo("America/Sao_Paulo")
JANELA_DIAS = 60


def _minutos(hora: str) -> int:
    horas, minutos = hora.split(":")
    return int(horas) * 60 + int(minutos)


def _hora(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


class SalaoSimulado:
    usar_memoria_local = False

    def __init__(self, arquivo: Path = ARQUIVO, agora: datetime | None = None) -> None:
        self.dados = json.loads(arquivo.read_text(encoding="utf-8"))
        self.agora = agora
        self.agendamentos: list[dict[str, Any]] = []

    def _agora(self) -> datetime:
        return self.agora or datetime.now(FUSO)

    def localizar_salao_mais_proximo(self) -> dict[str, Any]:
        return {"ok": True, "salao": dict(self.dados["salao"])}

    def listar_servicos(self, id_unidade: int) -> dict[str, Any]:
        return {"ok": True, "servicos": [dict(servico) for servico in self.dados["servicos"]]}

    def _servico(self, id_servico: int) -> dict[str, Any] | None:
        return next((s for s in self.dados["servicos"] if s["idServico"] == int(id_servico)), None)

    def listar_horarios(self, id_unidade: int, id_servico: int, data: str) -> dict[str, Any]:
        dia = date.fromisoformat(data)
        hoje = self._agora().date()
        if not hoje <= dia <= hoje + timedelta(days=JANELA_DIAS):
            return {"ok": False, "erro": {"codigo": "HTTP_400", "mensagem": "Escolha uma data entre hoje e os próximos 60 dias."}}
        servico = self._servico(id_servico)
        if not servico:
            return {"ok": False, "erro": {"codigo": "HTTP_404", "mensagem": "O serviço não está disponível nesta unidade."}}
        expediente = self.dados["expediente"]
        ocupados = [(_minutos(a["inicio"]), _minutos(a["fim"])) for a in self.agendamentos if a["data"] == data]
        agora_minutos = _minutos(self._agora().strftime("%H:%M")) if dia == hoje else -1
        horarios = []
        inicio = _minutos(expediente["inicio"])
        while inicio + servico["duracaoMinutos"] <= _minutos(expediente["fim"]):
            fim = inicio + servico["duracaoMinutos"]
            livre = inicio > agora_minutos and not any(inicio < o_fim and o_inicio < fim for o_inicio, o_fim in ocupados)
            if livre:
                profissional = self.dados["profissional"]
                horarios.append({"inicio": _hora(inicio), "fim": _hora(fim), "idFuncionario": profissional["idFuncionario"], "profissional": profissional["nome"]})
            inicio += servico["duracaoMinutos"]  # mesma grade do backend (gerarCandidatosPeriodo)
        return {"ok": True, "horarios": horarios}

    def criar_agendamentos(self, id_unidade: int, itens: list[dict[str, Any]]) -> dict[str, Any]:
        novos = []
        for item in itens:
            servico = self._servico(item["idServico"])
            data, inicio = item["dataHoraInicio"][:10], item["dataHoraInicio"][11:16]
            livres = self.listar_horarios(id_unidade, item["idServico"], data).get("horarios", [])
            if not servico or inicio not in {h["inicio"] for h in livres}:
                return {"ok": False, "erro": {"codigo": "CONFLITO_HORARIO", "mensagem": "O horário não está mais disponível."}}
            if f'{servico["valor"]:.2f}' != f'{float(item["valor"]):.2f}':
                return {"ok": False, "erro": {"codigo": "PRECO_ALTERADO", "mensagem": "O preço do serviço mudou."}}
            novos.append({"idAgendamento": 1000 + len(self.agendamentos) + len(novos) + 1, "data": data, "inicio": inicio, "fim": _hora(_minutos(inicio) + servico["duracaoMinutos"]), "observacao": OBSERVACAO_AGENDAMENTO, **item})
        self.agendamentos.extend(novos)  # tudo ou nada, como a transação do backend
        return {"ok": True, "idsAgendamentos": [novo["idAgendamento"] for novo in novos]}
