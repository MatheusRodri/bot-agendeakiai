"""Acesso somente de leitura à API real do AgendeAki."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from urllib import error, parse, request
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


def _normalizar(valor: str) -> str:
    texto = unicodedata.normalize("NFD", valor.casefold())
    return "".join(caractere for caractere in texto if unicodedata.category(caractere) != "Mn")


def _url_base_valida(base_url: str) -> bool:
    partes = urlsplit(base_url)
    host_local = partes.hostname in {"localhost", "127.0.0.1", "::1"}
    return partes.scheme == "https" or (partes.scheme == "http" and host_local)


def _requisitar(
    base_url: str,
    metodo: str,
    caminho: str,
    token: str = "",
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    corpo = json.dumps(payload).encode("utf-8") if payload is not None else None
    cabecalhos = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    requisicao = request.Request(
        f"{base_url.rstrip('/')}{caminho}",
        data=corpo,
        method=metodo,
        headers=cabecalhos,
    )
    try:
        with request.urlopen(requisicao, timeout=timeout) as resposta:
            corpo_resposta = resposta.read().decode("utf-8")
            if not corpo_resposta:
                return {"ok": True}
            dados = json.loads(corpo_resposta)
        if not isinstance(dados, dict):
            return {"ok": False, "erro": {"codigo": "FORMATO_INVALIDO", "mensagem": "A API não retornou um objeto JSON."}}
        return {"ok": True, **dados}
    except error.HTTPError as exc:
        try:
            dados = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            dados = {}
        return {
            "ok": False,
            "erro": {
                "codigo": dados.get("codigo", f"HTTP_{exc.code}"),
                "mensagem": dados.get("mensagem", f"A API respondeu HTTP {exc.code}."),
                "metodo": metodo,
                "endpoint": caminho.split("?", 1)[0],
            },
        }
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "erro": {
                "codigo": "API_INDISPONIVEL" if not isinstance(exc, json.JSONDecodeError) else "JSON_INVALIDO",
                "mensagem": "Não foi possível consultar a API." if not isinstance(exc, json.JSONDecodeError) else "A API retornou JSON inválido.",
                "metodo": metodo,
                "endpoint": caminho.split("?", 1)[0],
            },
        }


def autenticar_cliente(base_url: str, email: str, senha: str) -> tuple[str, dict[str, Any]]:
    if not _url_base_valida(base_url):
        raise ValueError("A URL da API deve usar HTTPS; HTTP só é permitido em localhost.")
    resposta = _requisitar(base_url, "POST", "/api/clientes/login", payload={"email": email, "senha": senha})
    if not resposta.get("ok"):
        mensagem = resposta.get("erro", {}).get("mensagem", "Não foi possível entrar.")
        raise ValueError(f"Login não realizado: {mensagem}")
    token = resposta.get("tokenAcesso", "")
    usuario = resposta.get("usuario", {})
    if not token or not usuario.get("id"):
        raise ValueError("A API não retornou uma sessão válida de cliente.")
    return token, usuario


@dataclass(frozen=True)
class AgendeAkiApiTools:
    """Implementa as ferramentas de leitura usando a sessão do cliente.

    A escrita de agendamentos fica intencionalmente desabilitada nesta etapa.
    """

    base_url: str
    token: str = field(repr=False)
    cliente_id: str
    latitude: float
    longitude: float
    raio_km: int
    data: str
    timeout_seconds: float = 10.0
    fonte_catalogo: str = "API AgendeAki: serviços e horários disponíveis"
    usar_memoria_local = False
    persistir_checkpoint = False
    allow_booking = False

    def __post_init__(self) -> None:
        if not _url_base_valida(self.base_url):
            raise ValueError("A URL da API deve usar HTTPS; HTTP só é permitido em localhost.")
        if not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError("Latitude ou longitude fora do intervalo permitido.")
        if self.raio_km not in {0, 1, 5, 10}:
            raise ValueError("O raio deve ser 0, 1, 5 ou 10 km.")
        date.fromisoformat(self.data)

    def _request(
        self,
        metodo: str,
        caminho: str,
        payload: dict[str, Any] | None = None,
        autenticado: bool = True,
    ) -> dict[str, Any]:
        resposta = _requisitar(
            self.base_url,
            metodo,
            caminho,
            self.token if autenticado else "",
            payload,
            self.timeout_seconds,
        )
        if not resposta.get("ok"):
            erro = resposta.setdefault("erro", {})
            erro.setdefault("metodo", metodo)
            erro.setdefault("endpoint", caminho.split("?", 1)[0])
        return resposta

    def consultar_historico(self, cliente_id: str | None = None) -> dict[str, Any]:
        resposta = self._request("GET", "/api/clientes/agendamentos/historico")
        if not resposta.get("ok"):
            return resposta
        agendamentos = resposta.get("agendamentos", [])
        return {
            "ok": True,
            "cliente": {"preferencias": {}, "agendamentos": agendamentos},
            "agendamentos": agendamentos,
        }

    def buscar_opcoes(
        self,
        servico: str = "",
        bairro: str = "",
        orcamento_max: float | None = None,
        cliente_id: str | None = None,
    ) -> dict[str, Any]:
        parametros = parse.urlencode({
            "latitude": self.latitude,
            "longitude": self.longitude,
            "raioKm": self.raio_km,
        })
        resposta_saloes = self._request("GET", f"/api/clientes/saloes-proximos?{parametros}")
        if not resposta_saloes.get("ok"):
            return resposta_saloes

        servico_buscado = _normalizar(servico)
        bairro_buscado = _normalizar(bairro)
        saloes = resposta_saloes.get("saloes", [])
        servicos_compativeis = 0
        servicos_com_profissionais = 0
        horarios_recebidos = 0
        opcoes: list[dict[str, Any]] = []
        for salao in saloes:
            if bairro_buscado and _normalizar(str(salao.get("bairro", ""))) != bairro_buscado:
                continue

            resposta_servicos = self._request("GET", f"/api/clientes/saloes/{int(salao['idUnidade'])}/servicos")
            if not resposta_servicos.get("ok"):
                return resposta_servicos

            for item_servico in resposta_servicos.get("servicos", []):
                nome_servico = str(item_servico.get("nome", ""))
                valor = float(item_servico.get("valor", 0))
                if servico_buscado and servico_buscado not in _normalizar(nome_servico):
                    continue
                if orcamento_max is not None and valor > orcamento_max:
                    continue
                servicos_compativeis += 1
                if not item_servico.get("profissionais"):
                    continue
                servicos_com_profissionais += 1

                caminho_publico = (
                    f"/api/publico/agendamento/{parse.quote(str(salao['slugSalao']), safe='')}"
                    f"/{parse.quote(str(salao['slugFilial']), safe='')}"
                )
                consulta_horarios = parse.urlencode({
                    "data": self.data,
                    "idFuncionario": "qualquer",
                    "idServico": item_servico["idServico"],
                })
                resposta_horarios = self._request(
                    "GET", f"{caminho_publico}/horarios?{consulta_horarios}", autenticado=False
                )
                if not resposta_horarios.get("ok"):
                    return resposta_horarios

                horarios = resposta_horarios.get("horarios", [])
                horarios_recebidos += len(horarios)
                for horario in horarios:
                    profissional = horario.get("profissionalSugerido")
                    if not profissional:
                        continue
                    inicio = datetime.fromisoformat(f"{self.data}T{horario['inicio']}:00").replace(
                        tzinfo=ZoneInfo("America/Sao_Paulo")
                    )
                    opcoes.append({
                        "opcaoId": f"unidade-{salao['idUnidade']}-servico-{item_servico['idServico']}-{self.data}-{horario['inicio']}",
                        "idUnidade": int(salao["idUnidade"]),
                        "idServico": int(item_servico["idServico"]),
                        "idFuncionario": int(profissional["idFuncionario"]),
                        "salao": salao.get("nomeSalao", "Salão"),
                        "bairro": salao.get("bairro", ""),
                        "servico": nome_servico,
                        "profissional": profissional.get("nome", profissional.get("nomeFuncionario", "Profissional")),
                        "dataHoraInicio": inicio.isoformat(),
                        "preco": valor,
                        "estilos": [],
                    })

        opcoes.sort(key=lambda opcao: (opcao["dataHoraInicio"], opcao["preco"], opcao["salao"]))
        return {
            "ok": True,
            "opcoes": opcoes,
            "diagnostico": {
                "saloes_no_raio": len(saloes),
                "servicos_compativeis": servicos_compativeis,
                "servicos_com_profissionais": servicos_com_profissionais,
                "horarios_encontrados": horarios_recebidos,
            },
        }

    def confirmar_agendamento(
        self,
        opcao: dict[str, Any],
        chave_idempotencia: str | None = None,
        cliente_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "erro": {
                "codigo": "ESCRITA_DESABILITADA",
                "mensagem": "A integração está em modo somente leitura; nenhum agendamento foi enviado.",
            },
        }

    def encerrar_sessao(self) -> None:
        self._request("POST", "/api/clientes/logout")
