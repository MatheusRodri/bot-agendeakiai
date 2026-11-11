"""Interface de linha de comando para o agente síncrono."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from .agendeaki_api import AgendeAkiApiTools, autenticar_cliente
from .contratos import EntradaAgente
from .grafo import executar, saida_validada
from .tools import ApiTools


def _ler_coordenada(rotulo: str, valor: float | None) -> float:
    texto = str(valor) if valor is not None else input(f"{rotulo}: ").strip()
    try:
        return float(texto.replace(",", "."))
    except ValueError as erro:
        raise ValueError(f"Informe um valor numérico válido para {rotulo.lower()}.") from erro


def _sessao_agendeaki(args: argparse.Namespace, data: str) -> AgendeAkiApiTools:
    base_url = args.api_base_url or os.getenv("API_BASE_URL") or "http://127.0.0.1:3001"
    latitude = _ler_coordenada("Latitude", args.latitude)
    longitude = _ler_coordenada("Longitude", args.longitude)
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Latitude ou longitude fora do intervalo permitido.")
    email = os.getenv("CLIENTE_EMAIL") or input("E-mail do cliente: ").strip()
    senha = os.getenv("CLIENTE_SENHA") or getpass("Senha do cliente: ")
    token, usuario = autenticar_cliente(base_url, email, senha)
    del senha
    return AgendeAkiApiTools(base_url=base_url, token=token, cliente_id=str(usuario["id"]), latitude=latitude, longitude=longitude, raio_km=args.raio_km, data=data)


def _rodar_chat(args: argparse.Namespace) -> int:
    """Modo conversa: o cliente digita, o agente responde, até 'sair'."""
    from .conversa import Conversa
    from .salao_simulado import SalaoSimulado

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ferramentas: AgendeAkiApiTools | SalaoSimulado | None = None
    try:
        if args.backend == "agendeaki":
            ferramentas = _sessao_agendeaki(args, data="")
            cliente_id = ferramentas.cliente_id
        else:
            ferramentas = SalaoSimulado()
            cliente_id = args.cliente_id or "cliente-simulado"
        conversa = Conversa(ferramentas, cliente_id, args.conversa_id)
        origem = "backend AgendeAki" if args.backend == "agendeaki" else "salão simulado"
        print(f"AgendeAkiAI — modo conversa ({origem}). Agendo só quando você pedir explicitamente. Digite 'sair' para encerrar.")
        while True:
            try:
                texto = input("\nVocê: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if normalizar_comando(texto) in {"sair", "exit", "tchau"}:
                break
            if not texto:
                continue
            resposta = conversa.responder(texto)
            print(f"\nAgendeAki: {resposta['resultado']}")
        print("Conversa encerrada.")
        return 0
    except (ValueError, OSError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2
    finally:
        if isinstance(ferramentas, AgendeAkiApiTools):
            ferramentas.encerrar_sessao()


def normalizar_comando(texto: str) -> str:
    return texto.strip().lower().rstrip(".!")


def main() -> int:
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    parser = argparse.ArgumentParser(description="Agente de recomendação e agendamento AgendeAkiAI")
    parser.add_argument("--backend", choices=("mock", "agendeaki"), default="mock", help="API simulada ou backend real do AgendeAki")
    parser.add_argument("--api-base-url", help="URL base da API; padrão localhost:8765 no mock ou localhost:3001 no AgendeAki")
    parser.add_argument("--cliente-id", help="Obrigatório no mock; no AgendeAki é obtido após login")
    parser.add_argument("--latitude", type=float, default=os.getenv("LATITUDE"), help="Latitude; pode vir do .env")
    parser.add_argument("--longitude", type=float, default=os.getenv("LONGITUDE"), help="Longitude; pode vir do .env")
    parser.add_argument("--raio-km", type=int, choices=(0, 1, 5, 10), default=int(os.getenv("RAIO_KM", "5")))
    parser.add_argument("--data", default=os.getenv("DATA_BUSCA"), help="Data da busca em AAAA-MM-DD; pode vir do .env")
    parser.add_argument("--conversa-id", default="conversa-local")
    parser.add_argument("--message", default="")
    parser.add_argument("--retomar", choices=("aprovar", "rejeitar"))
    parser.add_argument("--editar-opcao-id", default="")
    parser.add_argument("--chat", action="store_true", help="modo conversa: ocasião, recomendação, dia/horário e agendamento quando pedido explicitamente")
    args = parser.parse_args()
    if args.chat:
        return _rodar_chat(args)
    ferramentas: ApiTools | AgendeAkiApiTools | None = None

    try:
        if args.backend == "agendeaki":
            if args.retomar or args.editar_opcao_id:
                parser.error("Retomada/aprovação não está habilitada no backend real neste modo; use --chat.")
            data_busca = args.data or input("Data da busca (AAAA-MM-DD): ").strip()
            date.fromisoformat(data_busca)
            ferramentas = _sessao_agendeaki(args, data_busca)
            cliente_id = ferramentas.cliente_id
        else:
            if not args.cliente_id:
                parser.error("--cliente-id é obrigatório quando --backend=mock.")
            base_url = args.api_base_url or os.getenv("API_BASE_URL") or "http://127.0.0.1:8765"
            ferramentas = ApiTools(base_url, "token-mock", args.cliente_id)
            cliente_id = args.cliente_id

        if args.retomar or args.editar_opcao_id:
            decisao = {"acao": "editar", "opcao_id": args.editar_opcao_id} if args.editar_opcao_id else args.retomar == "aprovar"
            estado = executar(EntradaAgente(texto="retomada", cliente_id=cliente_id, conversa_id=args.conversa_id), ferramentas, decisao)
        else:
            entrada = EntradaAgente(texto=args.message, cliente_id=cliente_id, conversa_id=args.conversa_id)
            estado = executar(entrada, ferramentas)
        print(json.dumps(saida_validada(estado), ensure_ascii=False, indent=2))
        if args.backend == "agendeaki":
            for evento in estado.get("eventos", []):
                resultado_ferramenta = evento.get("resultado", {})
                erro_api = resultado_ferramenta.get("erro", {}) if isinstance(resultado_ferramenta, dict) else {}
                if evento.get("ferramenta") == "buscar_opcoes" and erro_api:
                    codigo = erro_api.get("codigo", "ERRO_API")
                    mensagem = erro_api.get("mensagem", "A API recusou a consulta.")
                    metodo = erro_api.get("metodo", "")
                    endpoint = erro_api.get("endpoint", "")
                    rota = f" ({metodo} {endpoint})" if metodo and endpoint else ""
                    print(f"Diagnóstico da API{rota}: {codigo}: {mensagem}", file=sys.stderr)
                elif evento.get("ferramenta") == "buscar_opcoes" and isinstance(resultado_ferramenta, dict):
                    diagnostico = resultado_ferramenta.get("diagnostico", {})
                    if resultado_ferramenta.get("ok") and not resultado_ferramenta.get("opcoes") and diagnostico:
                        print(
                            "Diagnóstico da busca: "
                            f"salões no raio={diagnostico.get('saloes_no_raio', 0)}, "
                            f"serviços compatíveis={diagnostico.get('servicos_compativeis', 0)}, "
                            f"com profissionais={diagnostico.get('servicos_com_profissionais', 0)}, "
                            f"horários encontrados={diagnostico.get('horarios_encontrados', 0)}.",
                            file=sys.stderr,
                        )
        print(f"[thread_id={args.conversa_id}; motivo={estado.get('motivo_terminacao', 'aguardando_aprovacao')}; passos={estado.get('passos', 0)}]")
        return 0
    except (ValueError, OSError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2
    finally:
        if isinstance(ferramentas, AgendeAkiApiTools):
            ferramentas.encerrar_sessao()


if __name__ == "__main__":
    raise SystemExit(main())
