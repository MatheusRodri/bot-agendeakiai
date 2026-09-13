"""Camada HTTP das ferramentas do agente.

Esta fronteira e intencional: hoje conversa com ``mock_api.py``; depois pode
adaptar os mesmos metodos para os endpoints do monorepo AgendeAki.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


@dataclass(frozen=True)
class ApiTools:
    base_url: str
    token: str
    cliente_id: str
    timeout_seconds: float = 3.0

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        requisicao = request.Request(
            f"{self.base_url.rstrip('/')}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-Mock-Cliente-Id": self.cliente_id,
            },
        )
        try:
            with request.urlopen(requisicao, timeout=self.timeout_seconds) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
                if not isinstance(dados, dict):
                    return self._erro("FORMATO_INVALIDO", "A API não retornou um objeto JSON.")
                return {"ok": True, **dados}
        except error.HTTPError as exc:
            try:
                dados_erro = json.loads(exc.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                dados_erro = {"mensagem": f"A API respondeu HTTP {exc.code}."}
            return self._erro(
                dados_erro.get("codigo", f"HTTP_{exc.code}"),
                dados_erro.get("mensagem", "Falha na API."),
                dados_erro.get("como_continuar"),
            )
        except (error.URLError, TimeoutError) as exc:
            return self._erro(
                "API_INDISPONIVEL",
                f"Não foi possível acessar a API: {exc.reason if hasattr(exc, 'reason') else exc}",
                "Informe que a disponibilidade não pôde ser verificada e não confirme agendamento.",
            )
        except json.JSONDecodeError:
            return self._erro(
                "JSON_INVALIDO",
                "A API retornou JSON inválido.",
                "Não invente dados; informe que a consulta falhou.",
            )

    @staticmethod
    def _erro(codigo: str, mensagem: str, como_continuar: str | None = None) -> dict[str, Any]:
        return {
            "ok": False,
            "erro": {"codigo": codigo, "mensagem": mensagem},
            "como_continuar": como_continuar or "Ajuste os argumentos ou prossiga sem este dado.",
        }

    def consultar_historico(self) -> dict[str, Any]:
        return self._request("GET", "/api/clientes/agendamentos/historico")

    def buscar_opcoes(
        self,
        servico: str = "",
        bairro: str = "",
        orcamento_max: float | None = None,
    ) -> dict[str, Any]:
        filtros = {"servico": servico, "bairro": bairro}
        if orcamento_max is not None:
            filtros["orcamentoMax"] = str(orcamento_max)
        consulta = parse.urlencode(filtros)
        return self._request("GET", f"/api/clientes/opcoes?{consulta}")

    def confirmar_agendamento(self, opcao: dict[str, Any]) -> dict[str, Any]:
        # O payload segue os campos usados hoje por POST /api/clientes/agendamentos
        # no monorepo. O opcaoId fica apenas para rastreabilidade do mock.
        payload = {
            "opcaoId": opcao["opcaoId"],
            "idUnidade": opcao["idUnidade"],
            "idServico": opcao["idServico"],
            "idFuncionario": opcao["idFuncionario"],
            "dataHoraInicio": opcao["dataHoraInicio"],
        }
        return self._request("POST", "/api/clientes/agendamentos", payload)

