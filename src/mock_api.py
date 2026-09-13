"""API HTTP tradicional e mockada para a prova de conceito.

Ela roda em outro processo e simula a fronteira que depois será substituída pelo
backend Express do monorepo-agendeaki.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "dados" / "catalogo.json"


class MockStore:
    def __init__(self, catalog_path: Path = CATALOG_PATH) -> None:
        self.catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.agendamentos: list[dict[str, Any]] = []

    def historico(self, cliente_id: str) -> dict[str, Any] | None:
        return self.catalog["clientes"].get(cliente_id)

    def opcoes(self, filtros: dict[str, list[str]]) -> list[dict[str, Any]]:
        servico = filtros.get("servico", [""])[0].strip().lower()
        bairro = filtros.get("bairro", [""])[0].strip().lower()
        orcamento_texto = filtros.get("orcamentoMax", [""])[0]
        try:
            orcamento = float(orcamento_texto) if orcamento_texto else None
        except ValueError:
            return []

        return [
            opcao
            for opcao in self.catalog["opcoes"]
            if (not servico or servico in opcao["servico"].lower())
            and (not bairro or bairro == opcao["bairro"].lower())
            and (orcamento is None or float(opcao["preco"]) <= orcamento)
        ]

    def agendar(self, cliente_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        opcao = next(
            (
                item
                for item in self.catalog["opcoes"]
                if item["opcaoId"] == payload.get("opcaoId")
                and item["idUnidade"] == payload.get("idUnidade")
                and item["idServico"] == payload.get("idServico")
                and item["idFuncionario"] == payload.get("idFuncionario")
                and item["dataHoraInicio"] == payload.get("dataHoraInicio")
            ),
            None,
        )
        if not opcao:
            return None

        agendamento = {
            "idAgendamento": f"agd-{len(self.agendamentos) + 1:03d}",
            "clienteId": cliente_id,
            "status": "CONFIRMADO",
            "criadoEm": datetime.now(timezone.utc).isoformat(),
            "opcao": opcao,
        }
        self.agendamentos.append(agendamento)
        return agendamento


class MockApiHandler(BaseHTTPRequestHandler):
    server_version = "AgendeAkiMock/1.0"

    @property
    def store(self) -> MockStore:
        return self.server.store  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802 - assinatura do BaseHTTPRequestHandler
        url = urlparse(self.path)
        if url.path == "/saude":
            self._json(HTTPStatus.OK, {"status": "online", "modo": "mock"})
            return
        if not self._autorizado():
            return
        if url.path == "/api/clientes/agendamentos/historico":
            cliente_id = self.headers.get("X-Mock-Cliente-Id", "")
            historico = self.store.historico(cliente_id)
            if not historico:
                self._json(
                    HTTPStatus.NOT_FOUND,
                    {
                        "codigo": "CLIENTE_NAO_ENCONTRADO",
                        "mensagem": f"Cliente '{cliente_id}' não existe no mock.",
                        "como_continuar": "Continue sem personalização e use somente o pedido atual.",
                    },
                )
                return
            self._json(HTTPStatus.OK, {"cliente": historico})
            return
        if url.path == "/api/clientes/opcoes":
            self._json(HTTPStatus.OK, {"opcoes": self.store.opcoes(parse_qs(url.query))})
            return
        self._json(HTTPStatus.NOT_FOUND, {"codigo": "ROTA_NAO_ENCONTRADA", "mensagem": "Rota inexistente."})

    def do_POST(self) -> None:  # noqa: N802 - assinatura do BaseHTTPRequestHandler
        url = urlparse(self.path)
        if not self._autorizado():
            return
        if url.path != "/api/clientes/agendamentos":
            self._json(HTTPStatus.NOT_FOUND, {"codigo": "ROTA_NAO_ENCONTRADA", "mensagem": "Rota inexistente."})
            return
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"codigo": "JSON_INVALIDO", "mensagem": "Corpo JSON inválido."})
            return

        cliente_id = self.headers.get("X-Mock-Cliente-Id", "")
        if not self.store.historico(cliente_id):
            self._json(
                HTTPStatus.NOT_FOUND,
                {"codigo": "CLIENTE_NAO_ENCONTRADO", "mensagem": "Cliente não pode realizar agendamento."},
            )
            return
        agendamento = self.store.agendar(cliente_id, payload)
        if not agendamento:
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {
                    "codigo": "OPCAO_INVALIDA",
                    "mensagem": "A opção não existe ou seus dados foram alterados.",
                    "como_continuar": "Busque as opções novamente antes de confirmar.",
                },
            )
            return
        opcao = agendamento["opcao"]
        self._json(
            HTTPStatus.CREATED,
            {
                "agendamento": agendamento,
                "mensagem": (
                    f'Agendamento {agendamento["idAgendamento"]} confirmado: {opcao["servico"]} '
                    f'com {opcao["profissional"]} no {opcao["salao"]}, por R$ {opcao["preco"]:.2f}.'
                ),
            },
        )

    def _autorizado(self) -> bool:
        if self.headers.get("Authorization") != "Bearer token-mock":
            self._json(HTTPStatus.UNAUTHORIZED, {"codigo": "NAO_AUTORIZADO", "mensagem": "Token inválido."})
            return False
        return True

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[mock-api] {self.address_string()} {format % args}")


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), MockApiHandler)
    server.store = MockStore()  # type: ignore[attr-defined]
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="API mock do AgendeAki")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"API mock disponível em http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

