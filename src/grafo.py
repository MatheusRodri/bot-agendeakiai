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

from opentelemetry.trace import Status, StatusCode
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .contratos import EntradaAgente, SaidaAgente
from .controles import validar_saida_modelo, verificar_escrita
from .memoria import recuperar, registrar
from .recuperacao import buscar_regra, normalizar
from .telemetria import TRACER, json_curto
from .tools import ApiTools
from .versao import VERSAO_SISTEMA


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


def _executar_ferramenta(nome: str, funcao, **argumentos):
    """Abre o span execute_tool <nome> (convenção GenAI) em volta da chamada."""
    with TRACER.start_as_current_span(f"execute_tool {nome}") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", nome)
        span.set_attribute("gen_ai.tool.call.arguments", json_curto(argumentos))
        resultado = funcao(**argumentos)
        span.set_attribute("gen_ai.tool.call.result", json_curto(resultado))
        ok = resultado.get("ok", True) if isinstance(resultado, dict) else True
        span.set_attribute("ferramenta.ok", bool(ok))
        if not ok:
            span.set_status(Status(StatusCode.ERROR))
        return resultado


def criar_nos(ferramentas: ApiTools):
    fonte_catalogo = getattr(ferramentas, "fonte_catalogo", "API mock: catálogo de opções")

    def validar(estado: EstadoAgente) -> dict[str, Any]:
        entrada = EntradaAgente(texto=estado["texto"], cliente_id=estado["cliente_id"], conversa_id=estado["conversa_id"], aprovar=estado.get("aprovar", False))
        arquivo_prompt = ROOT / "src" / "prompts" / "agente-v1.txt"
        prompt = arquivo_prompt.read_bytes()
        return {"texto": entrada.texto, "prompt_id": "agendeakiai-agente-v2", "prompt_hash": hashlib.sha256(prompt).hexdigest(), "passos": 1, "iniciado_em": datetime.now().timestamp(), "mensagens": [{"papel": "cliente", "conteudo": entrada.texto}], "eventos": [{"tipo": "entrada_validada", "texto": entrada.texto}, {"tipo": "prompt_carregado", "id": "agendeakiai-agente-v2", "sha256": hashlib.sha256(prompt).hexdigest()}]}

    def consultar_contexto(estado: EstadoAgente) -> dict[str, Any]:
        historico = _executar_ferramenta("consultar_historico", ferramentas.consultar_historico, cliente_id=estado["cliente_id"])
        memoria = recuperar(estado["cliente_id"], estado["texto"]) if getattr(ferramentas, "usar_memoria_local", True) else {"preferencias": {}, "episodios": []}
        eventos = [{"tipo": "ferramenta", "ferramenta": "consultar_historico", "argumentos": {"cliente_id": estado["cliente_id"]}, "resultado": historico}, {"tipo": "memoria", "resultado": memoria}]
        return {"historico": historico, "memoria": memoria, "eventos": eventos, "passos": estado.get("passos", 0) + 1}

    def consultar_fontes(estado: EstadoAgente) -> dict[str, Any]:
        texto = estado["texto"]
        frase = _normalizar(texto)
        if any(p in frase for p in ("cancel", "remarc", "taxa", "atras", "reembolso", "doente", "doenca", "alergia", "regra")):
            trechos = _executar_ferramenta("buscar_regra", buscar_regra, pergunta=texto)
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
        busca = _executar_ferramenta("buscar_opcoes", ferramentas.buscar_opcoes, **filtros, cliente_id=estado["cliente_id"])
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
            return {"resultado": f"Encontrei opções em {', '.join(bairros)}. Qual bairro prefere?", "fontes": [fonte_catalogo], "suficiente": False, "opcoes": opcoes, "eventos": eventos + [{"tipo": "entrada_ambigua", "campo": "bairro", "opcoes": bairros}], "passos": estado.get("passos", 0) + 1}
        if not opcoes:
            return {"resultado": "Não encontrei opções para esses filtros. Podemos ajustar bairro ou orçamento; nenhum agendamento foi realizado.", "fontes": [fonte_catalogo], "suficiente": True, "opcoes": [], "eventos": eventos, "passos": estado.get("passos", 0) + 1}
        opcoes_texto = "; ".join(f'{o["opcaoId"]}: {o["servico"]} com {o["profissional"]}, {o["bairro"]}, {o["dataHoraInicio"]}, R$ {o["preco"]:.2f}' for o in opcoes[:3])
        estilo_historico = estado.get("historico", {}).get("cliente", {}).get("preferencias", {}).get("estilo", estilo_salvo)
        estilo_atual = next((item for item in estilos_digitados if item in _normalizar(texto) and not (item == "natural" and "maquiagem natural" in _normalizar(texto))), "")
        prefixo = "Sua preferência atual foi priorizada sobre o histórico. " if estilo_atual and estilo_historico and estilo_atual != _normalizar(estilo_historico) else ""
        resultado = f"{prefixo}Opções: {opcoes_texto}. Nenhum agendamento foi realizado."
        pedir = _pede_agendamento(texto)
        return {"resultado": resultado, "fontes": [fonte_catalogo], "suficiente": True, "opcoes": opcoes, "exige_aprovacao": pedir, "eventos": eventos, "passos": estado.get("passos", 0) + 1}

    def decidir_proxima_acao(estado: EstadoAgente) -> dict[str, Any]:
        if estado.get("passos", 0) >= MAX_PASSOS:
            acao = "finalizar"
            retorno = {"resultado": "A execução atingiu o limite de passos e foi encerrada sem nova ação.", "fontes": [], "suficiente": False, "motivo_terminacao": "limite_de_passos"}
        elif "resultado" not in estado:
            acao = "consultar_fontes"
            retorno = {}
        elif estado.get("exige_aprovacao") and getattr(ferramentas, "allow_booking", True):
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
        bloqueio = verificar_escrita(estado)
        if bloqueio:  # fail-closed: sem a ferramenta, nada é escrito
            return {"resultado": "A escrita foi bloqueada por um controle de segurança. Nenhum agendamento foi realizado.", "suficiente": False, "eventos": [{"tipo": "escrita_bloqueada", "motivo": bloqueio}], "passos": estado.get("passos", 0) + 1}
        opcao = estado["decisao"]["opcao"]
        partes = [estado["cliente_id"], opcao["opcaoId"], opcao["dataHoraInicio"]]
        chave = hashlib.sha256("|".join(partes).encode()).hexdigest()
        resultado = _executar_ferramenta("confirmar_agendamento", ferramentas.confirmar_agendamento, opcao=opcao, chave_idempotencia=chave, cliente_id=estado["cliente_id"])
        ok = resultado.get("ok", False)
        corpo = resultado.get("agendamento", {})
        resposta = resultado.get("mensagem", "Não foi possível registrar o agendamento.") if ok else "A opção não pôde ser confirmada. Busque novamente; nenhum agendamento foi registrado."
        return {"agendamento": corpo if ok else {}, "resultado": resposta, "suficiente": ok, "eventos": [{"tipo": "ferramenta", "ferramenta": "confirmar_agendamento", "argumentos": {"cliente_id": estado["cliente_id"], "opcao_id": opcao["opcaoId"], "chave_idempotencia": chave}, "resultado": resultado}], "passos": estado.get("passos", 0) + 1}

    def finalizar(estado: EstadoAgente) -> dict[str, Any]:
        eventos = []
        resultado_modelo = None
        if os.getenv("MODO", "mock").lower() == "gemini":
            try:
                from .modelo import responder_com_gemini
                nome_modelo = os.getenv("LLM_MODELO") or "gemini-3.8-flash"
                with TRACER.start_as_current_span(f"chat {nome_modelo}") as span_chat:
                    span_chat.set_attribute("gen_ai.operation.name", "chat")
                    span_chat.set_attribute("gen_ai.request.model", nome_modelo)
                    saida, uso = responder_com_gemini(estado["texto"], estado["resultado"], estado.get("fontes", []), estado.get("suficiente", False))
                    span_chat.set_attribute("gen_ai.usage.input_tokens", uso["tokens_entrada"])
                    span_chat.set_attribute("gen_ai.usage.output_tokens", uso["tokens_saida"])
                    span_chat.set_attribute("custo_usd", uso["custo_usd"])
                eventos.append({"tipo": "modelo", "nome": os.getenv("LLM_MODELO") or "gemini-3.8-flash", **uso})
                rejeicao = validar_saida_modelo(estado["resultado"], saida["resultado"], bool(estado.get("agendamento")))
                if rejeicao:  # fail-closed: mantém a resposta verificada pelo código
                    eventos.append({"tipo": "saida_modelo_rejeitada", "motivo": rejeicao})
                else:
                    resultado_modelo = saida["resultado"]
            except Exception as erro:
                eventos.append({"tipo": "modelo", "erro": str(erro), "resposta_base_preservada": True})
        if getattr(ferramentas, "usar_memoria_local", True):
            bloqueio = registrar(estado["cliente_id"], estado["texto"])
            if bloqueio:
                eventos.append({"tipo": "memoria_bloqueada", "motivo": bloqueio})
        evento_aprovacao = next((evento for evento in estado.get("eventos", []) if evento.get("tipo") == "aprovacao_humana"), {})
        motivo = "agendamento_confirmado" if estado.get("agendamento") else evento_aprovacao.get("motivo") or ("aprovacao_rejeitada" if evento_aprovacao else "resposta_final")
        if any(evento.get("tipo") == "escrita_bloqueada" for evento in estado.get("eventos", [])):
            motivo = "escrita_bloqueada"
        if estado.get("passos", 0) >= MAX_PASSOS:
            motivo = "limite_de_passos"
        elif datetime.now().timestamp() - estado.get("iniciado_em", datetime.now().timestamp()) > TEMPO_MAXIMO_SEGUNDOS:
            motivo = "limite_de_tempo"
        retorno = {"motivo_terminacao": motivo, "eventos": eventos + [{"tipo": "fim", "motivo": motivo}]}
        if resultado_modelo is not None:
            retorno["resultado"] = resultado_modelo
        return retorno

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
    checkpointer = CHECKPOINTER if getattr(ferramentas, "persistir_checkpoint", True) else None
    return fluxo.compile(checkpointer=checkpointer)


def executar(entrada: EntradaAgente, ferramentas: ApiTools, aprovar: bool | dict[str, Any] | None = None) -> dict[str, Any]:
    """Abre o span raiz invoke_agent e registra os atributos da decisão (§2.3 e §4.2)."""
    with TRACER.start_as_current_span("invoke_agent agendeakiai") as raiz:
        raiz.set_attribute("gen_ai.operation.name", "invoke_agent")
        raiz.set_attribute("gen_ai.agent.name", "agendeakiai")
        raiz.set_attribute("sistema.versao", VERSAO_SISTEMA)
        raiz.set_attribute("conversa_id", entrada.conversa_id)
        raiz.set_attribute("cliente_id", entrada.cliente_id)
        raiz.set_attribute("entrada", entrada.texto)
        raiz.set_attribute("retomada", aprovar is not None)
        try:
            estado = _invocar(entrada, ferramentas, aprovar)
        except Exception as erro:
            raiz.set_attribute("motivo_termino", "erro")
            raiz.set_attribute("erro", str(erro)[:300])
            raise
        interrompido = bool(estado.get("__interrupt__"))
        motivo = "aguardando_humano" if interrompido else estado.get("motivo_terminacao", "erro")
        raiz.set_attribute("motivo_termino", motivo)
        raiz.set_attribute("prompt.id", estado.get("prompt_id", ""))
        raiz.set_attribute("prompt.sha256", estado.get("prompt_hash", ""))
        raiz.set_attribute("contexto_recuperado", json_curto(estado.get("fontes", [])))
        raiz.set_attribute("saida", estado.get("resultado", ""))
        aprovacao_humana = [e for e in estado.get("eventos", []) if e.get("tipo") == "aprovacao_humana"]
        if aprovacao_humana:
            raiz.set_attribute("aprovacao_humana", json_curto({**aprovacao_humana[-1], "aprovador": entrada.cliente_id, "quando": datetime.now(timezone.utc).isoformat()}))
        return estado


def _invocar(entrada: EntradaAgente, ferramentas: ApiTools, aprovar: bool | dict[str, Any] | None = None) -> dict[str, Any]:
    global _GRAFO_CACHE
    chave_cache = (type(ferramentas), ferramentas.base_url)
    if chave_cache not in _GRAFO_CACHE:
        _GRAFO_CACHE[chave_cache] = montar_grafo(ferramentas)
    grafo = _GRAFO_CACHE[chave_cache]
    thread_id = entrada.conversa_id
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": MAX_PASSOS + 4}
    if aprovar is not None:
        decisao = aprovar if isinstance(aprovar, dict) else {"acao": "aprovar" if aprovar else "rejeitar"}
        return grafo.invoke(Command(resume=decisao), config)
    return grafo.invoke({"cliente_id": entrada.cliente_id, "conversa_id": entrada.conversa_id, "thread_id": thread_id, "texto": entrada.texto, "aprovar": entrada.aprovar, "eventos": []}, config)


def saida_validada(estado: dict[str, Any]) -> dict[str, Any]:
    return SaidaAgente(resultado=estado.get("resultado", ""), fontes=estado.get("fontes", []), suficiente=estado.get("suficiente", False)).model_dump()


_GRAFO_CACHE: dict[tuple[type, str], Any] = {}
URL_API_PADRAO = os.getenv("API_BASE_URL") or "http://127.0.0.1:8765"
GRAFO = montar_grafo(ApiTools(URL_API_PADRAO, "token-mock"))
_GRAFO_CACHE[(ApiTools, URL_API_PADRAO)] = GRAFO
