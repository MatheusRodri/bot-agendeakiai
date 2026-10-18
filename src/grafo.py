"""Grafo síncrono do AgendeAkiAI."""

from __future__ import annotations

import hashlib
import json
import operator
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, TypedDict

# Restringe desserialização de checkpoints locais antes de carregar o saver.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .contratos import EntradaAgente, SaidaAgente
from .memoria import recuperar, registrar
from .recuperacao import buscar_regra, normalizar
from .tools import ApiTools


ROOT = Path(__file__).resolve().parents[1]
CAMINHO_CHECKPOINT = ROOT / "dados" / "checkpoints.sqlite"
MAX_PASSOS = 8
TEMPO_MAXIMO_SEGUNDOS = 30
PRAZO_APROVACAO_MINUTOS = 15


class EstadoAgente(TypedDict, total=False):
    cliente_id: str
    conversa_id: str
    thread_id: str
    texto: str
    aprovar: bool
    passos: int
    iniciado_em: float
    mensagens: list[dict[str, str]]
    eventos: Annotated[list[dict[str, Any]], operator.add]
    historico: dict[str, Any]
    memoria: dict[str, Any]
    opcoes: list[dict[str, Any]]
    fontes: list[str]
    resultado: str
    suficiente: bool
    exige_aprovacao: bool
    decisao: dict[str, Any]
    agendamento: dict[str, Any]
    motivo_terminacao: str
    pendente: bool
    aprovacao_pendente: dict[str, Any]
    prompt_id: str
    prompt_hash: str
    acao_planejada: str


CONEXAO = sqlite3.connect(str(CAMINHO_CHECKPOINT), check_same_thread=False)
CHECKPOINTER = SqliteSaver(CONEXAO)
CHECKPOINTER.setup()


def _normalizar(texto: str) -> str:
    return normalizar(texto)


def _filtros(texto: str) -> dict[str, Any]:
    frase = _normalizar(texto)
    servico = next((item for item in ("maquiagem", "penteado", "corte") if item in frase), "")
    bairro = next((item for item in ("centro", "moema", "vila mariana") if item in frase), "")
    valor = re.search(r"(?:r\$\s*|ate\s+)(\d+(?:[.,]\d+)?)", frase)
    return {"servico": servico, "bairro": bairro.title() if bairro else "", "orcamento_max": float(valor.group(1).replace(",", ".")) if valor else None}


def _eh_pedido_beauty(texto: str) -> bool:
    return any(palavra in _normalizar(texto) for palavra in ("beleza", "cabelo", "corte", "penteado", "maquiagem", "unha", "salao", "arrumar", "evento"))


def _pede_agendamento(texto: str) -> bool:
    frase = _normalizar(texto)
    return any(palavra in frase for palavra in ("confirmo", "quero agendar", "pode reservar", "faca a reserva", "agende para mim"))


def _destino_proxima_acao(estado: EstadoAgente) -> str:
    return estado["acao_planejada"]


def _destino_aprovacao(estado: EstadoAgente) -> str:
    return "registrar_agendamento" if estado.get("decisao", {}).get("aprovada") else "finalizar"


def criar_nos(ferramentas: ApiTools):
    def validar(estado: EstadoAgente) -> dict[str, Any]:
        entrada = EntradaAgente(texto=estado["texto"], cliente_id=estado["cliente_id"], conversa_id=estado["conversa_id"], aprovar=estado.get("aprovar", False))
        arquivo_prompt = ROOT / "src" / "prompts" / "agente-v1.txt"
        prompt = arquivo_prompt.read_bytes()
        return {"texto": entrada.texto, "prompt_id": "agendeakiai-agente-v2", "prompt_hash": hashlib.sha256(prompt).hexdigest(), "passos": 1, "iniciado_em": datetime.now().timestamp(), "mensagens": [{"papel": "cliente", "conteudo": entrada.texto}], "eventos": [{"tipo": "entrada_validada", "texto": entrada.texto}, {"tipo": "prompt_carregado", "id": "agendeakiai-agente-v2", "sha256": hashlib.sha256(prompt).hexdigest()}]}

    def consultar_contexto(estado: EstadoAgente) -> dict[str, Any]:
        historico = ferramentas.consultar_historico(estado["cliente_id"])
        memoria = recuperar(estado["cliente_id"], estado["texto"])
        eventos = [{"tipo": "ferramenta", "ferramenta": "consultar_historico", "argumentos": {"cliente_id": estado["cliente_id"]}, "resultado": historico}, {"tipo": "memoria", "resultado": memoria}]
        return {"historico": historico, "memoria": memoria, "eventos": eventos, "passos": estado.get("passos", 0) + 1}

    def consultar_fontes(estado: EstadoAgente) -> dict[str, Any]:
        texto = estado["texto"]
        frase = _normalizar(texto)
        if any(p in frase for p in ("cancel", "remarc", "taxa", "atras", "reembolso", "doente", "doenca", "alergia", "regra")):
            trechos = buscar_regra(texto)
            pontos = int(trechos[0]["pontos"]) if trechos else 0
            if pontos >= 2 and "alergia" not in frase:
                fonte = trechos[0]
                resultado = f'{fonte["titulo"]}: {fonte["trecho"].splitlines()[-1]}'
                return {"resultado": resultado, "fontes": [f'{fonte["fonte"]}#{fonte["titulo"]}'], "suficiente": True, "opcoes": [], "eventos": [{"tipo": "ferramenta", "ferramenta": "buscar_regra", "argumentos": {"consulta": texto}, "resultado": fonte}], "passos": estado.get("passos", 0) + 1}
            return {"resultado": "Não encontrei uma regra suficiente no corpus para responder com segurança. Procure a operação do AgendeAki.", "fontes": [], "suficiente": False, "opcoes": [], "eventos": [{"tipo": "ferramenta", "ferramenta": "buscar_regra", "argumentos": {"consulta": texto}, "resultado": {"trechos": trechos, "suficiente": False}}], "passos": estado.get("passos", 0) + 1}

        if not _eh_pedido_beauty(texto):
            return {"resultado": "Posso ajudar a encontrar e agendar serviços de beleza. Não realizei nenhum agendamento.", "fontes": [], "suficiente": False, "opcoes": [], "eventos": [{"tipo": "recusa", "motivo": "fora_do_escopo"}], "passos": estado.get("passos", 0) + 1}

        filtros = _filtros(texto)
        if not filtros["servico"]:
            return {"resultado": "Qual serviço você procura: penteado, maquiagem ou corte?", "fontes": ["entrada do cliente"], "suficiente": False, "opcoes": [], "eventos": [{"tipo": "entrada_incompleta", "campos": ["servico"]}], "passos": estado.get("passos", 0) + 1}
        busca = ferramentas.buscar_opcoes(**filtros, cliente_id=estado["cliente_id"])
        opcoes = busca.get("opcoes", []) if busca.get("ok") else []
        preferencias_memoria = estado.get("memoria", {}).get("preferencias", {})
        estilo_salvo = preferencias_memoria.get("estilo", {}).get("valor", "")
        estilos_digitados = ("classico", "moderno", "natural", "discreto", "elegante")
        tem_estilo_atual = any(estilo in _normalizar(texto) and not (estilo == "natural" and "maquiagem natural" in _normalizar(texto)) for estilo in estilos_digitados)
        if estilo_salvo and not tem_estilo_atual:
            opcoes.sort(key=lambda opcao: estilo_salvo not in _normalizar(" ".join(opcao.get("estilos", []))))
        eventos = [{"tipo": "ferramenta", "ferramenta": "buscar_opcoes", "argumentos": {**filtros, "cliente_id": estado["cliente_id"]}, "resultado": busca}]
        if not busca.get("ok"):
            return {"resultado": "Não consegui consultar a disponibilidade agora. Nenhum agendamento foi feito.", "fontes": ["buscar_opcoes"], "suficiente": False, "opcoes": [], "eventos": eventos, "passos": estado.get("passos", 0) + 1}
        if not filtros["bairro"] and len(opcoes) > 1:
            bairros = sorted({opcao["bairro"] for opcao in opcoes})
            return {"resultado": f"Encontrei opções em {', '.join(bairros)}. Qual bairro prefere?", "fontes": ["API mock: catálogo de opções"], "suficiente": False, "opcoes": opcoes, "eventos": eventos + [{"tipo": "entrada_ambigua", "campo": "bairro", "opcoes": bairros}], "passos": estado.get("passos", 0) + 1}
        if not opcoes:
            return {"resultado": "Não encontrei opções para esses filtros. Podemos ajustar bairro ou orçamento; nenhum agendamento foi realizado.", "fontes": ["API mock: catálogo de opções"], "suficiente": True, "opcoes": [], "eventos": eventos, "passos": estado.get("passos", 0) + 1}
        opcoes_texto = "; ".join(f'{o["opcaoId"]}: {o["servico"]} com {o["profissional"]}, {o["bairro"]}, {o["dataHoraInicio"]}, R$ {o["preco"]:.2f}' for o in opcoes[:3])
        estilo_historico = estado.get("historico", {}).get("cliente", {}).get("preferencias", {}).get("estilo", estilo_salvo)
        estilo_atual = next((item for item in estilos_digitados if item in _normalizar(texto) and not (item == "natural" and "maquiagem natural" in _normalizar(texto))), "")
        prefixo = "Sua preferência atual foi priorizada sobre o histórico. " if estilo_atual and estilo_historico and estilo_atual != _normalizar(estilo_historico) else ""
        resultado = f"{prefixo}Opções: {opcoes_texto}. Nenhum agendamento foi realizado."
        pedir = _pede_agendamento(texto)
        return {"resultado": resultado, "fontes": ["API mock: catálogo de opções"], "suficiente": True, "opcoes": opcoes, "exige_aprovacao": pedir, "eventos": eventos, "passos": estado.get("passos", 0) + 1}

    def decidir_proxima_acao(estado: EstadoAgente) -> dict[str, Any]:
        if estado.get("passos", 0) >= MAX_PASSOS:
            acao = "finalizar"
            retorno = {"resultado": "A execução atingiu o limite de passos e foi encerrada sem nova ação.", "fontes": [], "suficiente": False, "motivo_terminacao": "limite_de_passos"}
        elif "resultado" not in estado:
            acao = "consultar_fontes"
            retorno = {}
        elif estado.get("exige_aprovacao"):
            acao = "preparar_aprovacao"
            retorno = {}
        else:
            acao = "finalizar"
            retorno = {}
        return {**retorno, "acao_planejada": acao, "eventos": [{"tipo": "roteamento", "proxima_acao": acao}]}

    def preparar_aprovacao(estado: EstadoAgente) -> dict[str, Any]:
        melhor = estado["opcoes"][0]
        expira_em = (datetime.now(timezone.utc) + timedelta(minutes=PRAZO_APROVACAO_MINUTOS)).isoformat()
        apresentacao = {"acao": "criar_agendamento", "opcao_id": melhor["opcaoId"], "servico": melhor["servico"], "profissional": melhor["profissional"], "horario": melhor["dataHoraInicio"], "preco": melhor["preco"], "opcoes_consultadas": [o["opcaoId"] for o in estado["opcoes"]], "alternativas_consultadas": [{"opcao_id": o["opcaoId"], "servico": o["servico"], "profissional": o["profissional"], "horario": o["dataHoraInicio"], "preco": o["preco"]} for o in estado["opcoes"]], "expira_em": expira_em}
        return {"aprovacao_pendente": apresentacao, "passos": estado.get("passos", 0) + 1}

    def aprovacao(estado: EstadoAgente) -> dict[str, Any]:
        apresentacao = estado["aprovacao_pendente"]
        melhor = next(o for o in estado["opcoes"] if o["opcaoId"] == apresentacao["opcao_id"])
        decisao = interrupt(apresentacao)
        prazo = datetime.fromisoformat(apresentacao["expira_em"])
        expirou = datetime.now(timezone.utc) > prazo
        if expirou:
            decisao = {"acao": "rejeitar", "motivo": "aprovacao_expirada"}
        if isinstance(decisao, str):
            decisao = {"acao": decisao}
        acao = decisao.get("acao", "rejeitar")
        if acao == "editar":
            nova_id = decisao.get("opcao_id")
            if nova_id not in apresentacao["opcoes_consultadas"]:
                acao = "rejeitar"
            else:
                melhor = next(o for o in estado["opcoes"] if o["opcaoId"] == nova_id)
        aprovada = acao in ("aprovar", "editar")
        eventos = [{"tipo": "aprovacao_humana", "decisao": acao, "motivo": "aprovacao_expirada" if expirou else decisao.get("motivo", ""), "opcao_id": melhor["opcaoId"], "expira_em": apresentacao["expira_em"]}]
        if not aprovada:
            resultado = "A aprovação foi rejeitada ou expirou. Nenhum agendamento foi realizado."
        else:
            resultado = estado["resultado"]
        return {"decisao": {"aprovada": aprovada, "opcao": melhor, "acao": acao}, "resultado": resultado, "pendente": False, "eventos": eventos, "passos": estado.get("passos", 0) + 1}

    def agendar(estado: EstadoAgente) -> dict[str, Any]:
        opcao = estado["decisao"]["opcao"]
        partes = [estado["cliente_id"], opcao["opcaoId"], opcao["dataHoraInicio"]]
        chave = hashlib.sha256("|".join(partes).encode()).hexdigest()
        resultado = ferramentas.confirmar_agendamento(opcao, chave, estado["cliente_id"])
        ok = resultado.get("ok", False)
        corpo = resultado.get("agendamento", {})
        resposta = resultado.get("mensagem", "Não foi possível registrar o agendamento.") if ok else "A opção não pôde ser confirmada. Busque novamente; nenhum agendamento foi registrado."
        return {"agendamento": corpo if ok else {}, "resultado": resposta, "suficiente": ok, "eventos": [{"tipo": "ferramenta", "ferramenta": "confirmar_agendamento", "argumentos": {"cliente_id": estado["cliente_id"], "opcao_id": opcao["opcaoId"], "chave_idempotencia": chave}, "resultado": resultado}], "passos": estado.get("passos", 0) + 1}

    def finalizar(estado: EstadoAgente) -> dict[str, Any]:
        eventos = []
        if os.getenv("MODO", "mock").lower() == "gemini":
            try:
                from .modelo import responder_com_gemini
                saida, uso = responder_com_gemini(estado["texto"], estado["resultado"], estado.get("fontes", []), estado.get("suficiente", False))
                estado["resultado"] = saida["resultado"]
                eventos.append({"tipo": "modelo", "nome": os.getenv("LLM_MODELO") or "gemini-3.8-flash", **uso})
            except Exception as erro:
                eventos.append({"tipo": "modelo", "erro": str(erro), "resposta_base_preservada": True})
        registrar(estado["cliente_id"], estado["texto"])
        evento_aprovacao = next((evento for evento in estado.get("eventos", []) if evento.get("tipo") == "aprovacao_humana"), {})
        motivo = "agendamento_confirmado" if estado.get("agendamento") else evento_aprovacao.get("motivo") or ("aprovacao_rejeitada" if evento_aprovacao else "resposta_final")
        if estado.get("passos", 0) >= MAX_PASSOS:
            motivo = "limite_de_passos"
        elif datetime.now().timestamp() - estado.get("iniciado_em", datetime.now().timestamp()) > TEMPO_MAXIMO_SEGUNDOS:
            motivo = "limite_de_tempo"
        return {"motivo_terminacao": motivo, "eventos": eventos + [{"tipo": "fim", "motivo": motivo}]}

    return validar, consultar_contexto, consultar_fontes, decidir_proxima_acao, preparar_aprovacao, aprovacao, agendar, finalizar


def montar_grafo(ferramentas: ApiTools):
    validar, consultar_contexto, consultar_fontes, decidir_proxima_acao, preparar_aprovacao, aprovacao, agendar, finalizar = criar_nos(ferramentas)
    fluxo = StateGraph(EstadoAgente)
    fluxo.add_node("validar_entrada", validar)
    fluxo.add_node("consultar_contexto", consultar_contexto)
    fluxo.add_node("consultar_fontes", consultar_fontes)
    fluxo.add_node("decidir_proxima_acao", decidir_proxima_acao)
    fluxo.add_node("preparar_aprovacao", preparar_aprovacao)
    fluxo.add_node("aprovar_agendamento", aprovacao)
    fluxo.add_node("registrar_agendamento", agendar)
    fluxo.add_node("finalizar", finalizar)
    fluxo.add_edge(START, "validar_entrada")
    fluxo.add_edge("validar_entrada", "consultar_contexto")
    fluxo.add_edge("consultar_contexto", "decidir_proxima_acao")
    fluxo.add_conditional_edges("decidir_proxima_acao", _destino_proxima_acao, {"consultar_fontes": "consultar_fontes", "preparar_aprovacao": "preparar_aprovacao", "finalizar": "finalizar"})
    fluxo.add_edge("consultar_fontes", "decidir_proxima_acao")
    fluxo.add_edge("preparar_aprovacao", "aprovar_agendamento")
    fluxo.add_conditional_edges("aprovar_agendamento", _destino_aprovacao, {"registrar_agendamento": "registrar_agendamento", "finalizar": "finalizar"})
    fluxo.add_edge("registrar_agendamento", "finalizar")
    fluxo.add_edge("finalizar", END)
    return fluxo.compile(checkpointer=CHECKPOINTER)


def executar(entrada: EntradaAgente, ferramentas: ApiTools, aprovar: bool | dict[str, Any] | None = None) -> dict[str, Any]:
    global _GRAFO_CACHE
    if ferramentas.base_url not in _GRAFO_CACHE:
        _GRAFO_CACHE[ferramentas.base_url] = montar_grafo(ferramentas)
    grafo = _GRAFO_CACHE[ferramentas.base_url]
    thread_id = entrada.conversa_id
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": MAX_PASSOS + 4}
    if aprovar is not None:
        decisao = aprovar if isinstance(aprovar, dict) else {"acao": "aprovar" if aprovar else "rejeitar"}
        return grafo.invoke(Command(resume=decisao), config)
    return grafo.invoke({"cliente_id": entrada.cliente_id, "conversa_id": entrada.conversa_id, "thread_id": thread_id, "texto": entrada.texto, "aprovar": entrada.aprovar, "eventos": []}, config)


def saida_validada(estado: dict[str, Any]) -> dict[str, Any]:
    return SaidaAgente(resultado=estado.get("resultado", ""), fontes=estado.get("fontes", []), suficiente=estado.get("suficiente", False)).model_dump()


_GRAFO_CACHE: dict[str, Any] = {}
URL_API_PADRAO = os.getenv("API_BASE_URL") or "http://127.0.0.1:8765"
GRAFO = montar_grafo(ApiTools(URL_API_PADRAO, "token-mock"))
_GRAFO_CACHE[URL_API_PADRAO] = GRAFO
