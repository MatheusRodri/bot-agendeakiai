"""Agente simples do AgendeAkiAI, com tool calling, estado e orcamentos."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

try:
    from openai import OpenAI
except ModuleNotFoundError:  # permite executar a demonstração mock antes do pip install
    OpenAI = None  # type: ignore[assignment,misc]
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = lambda: None

from .tools import ApiTools


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "agente-v1.txt"
DEFAULT_API_URL = "http://127.0.0.1:8765"


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_historico",
            "description": "Consulta preferências e agendamentos anteriores do cliente autenticado.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_opcoes",
            "description": "Busca opções reais de serviço, profissional, preço e horário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "servico": {"type": "string", "description": "Tipo de serviço; vazio aceita todos."},
                    "bairro": {"type": "string", "description": "Bairro preferido; vazio aceita todos."},
                    "orcamento_max": {"type": "number", "description": "Preço máximo em reais; omita se não houver."},
                },
                "required": ["servico", "bairro"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_agendamento",
            "description": "Confirma um agendamento após autorização explícita e usando uma opção já consultada.",
            "parameters": {
                "type": "object",
                "properties": {"opcao_id": {"type": "string"}},
                "required": ["opcao_id"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass(frozen=True)
class Budget:
    max_steps: int = 6
    max_total_tokens: int = 4000
    max_seconds: float = 120.0
    max_cost_usd: float = 0.01
    input_usd_per_million: float = 0.0
    output_usd_per_million: float = 0.0


@dataclass
class AgentState:
    cliente_id: str
    mensagem: str
    confirmacao_explicita: bool
    passos: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    inicio: float = field(default_factory=time.monotonic)
    historico: dict[str, Any] | None = None
    opcoes: list[dict[str, Any]] = field(default_factory=list)
    agendamento: dict[str, Any] | None = None
    trajetoria: list[dict[str, Any]] = field(default_factory=list)
    resposta: str = ""
    motivo_terminacao: str = ""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    content: str | None
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int


class DecisionModel(Protocol):
    name: str

    def next_turn(self, messages: list[dict[str, Any]], state: AgentState) -> ModelTurn: ...


class OpenAIChatModel:
    """Adaptador para qualquer provedor compatível com Chat Completions."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        if OpenAI is None:
            raise ValueError("Instale as dependências com 'pip install -r requirements.txt'.")
        if not api_key:
            raise ValueError("Preencha OPENAI_API_KEY no arquivo .env para chamar a Mistral.")
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.name = model

    def next_turn(self, messages: list[dict[str, Any]], state: AgentState) -> ModelTurn:
        # Técnica: zero-shot com contrato e ferramentas tipadas. É suficiente para
        # esta POC porque os dados factuais vêm da API e não de exemplos no prompt.
        # Contrato: ou chama uma das 3 ferramentas declaradas, ou responde em até
        # 5 frases; proíbe inventar disponibilidade e escrever sem confirmação.
        # Isso impede alucinação de catálogo e agendamento autônomo.
        completion = self.client.chat.completions.create(
            model=self.name,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=600,
        )
        message = completion.choices[0].message
        calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=json.loads(call.function.arguments or "{}"),
            )
            for call in (message.tool_calls or [])
        ]
        usage = completion.usage
        return ModelTurn(
            content=message.content,
            tool_calls=calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


class MockDecisionModel:
    """Modelo determinístico para demonstrar o laço sem consumir uma API LLM."""

    name = "mock-agendeakiai-v1"

    def next_turn(self, messages: list[dict[str, Any]], state: AgentState) -> ModelTurn:
        del messages
        entrada = _sem_acentos(state.mensagem.lower())
        chamadas = {evento.get("ferramenta") for evento in state.trajetoria if evento["tipo"] == "ferramenta"}

        if not _pedido_de_beleza(entrada):
            return self._final(
                "Posso ajudar apenas com descoberta e agendamento de serviços de beleza. "
                "Nenhum agendamento foi solicitado ou realizado."
            )

        if "consultar_historico" not in chamadas:
            return self._call("consultar_historico", {})

        if "buscar_opcoes" not in chamadas:
            return self._call("buscar_opcoes", _extrair_filtros(entrada))

        if state.confirmacao_explicita and not state.agendamento:
            melhor = _melhor_opcao(state.opcoes, entrada)
            if melhor and "confirmar_agendamento" not in chamadas:
                return self._call("confirmar_agendamento", {"opcao_id": melhor["opcaoId"]})

        return self._final(_montar_resposta_mock(state, entrada))

    @staticmethod
    def _call(name: str, arguments: dict[str, Any]) -> ModelTurn:
        payload = json.dumps(arguments, ensure_ascii=False)
        return ModelTurn(None, [ToolCall(f"mock-{name}", name, arguments)], 120, max(12, len(payload) // 4))

    @staticmethod
    def _final(content: str) -> ModelTurn:
        return ModelTurn(content, [], 180, max(20, len(content) // 4))


def _sem_acentos(texto: str) -> str:
    traducao = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    return texto.translate(traducao)


def _pedido_de_beleza(texto: str) -> bool:
    termos = ("cabelo", "corte", "penteado", "maquiagem", "unha", "salao", "beleza")
    return any(termo in texto for termo in termos)


def _extrair_filtros(texto: str) -> dict[str, Any]:
    servico = next((item for item in ("maquiagem", "penteado", "corte") if item in texto), "")
    bairro = next((item for item in ("centro", "moema", "vila mariana") if item in texto), "")
    valor = re.search(r"(?:r\$\s*|ate\s+)(\d+(?:[.,]\d+)?)", texto)
    return {
        "servico": servico,
        "bairro": bairro.title() if bairro else "",
        "orcamento_max": float(valor.group(1).replace(",", ".")) if valor else None,
    }


def _melhor_opcao(opcoes: list[dict[str, Any]], texto: str) -> dict[str, Any] | None:
    if not opcoes:
        return None
    termos = set(texto.split())

    def pontuar(opcao: dict[str, Any]) -> tuple[int, float]:
        atributos = " ".join(opcao.get("ocasioes", []) + opcao.get("estilos", []) + opcao.get("clima", []))
        atributos = _sem_acentos(atributos.lower())
        return sum(termo in atributos for termo in termos), -float(opcao["preco"])

    return max(opcoes, key=pontuar)


def _montar_resposta_mock(state: AgentState, texto: str) -> str:
    if state.agendamento:
        return state.agendamento.get("mensagem", "Agendamento confirmado.")
    if not state.opcoes:
        return "Não encontrei opções com esses filtros. Podemos flexibilizar bairro, serviço ou orçamento; nenhum agendamento foi realizado."

    ordenadas = sorted(
        state.opcoes,
        key=lambda opcao: (opcao != _melhor_opcao(state.opcoes, texto), float(opcao["preco"])),
    )[:3]
    partes = [
        f'{opcao["opcaoId"]}: {opcao["servico"]} com {opcao["profissional"]} no '
        f'{opcao["salao"]}, {opcao["bairro"]}, por R$ {opcao["preco"]:.2f}'
        for opcao in ordenadas
    ]
    historico_falhou = state.historico is not None and not state.historico.get("ok", False)
    prefixo = "Não consegui consultar seu histórico, então usei apenas o pedido atual. " if historico_falhou else ""
    divergencia = "Sua preferência atual foi priorizada sobre o histórico. " if "classico" in texto else ""
    return f"{prefixo}{divergencia}Melhor opção: {'; alternativa: '.join(partes)}. Nenhum agendamento foi realizado."


class Agent:
    def __init__(self, model: DecisionModel, tools: ApiTools, budget: Budget) -> None:
        self.model = model
        self.tools = tools
        self.budget = budget
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def run(self, mensagem: str, cliente_id: str, confirmado: bool = False) -> AgentState:
        state = AgentState(cliente_id=cliente_id, mensagem=mensagem, confirmacao_explicita=confirmado)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {"mensagem": mensagem, "cliente_id": cliente_id, "confirmacao_explicita": confirmado},
                    ensure_ascii=False,
                ),
            },
        ]

        while True:
            limite = self._limite_atingido(state, incluir_passos=True)
            if limite:
                self._terminar(state, limite, "Execução encerrada pelo orçamento de segurança.")
                break

            state.passos += 1
            try:
                turn = self.model.next_turn(messages, state)
            except Exception as exc:  # falha do provedor não deve derrubar sem registro
                self._terminar(state, "erro_modelo", f"Não foi possível consultar o modelo: {exc}")
                state.trajetoria.append({"tipo": "erro_modelo", "passo": state.passos, "erro": str(exc)})
                break

            self._registrar_uso(state, turn.input_tokens, turn.output_tokens)
            state.trajetoria.append(
                {
                    "tipo": "modelo",
                    "passo": state.passos,
                    "modelo": self.model.name,
                    "tool_calls": [asdict(call) for call in turn.tool_calls],
                    "resposta": turn.content,
                    "tokens_entrada": turn.input_tokens,
                    "tokens_saida": turn.output_tokens,
                }
            )

            limite = self._limite_atingido(state, incluir_passos=False)
            if limite:
                self._terminar(state, limite, "Execução encerrada antes de executar outra ferramenta.")
                break

            if not turn.tool_calls:
                self._terminar(state, "resposta_final", turn.content or "O modelo não retornou uma resposta.")
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": turn.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                        }
                        for call in turn.tool_calls
                    ],
                }
            )
            for call in turn.tool_calls:
                result = self._execute_tool(call, state)
                state.trajetoria.append(
                    {
                        "tipo": "ferramenta",
                        "passo": state.passos,
                        "ferramenta": call.name,
                        "argumentos": call.arguments,
                        "resultado": result,
                        "erro": not result.get("ok", False),
                    }
                )
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)}
                )

        state.trajetoria.append(
            {
                "tipo": "terminacao",
                "motivo": state.motivo_terminacao,
                "passos": state.passos,
                "tokens_total": state.tokens_entrada + state.tokens_saida,
                "custo_usd": round(state.custo_usd, 8),
            }
        )
        return state

    def _execute_tool(self, call: ToolCall, state: AgentState) -> dict[str, Any]:
        try:
            if call.name == "consultar_historico":
                result = self.tools.consultar_historico()
                state.historico = result
                return result
            if call.name == "buscar_opcoes":
                result = self.tools.buscar_opcoes(**call.arguments)
                state.opcoes = result.get("opcoes", []) if result.get("ok") else []
                return result
            if call.name == "confirmar_agendamento":
                if not state.confirmacao_explicita:
                    return ApiTools._erro(
                        "CONFIRMACAO_OBRIGATORIA",
                        "O cliente não confirmou a escrita nesta execução.",
                        "Apresente a opção e peça confirmação explícita.",
                    )
                opcao_id = str(call.arguments.get("opcao_id", ""))
                opcao = next((item for item in state.opcoes if item.get("opcaoId") == opcao_id), None)
                if not opcao:
                    return ApiTools._erro(
                        "OPCAO_NAO_CONSULTADA",
                        "A opção não pertence ao resultado da busca desta execução.",
                        "Consulte opções novamente e use um opcaoId retornado.",
                    )
                result = self.tools.confirmar_agendamento(opcao)
                if result.get("ok"):
                    state.agendamento = result
                return result
            return ApiTools._erro("FERRAMENTA_DESCONHECIDA", f"Ferramenta '{call.name}' não existe.")
        except (TypeError, ValueError, KeyError) as exc:
            return ApiTools._erro(
                "ARGUMENTOS_INVALIDOS",
                str(exc),
                "Corrija os argumentos conforme o schema da ferramenta.",
            )

    def _registrar_uso(self, state: AgentState, input_tokens: int, output_tokens: int) -> None:
        state.tokens_entrada += input_tokens
        state.tokens_saida += output_tokens
        state.custo_usd += (
            input_tokens * self.budget.input_usd_per_million
            + output_tokens * self.budget.output_usd_per_million
        ) / 1_000_000

    def _limite_atingido(self, state: AgentState, incluir_passos: bool) -> str | None:
        if incluir_passos and state.passos >= self.budget.max_steps:
            return "limite_passos"
        if state.tokens_entrada + state.tokens_saida >= self.budget.max_total_tokens:
            return "limite_tokens"
        if time.monotonic() - state.inicio >= self.budget.max_seconds:
            return "limite_tempo"
        if state.custo_usd >= self.budget.max_cost_usd:
            return "limite_custo"
        return None

    @staticmethod
    def _terminar(state: AgentState, motivo: str, resposta: str) -> None:
        state.motivo_terminacao = motivo
        state.resposta = resposta


def build_agent(cliente_id: str, use_mock: bool = False, api_url: str = DEFAULT_API_URL) -> Agent:
    load_dotenv()
    if use_mock:
        model: DecisionModel = MockDecisionModel()
        budget = Budget()
    else:
        model = OpenAIChatModel(
            base_url=os.getenv("LLM_BASE_URL", "https://api.mistral.ai/v1"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("LLM_MODELO", "mistral-small-latest"),
        )
        # Preços do Mistral Small em 13/09/2026. O teto de US$ 0,01 evita
        # uma execução descontrolada; revise estes valores se trocar o modelo.
        budget = Budget(input_usd_per_million=0.15, output_usd_per_million=0.60)

    tools = ApiTools(
        base_url=api_url,
        token="token-mock",
        cliente_id=cliente_id,
    )
    return Agent(model, tools, budget)


def state_as_log(state: AgentState, model_name: str) -> dict[str, Any]:
    return {
        "executado_em": datetime.now(timezone.utc).isoformat(),
        "prompt": "agendeakiai-agente-v1",
        "modelo": model_name,
        "entrada": {
            "cliente_id": state.cliente_id,
            "mensagem": state.mensagem,
            "confirmacao_explicita": state.confirmacao_explicita,
        },
        "estado_final": {
            "passos": state.passos,
            "tokens_entrada": state.tokens_entrada,
            "tokens_saida": state.tokens_saida,
            "custo_usd": round(state.custo_usd, 8),
            "motivo_terminacao": state.motivo_terminacao,
            "resposta": state.resposta,
        },
        "trajetoria": state.trajetoria,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agente simples do AgendeAkiAI")
    parser.add_argument("--message", "--mensagem", dest="mensagem", required=True)
    parser.add_argument("--cliente-id", default="cliente-001")
    parser.add_argument("--confirmar", action="store_true", help="Autoriza a escrita do agendamento nesta execução.")
    parser.add_argument("--mock", action="store_true", help="Usa decisões locais e não chama a API da Mistral.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="URL da API tradicional/mock.")
    parser.add_argument("--log", type=Path, help="Arquivo JSON opcional para registrar a execução.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        agent = build_agent(args.cliente_id, args.mock, args.api_url)
        state = agent.run(args.mensagem, args.cliente_id, args.confirmar)
    except (OSError, ValueError) as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 2

    log = state_as_log(state, agent.model.name)
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(state.resposta)
    print(
        f"[terminação={state.motivo_terminacao}; passos={state.passos}; "
        f"tokens={state.tokens_entrada + state.tokens_saida}; custo_usd={state.custo_usd:.8f}]"
    )
    return 0 if state.motivo_terminacao == "resposta_final" else 1


if __name__ == "__main__":
    raise SystemExit(main())
