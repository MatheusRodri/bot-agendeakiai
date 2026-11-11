"""Modo conversa: ocasião → salão mais próximo → serviços recomendados → dia e
horário → agendamento, só quando o próprio cliente pede explicitamente.

Diferente do grafo (um comando por execução), a conversa guarda estado entre os
turnos. O modelo só escolhe serviços do catálogo (controle 3b) e redige o motivo
(controle 3); data, horário, preço e escrita ficam com o código (controle 5).
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from opentelemetry.trace import Status, StatusCode

from .controles import pedido_explicito_de_agendamento, validar_recomendacao, validar_saida_modelo, verificar_escrita_conversa
from .recuperacao import buscar_regra, normalizar
from .telemetria import TRACER, json_curto
from .versao import VERSAO_SISTEMA

FUSO = ZoneInfo("America/Sao_Paulo")
JANELA_DIAS = 60
MAX_SERVICOS = 3
MAX_HORARIOS_LISTADOS = 8
MAX_ESPERA_MINUTOS = 30  # folga entre um serviço e o próximo (o backend gera horários na grade de cada serviço)
MARGEM_COMPROMISSO_MINUTOS = 60  # terminar pelo menos 1 h antes do compromisso, para dar tempo de chegar
PALAVRAS_COMPROMISSO = (
    "reuniao", "entrevista", "casamento", "formatura", "festa", "evento", "jantar", "aniversario", "encontro",
    "batizado", "noivado", "apresentacao", "compromisso", "cerimonia", "palestra",
)
# "corte às 10h", "pode agendar às 14h": a hora é do atendimento, não do compromisso
HORA_DO_ATENDIMENTO = re.compile(r"\b(?:agend\w*|marc\w*|reserv\w*|horario|atendimento|cort\w*|barba|unhas?|manicure|servico\w*)\b[^.,;!?]{0,25}?\b(?:as|para as|pras|a partir das)\s+\d")
MENSAGEM_SUSPENSO = "O serviço está temporariamente suspenso. Procure a operação do AgendeAki. Nenhum agendamento foi realizado."
NENHUM = "Nenhum agendamento foi realizado."

PALAVRAS_REGRA = ("cancel", "remarc", "taxa", "atras", "reembolso", "doente", "doenca", "alergia", "regra")
PALAVRAS_PEDIDO = (
    "beleza", "cabelo", "corte", "cortar", "penteado", "maquiagem", "unha", "barba", "salao", "arrumar", "visual",
    "produzir", "manicure", "pedicure", "sobrancelha", "escova", "evento", "reuniao", "entrevista", "casamento",
    "formatura", "festa", "aniversario", "encontro", "batizado", "noivado", "jantar", "apresentacao", "viagem",
)
PALAVRAS_FORMAIS = (
    "reuniao", "cliente", "alto padrao", "entrevista", "casamento", "formatura", "noivado", "batizado", "apresentacao",
    "evento", "festa", "jantar", "importante", "formal", "elegante", "premium",
)
# palavra no texto do cliente → trechos procurados no nome do serviço
SINONIMOS = {
    "cabelo": ("corte", "cabelo"), "cortar": ("corte",), "corte": ("corte",), "barba": ("barba",),
    "unha": ("unha", "manicure", "pedicure"), "manicure": ("manicure",), "pedicure": ("pedicure",),
    "sobrancelha": ("sobrancelha",), "maquiagem": ("maquiagem",), "penteado": ("penteado",), "escova": ("escova",),
}
PRIORIDADE_GRUPOS = ("corte", "cabelo", "escova", "penteado", "barba", "maquiagem", "sobrancelha", "manicure", "unha", "pedicure")
# tipos de serviço de cabelo: sem citação do cliente, as regras escolhem só um deles
GRUPOS_CABELO = {"corte", "cabelo", "escova", "penteado", "progressiva", "hidratacao", "coloracao", "mechas", "luzes", "alisamento"}
DIAS_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
NOMES_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


# --- Extração de dados do texto do cliente (determinística) ---

def extrair_data(texto: str, hoje: date) -> date | None:
    frase = normalizar(texto)
    if "depois de amanha" in frase:
        return hoje + timedelta(days=2)
    if "amanha" in frase:
        return hoje + timedelta(days=1)
    if re.search(r"\bhoje\b", frase):
        return hoje
    try:
        if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", frase):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", frase):
            ano = int(m[3]) if m[3] else hoje.year
            ano = ano + 2000 if ano < 100 else ano
            candidata = date(ano, int(m[2]), int(m[1]))
            return candidata.replace(year=ano + 1) if not m[3] and candidata < hoje else candidata
        if m := re.search(r"\bdia\s+(\d{1,2})\b", frase):
            dia = int(m[1])
            if dia >= hoje.day:
                return hoje.replace(day=dia)
            proximo_mes = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
            return proximo_mes.replace(day=dia)
    except ValueError:
        return None
    for nome, indice in DIAS_SEMANA.items():
        if re.search(rf"\b{nome}(?:-feira| feira)?\b", frase):
            return hoje + timedelta(days=(indice - hoje.weekday()) % 7 or 7)
    return None


def extrair_hora(texto: str) -> str | None:
    frase = normalizar(texto)
    if re.search(r"\bmeio[- ]dia\b", frase):
        return "12:00"
    for padrao in (r"\b(\d{1,2}):(\d{2})\b", r"\b(\d{1,2})\s*h(?:oras?|rs?)?\s*(\d{2})?\b", r"\b(?:as|a partir das)\s+(\d{1,2})(?![\d/:])\b"):
        if m := re.search(padrao, frase):
            hora, minuto = int(m[1]), int(m[2]) if m.lastindex and m.lastindex >= 2 and m[2] else 0
            if hora <= 23 and minuto <= 59:
                return f"{hora:02d}:{minuto:02d}"
    return None


def hora_e_do_compromisso(texto: str) -> bool:
    """"Reunião no sábado às 15h" → a hora é do compromisso (prazo); "corte às 15h" → do atendimento."""
    frase = normalizar(texto)
    return any(palavra in frase for palavra in PALAVRAS_COMPROMISSO) and not HORA_DO_ATENDIMENTO.search(frase)


def eh_pedido_de_beleza(texto: str) -> bool:
    frase = normalizar(texto)
    return any(palavra in frase for palavra in PALAVRAS_PEDIDO)


def _brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _duracao(minutos: int) -> str:
    return f"{minutos} min" if minutos < 60 else f"{minutos // 60}h{minutos % 60:02d}" if minutos % 60 else f"{minutos // 60}h"


def _data_br(dia: date) -> str:
    return f"{NOMES_DIAS[dia.weekday()]}, {dia:%d/%m/%Y}"


def _minutos(hora: str) -> int:
    return int(hora[:2]) * 60 + int(hora[3:5])


def _grupo(servico: dict[str, Any]) -> str:
    return normalizar(servico["nome"]).split()[0] if servico["nome"].strip() else ""


def _servicos_por_palavra(palavra: str, catalogo: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trechos = SINONIMOS.get(palavra, (palavra.rstrip("s"),))
    return [s for s in catalogo if any(trecho in normalizar(s["nome"]) for trecho in trechos)]


def _ordem_grupo(grupo: str) -> int:
    return PRIORIDADE_GRUPOS.index(grupo) if grupo in PRIORIDADE_GRUPOS else len(PRIORIDADE_GRUPOS)


def recomendar_por_regras(pedido: str, catalogo: list[dict[str, Any]]) -> tuple[list[int], str]:
    """Reserva quando o modelo está desligado, falha ou é rejeitado: serviços citados
    pelo cliente; sem citação, um serviço de cabelo e, se a ocasião for formal, os
    complementos (barba, unhas...). Ocasião formal → versão mais cara de cada tipo."""
    frase = normalizar(pedido)
    formal = any(palavra in frase for palavra in PALAVRAS_FORMAIS)
    escolher = (lambda grupo: max(grupo, key=lambda s: s["valor"])) if formal else (lambda grupo: min(grupo, key=lambda s: s["valor"]))
    citados: dict[str, list[dict[str, Any]]] = {}
    for palavra in SINONIMOS:
        if re.search(rf"\b{palavra}", frase):
            for servico in _servicos_por_palavra(palavra, catalogo):
                citados.setdefault(_grupo(servico), []).append(servico)
    grupos = citados or {}
    if not grupos:
        for servico in catalogo:
            grupos.setdefault(_grupo(servico), []).append(servico)
    ordenados = sorted(grupos.items(), key=lambda item: _ordem_grupo(item[0]))
    if not citados:
        cabelo = [item for item in ordenados if item[0] in GRUPOS_CABELO][:1]
        outros = [item for item in ordenados if item[0] not in GRUPOS_CABELO]
        ordenados = (cabelo + outros) if formal else (cabelo or outros)[:1]
    ids = list(dict.fromkeys(escolher(lista)["idServico"] for _, lista in ordenados))[:MAX_SERVICOS]
    if citados:
        motivo = "Separei os serviços que você citou" + (", nas versões mais completas, pela ocasião." if formal else ".")
    else:
        motivo = "Pela ocasião, priorizei as versões mais completas de cada serviço." if formal else "Separei o essencial para a ocasião."
    return ids, motivo


class Conversa:
    """Uma conversa com um cliente. `responder` processa um turno e devolve
    {resultado, fontes, suficiente, motivo}."""

    def __init__(self, ferramentas: Any, cliente_id: str, conversa_id: str = "conversa-chat", hoje: date | None = None, modo: str | None = None) -> None:
        self.ferramentas = ferramentas
        self.cliente_id = cliente_id
        self.conversa_id = conversa_id
        self.hoje = hoje or datetime.now(FUSO).date()
        self.modo = (modo or os.getenv("MODO", "mock")).lower()
        self.pedido = ""
        self.salao: dict[str, Any] | None = None
        self.catalogo: list[dict[str, Any]] = []
        self.recomendados: list[dict[str, Any]] = []
        self.motivo = ""
        self.data: date | None = None
        self.hora: str | None = None
        self.prazo: str | None = None  # hora do compromisso do cliente: os serviços terminam antes dela
        self.pedido_explicito = False
        self.pedido_suspenso = False  # o agente trocou o horário pedido: falta o cliente confirmar
        self.ids_agendamentos: list[int] = []
        self.horarios: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self.horarios_consultados: set[tuple[int, str]] = set()
        self.eventos: list[dict[str, Any]] = []

    # --- infraestrutura ---

    def _ferramenta(self, nome: str, funcao, **argumentos) -> dict[str, Any]:
        with TRACER.start_as_current_span(f"execute_tool {nome}") as span:
            span.set_attribute("gen_ai.operation.name", "execute_tool")
            span.set_attribute("gen_ai.tool.name", nome)
            span.set_attribute("gen_ai.tool.call.arguments", json_curto(argumentos))
            resultado = funcao(**argumentos)
            span.set_attribute("gen_ai.tool.call.result", json_curto(resultado))
            span.set_attribute("ferramenta.ok", bool(resultado.get("ok")))
            if not resultado.get("ok"):
                span.set_status(Status(StatusCode.ERROR))
        self.eventos.append({"tipo": "ferramenta", "ferramenta": nome, "argumentos": argumentos, "resultado": resultado})
        return resultado

    @staticmethod
    def _saida(texto: str, motivo: str, suficiente: bool = False, fontes: list[str] | None = None) -> dict[str, Any]:
        return {"resultado": texto, "fontes": fontes or [], "suficiente": suficiente, "motivo": motivo}

    def responder(self, texto: str) -> dict[str, Any]:
        with TRACER.start_as_current_span("invoke_agent agendeakiai-conversa") as raiz:
            raiz.set_attribute("gen_ai.operation.name", "invoke_agent")
            raiz.set_attribute("gen_ai.agent.name", "agendeakiai-conversa")
            raiz.set_attribute("sistema.versao", VERSAO_SISTEMA)
            raiz.set_attribute("conversa_id", self.conversa_id)
            raiz.set_attribute("cliente_id", self.cliente_id)
            raiz.set_attribute("entrada", texto)
            if os.getenv("AGENTE_SUSPENSO") == "1":  # interruptor de suspensão: nada é consultado nem escrito
                saida = self._saida(MENSAGEM_SUSPENSO, "suspenso")
            else:
                saida = self._turno(texto.strip())
            raiz.set_attribute("motivo_termino", saida["motivo"])
            raiz.set_attribute("saida", saida["resultado"])
            raiz.set_attribute("pedido_explicito", self.pedido_explicito)
            self.eventos.append({"tipo": "fim_turno", "motivo": saida["motivo"]})
            return saida

    # --- turno ---

    def _turno(self, texto: str) -> dict[str, Any]:
        if not texto:
            return self._saida("Me conte para qual ocasião você quer se arrumar ou qual serviço procura.", "aguardando_cliente")
        frase = normalizar(texto)
        intencao = pedido_explicito_de_agendamento(texto)
        if intencao is not None:
            self.pedido_explicito, self.pedido_suspenso = intencao, False
            self.eventos.append({"tipo": "pedido_de_agendamento", "explicito": intencao, "texto": texto})

        if self.ids_agendamentos:
            return self._saida(f"Seu agendamento já está confirmado (códigos {', '.join(map(str, self.ids_agendamentos))}). Para alterar ou cancelar, use o app AgendeAki.", "resposta_final", True)

        if any(palavra in frase for palavra in PALAVRAS_REGRA) and not intencao:
            return self._responder_regra(texto, frase)

        apresentar = ""
        if self.salao is None:
            if not eh_pedido_de_beleza(texto):
                self.eventos.append({"tipo": "recusa", "motivo": "fora_do_escopo"})
                return self._saida("Posso ajudar a encontrar e agendar serviços de beleza. " + NENHUM, "fora_do_escopo")
            self.pedido = texto
            falha = self._preparar_recomendacao()
            if falha:
                return falha
            apresentar = "completa"
        elif self._ajustar_servicos(frase):
            apresentar = "servicos"
            self.hora = None

        if not self.recomendados:
            return self._saida("Qual serviço você quer? Os disponíveis são: " + ", ".join(s["nome"] for s in self.catalogo) + ".", "aguardando_cliente")

        nova_data = extrair_data(texto, self.hoje)
        if nova_data is not None:
            if not self.hoje <= nova_data <= self.hoje + timedelta(days=JANELA_DIAS):
                return self._saida(f"Escolha uma data entre hoje e os próximos {JANELA_DIAS} dias. " + NENHUM, "aguardando_cliente")
            if nova_data != self.data:
                self.data, self.hora = nova_data, None
        nova_hora = extrair_hora(texto)
        if nova_hora and apresentar == "completa" and hora_e_do_compromisso(texto):
            self.prazo = nova_hora
            self.eventos.append({"tipo": "horario_do_compromisso", "prazo": nova_hora})
        elif nova_hora:
            self.hora = nova_hora
            if self.pedido_suspenso:  # o próprio cliente escolheu o horário: vale o pedido que ele já fez
                self.pedido_explicito, self.pedido_suspenso = True, False
                self.eventos.append({"tipo": "pedido_de_agendamento", "explicito": True, "texto": texto, "retomado": True})
        return self._proximo_passo(apresentar)

    def _responder_regra(self, texto: str, frase: str) -> dict[str, Any]:
        trechos = self._ferramenta_regra(texto)
        if trechos and int(trechos[0]["pontos"]) >= 2 and "alergia" not in frase:
            fonte = trechos[0]
            return self._saida(f'{fonte["titulo"]}: {fonte["trecho"].splitlines()[-1]}', "resposta_final", True, [f'{fonte["fonte"]}#{fonte["titulo"]}'])
        return self._saida("Não encontrei uma regra suficiente no corpus para responder com segurança. Procure a operação do AgendeAki.", "resposta_final")

    def _ferramenta_regra(self, texto: str) -> list[dict[str, Any]]:
        with TRACER.start_as_current_span("execute_tool buscar_regra") as span:
            span.set_attribute("gen_ai.operation.name", "execute_tool")
            span.set_attribute("gen_ai.tool.name", "buscar_regra")
            trechos = buscar_regra(pergunta=texto)
            span.set_attribute("gen_ai.tool.call.result", json_curto(trechos[:1]))
        self.eventos.append({"tipo": "ferramenta", "ferramenta": "buscar_regra", "argumentos": {"consulta": texto}, "resultado": trechos[:1]})
        return trechos

    # --- recomendação ---

    def _preparar_recomendacao(self) -> dict[str, Any] | None:
        busca = self._ferramenta("localizar_salao_mais_proximo", self.ferramentas.localizar_salao_mais_proximo)
        if not busca.get("ok"):
            return self._saida("Não consegui consultar os salões próximos agora. " + NENHUM, "erro_ferramenta")
        if not busca.get("salao"):
            return self._saida("Não encontrei salão parceiro perto da sua localização. " + NENHUM, "resposta_final", True)
        salao = busca["salao"]
        servicos = self._ferramenta("listar_servicos", self.ferramentas.listar_servicos, id_unidade=salao["idUnidade"])
        if not servicos.get("ok"):
            return self._saida("Não consegui consultar os serviços do salão agora. " + NENHUM, "erro_ferramenta")
        if not servicos.get("servicos"):
            return self._saida(f'O {salao["nomeSalao"]} não tem serviços com profissional disponível no momento. ' + NENHUM, "resposta_final", True)
        self.salao, self.catalogo = salao, servicos["servicos"]
        ids, self.motivo = self._recomendar()
        por_id = {s["idServico"]: s for s in self.catalogo}
        self.recomendados = [por_id[i] for i in ids]
        return None

    def _texto_catalogo(self) -> str:
        return "; ".join(f'{s["nome"]} {_brl(s["valor"])}' for s in self.catalogo)

    def _recomendar(self) -> tuple[list[int], str]:
        if self.modo == "gemini":
            try:
                from .modelo import recomendar_servicos
                nome_modelo = os.getenv("LLM_MODELO") or "gemini-3.8-flash"
                with TRACER.start_as_current_span(f"chat {nome_modelo}") as span:
                    span.set_attribute("gen_ai.operation.name", "chat")
                    span.set_attribute("gen_ai.request.model", nome_modelo)
                    proposta, uso = recomendar_servicos(self.pedido, self.catalogo)
                    span.set_attribute("gen_ai.usage.input_tokens", uso["tokens_entrada"])
                    span.set_attribute("gen_ai.usage.output_tokens", uso["tokens_saida"])
                    span.set_attribute("custo_usd", uso["custo_usd"])
                self.eventos.append({"tipo": "modelo", "nome": nome_modelo, "proposta": proposta, **uso})
                rejeicao = validar_recomendacao(proposta["ids_servicos"], self.catalogo, MAX_SERVICOS)
                if rejeicao:  # fail-closed: volta para as regras
                    self.eventos.append({"tipo": "recomendacao_modelo_rejeitada", "motivo": rejeicao})
                else:
                    motivo = proposta["motivo"].strip()
                    rejeicao_motivo = validar_saida_modelo(self._texto_catalogo(), motivo, False) if motivo else "motivo_vazio"
                    if rejeicao_motivo or len(motivo) > 300:
                        self.eventos.append({"tipo": "saida_modelo_rejeitada", "motivo": rejeicao_motivo or "motivo_longo"})
                        motivo = ""
                    return proposta["ids_servicos"], motivo
            except Exception as erro:
                self.eventos.append({"tipo": "modelo", "erro": str(erro)[:300], "recomendacao_por_regras": True})
        ids, motivo = recomendar_por_regras(self.pedido, self.catalogo)
        self.eventos.append({"tipo": "recomendacao_regras", "ids": ids})
        return ids, motivo

    def _ajustar_servicos(self, frase: str) -> bool:
        """"sem a barba", "só o corte", "adiciona unha": muda a lista e devolve se mudou."""
        antes = [s["idServico"] for s in self.recomendados]
        for m in re.finditer(r"\bsem\s+(?:a\s+|o\s+|as\s+|os\s+)?(\w+)", frase):
            remover = {s["idServico"] for s in _servicos_por_palavra(m[1], self.recomendados)}
            self.recomendados = [s for s in self.recomendados if s["idServico"] not in remover]
        if m := re.search(r"\b(?:so|apenas|somente)\s+(?:a\s+|o\s+|as\s+|os\s+)?(\w+)", frase):
            manter = _servicos_por_palavra(m[1], self.recomendados)
            if manter:
                self.recomendados = manter
        if re.search(r"\b(?:adicion\w*|inclu\w*|tambem|acrescent\w*|coloca\w*)\b", frase):
            for palavra in SINONIMOS:
                if re.search(rf"\b{palavra}", frase):
                    candidatos = [s for s in _servicos_por_palavra(palavra, self.catalogo) if s not in self.recomendados]
                    if candidatos and len(self.recomendados) < MAX_SERVICOS:
                        self.recomendados.append(min(candidatos, key=lambda s: s["valor"]))
        mudou = [s["idServico"] for s in self.recomendados] != antes
        if mudou:
            self.eventos.append({"tipo": "servicos_ajustados", "ids": [s["idServico"] for s in self.recomendados]})
        return mudou

    # --- dia, horário e agendamento ---

    def _texto_apresentacao(self, so_servicos: bool = False) -> str:
        salao = self.salao or {}
        nome = salao["nomeSalao"] + (f' ({salao["nomeUnidade"]})' if salao.get("nomeUnidade") else "")
        distancia = f'{salao["distanciaKm"]:.1f}'.replace(".", ",")
        linhas = ["Serviços atualizados:"] if so_servicos else [f'Salão mais próximo: {nome}, a {distancia} km — {salao["endereco"]}.', "Recomendo:"]
        linhas += [f'  • {s["nome"]} — {_brl(s["valor"])} ({_duracao(s["duracaoMinutos"])})' for s in self.recomendados]
        total = sum(s["valor"] for s in self.recomendados)
        duracao = sum(s["duracaoMinutos"] for s in self.recomendados)
        linhas.append(f"Total: {_brl(total)}, cerca de {_duracao(duracao)}." + (f" {self.motivo}" if self.motivo and not so_servicos else ""))
        return "\n".join(linhas)

    def _horarios_do_servico(self, servico: dict[str, Any]) -> dict[str, Any]:
        chave = (self.data.isoformat(), servico["idServico"])
        if chave not in self.horarios:
            resposta = self._ferramenta("listar_horarios", self.ferramentas.listar_horarios, id_unidade=self.salao["idUnidade"], id_servico=servico["idServico"], data=chave[0])
            if not resposta.get("ok"):
                return resposta
            self.horarios[chave] = resposta.get("horarios", [])
            self.horarios_consultados |= {(servico["idServico"], f'{chave[0]}T{h["inicio"]}:00') for h in self.horarios[chave]}
        return {"ok": True, "horarios": self.horarios[chave]}

    def _plano(self, inicio: str) -> list[dict[str, Any]] | None:
        """Encaixa os serviços em sequência: o primeiro começa em `inicio`; cada seguinte,
        no primeiro horário livre até MAX_ESPERA_MINUTOS depois do fim do anterior."""
        itens, hora = [], inicio
        for indice, servico in enumerate(self.recomendados):
            livres = self.horarios[(self.data.isoformat(), servico["idServico"])]
            if indice == 0:
                slot = next((h for h in livres if h["inicio"] == hora), None)
            else:
                slot = next((h for h in livres if 0 <= _minutos(h["inicio"]) - _minutos(hora) <= MAX_ESPERA_MINUTOS), None)
            if not slot:
                return None
            itens.append({"idServico": servico["idServico"], "nome": servico["nome"], "valor": servico["valor"], "idFuncionario": slot["idFuncionario"], "profissional": slot["profissional"], "inicio": slot["inicio"], "fim": slot["fim"], "dataHoraInicio": f'{self.data.isoformat()}T{slot["inicio"]}:00'})
            hora = slot["fim"]
        return itens

    def _inicios_viaveis(self) -> list[str] | dict[str, Any]:
        for servico in self.recomendados:
            resposta = self._horarios_do_servico(servico)
            if not resposta.get("ok"):
                return resposta
        primeiro = self.horarios[(self.data.isoformat(), self.recomendados[0]["idServico"])]
        return [h["inicio"] for h in primeiro if self._plano(h["inicio"])]

    def _proximo_passo(self, apresentar: str) -> dict[str, Any]:
        partes = [self._texto_apresentacao(so_servicos=apresentar == "servicos")] if apresentar else []
        fontes = ["API AgendeAki: salões próximos, serviços e horários"]
        if self.data is None:
            partes.append("Para qual dia você quer? (ex.: amanhã, sexta, 20/11)")
            return self._saida("\n".join(partes), "aguardando_cliente", False, fontes)
        livres = self._inicios_viaveis()
        if isinstance(livres, dict):
            mensagem = livres.get("erro", {}).get("mensagem", "")
            self.data = None
            partes.append(f"Não consegui consultar os horários desse dia{': ' + mensagem if mensagem else ''}. Quer tentar outro dia? " + NENHUM)
            return self._saida("\n".join(partes), "aguardando_cliente", False, fontes)
        if not livres:
            dia = _data_br(self.data)
            self.data, self.hora = None, None
            partes.append(f"Não há horário livre em {dia} para esses serviços em sequência. Quer tentar outro dia?")
            return self._saida("\n".join(partes), "aguardando_cliente", False, fontes)
        if self.hora is None and self.prazo:
            return self._propor_antes_do_compromisso(livres, partes, fontes)
        if self.hora is None:
            passo = max(1, -(-len(livres) // MAX_HORARIOS_LISTADOS))  # espalha as opções pelo dia
            partes.append(f"Para {_data_br(self.data)}, tenho estes horários de início: {', '.join(livres[::passo])}. Qual prefere?")
            return self._saida("\n".join(partes), "aguardando_cliente", False, fontes)
        plano = self._plano(self.hora)
        if plano is None:
            # horário fora da grade ou ocupado: propõe o início mais próximo, sem agendar sozinho
            pedido = self.hora
            mais_proximo = min(livres, key=lambda h: (abs(_minutos(h) - _minutos(pedido)), h))
            outros = sorted(sorted(livres, key=lambda h: abs(_minutos(h) - _minutos(pedido)))[1:4])
            self.hora, plano = mais_proximo, self._plano(mais_proximo)
            if self.pedido_explicito:
                self.pedido_explicito, self.pedido_suspenso = False, True
                self.eventos.append({"tipo": "pedido_suspenso", "motivo": "horario_alterado", "pedido": pedido, "proposto": mais_proximo})
            partes.append(f"O horário {pedido} não está livre em {_data_br(self.data)}; o mais próximo é {mais_proximo}." + (f" Outras opções: {', '.join(outros)}." if outros else ""))
            partes.append(f"{self._texto_plano(plano)}\n{NENHUM} Se {mais_proximo} servir, diga \"pode agendar\"; ou escolha outro horário.")
            return self._saida("\n".join(partes), "aguardando_cliente", True, fontes)
        resumo = self._texto_plano(plano)
        if not self.pedido_explicito:
            partes.append(f"{resumo}\n{NENHUM} Se quiser que eu agende, é só dizer explicitamente, por exemplo: \"pode agendar\".")
            return self._saida("\n".join(partes), "aguardando_cliente", True, fontes)
        return self._agendar(plano, partes, fontes)

    def _propor_antes_do_compromisso(self, livres: list[str], partes: list[str], fontes: list[str]) -> dict[str, Any]:
        """Escolhe o início mais tarde em que tudo termina até MARGEM antes do compromisso."""
        limite = _minutos(self.prazo) - MARGEM_COMPROMISSO_MINUTOS
        limite_texto = f"{limite // 60:02d}:{limite % 60:02d}"
        cabem = [h for h in livres if _minutos(self._plano(h)[-1]["fim"]) <= limite]
        if not cabem:
            passo = max(1, -(-len(livres) // MAX_HORARIOS_LISTADOS))
            partes.append(f"Seu compromisso é às {self.prazo}, mas em {_data_br(self.data)} não há horário que termine até {limite_texto}. Horários livres nesse dia: {', '.join(livres[::passo])}. Prefere um deles ou outro dia? " + NENHUM)
            return self._saida("\n".join(partes), "aguardando_cliente", False, fontes)
        self.hora = cabem[-1]
        plano = self._plano(self.hora)
        if self.pedido_explicito:  # quem escolheu o horário foi o agente: o cliente confirma
            self.pedido_explicito, self.pedido_suspenso = False, True
            self.eventos.append({"tipo": "pedido_suspenso", "motivo": "horario_escolhido_pelo_agente", "proposto": self.hora})
        outros = cabem[-4:-1]
        partes.append(f"Como seu compromisso é às {self.prazo}, sugiro terminar até {limite_texto}, com folga para chegar." + (f" Também dá para começar às {', '.join(outros)}." if outros else ""))
        partes.append(f"{self._texto_plano(plano)}\n{NENHUM} Se servir, diga \"pode agendar\"; ou escolha outro horário.")
        return self._saida("\n".join(partes), "aguardando_cliente", True, fontes)

    def _texto_plano(self, plano: list[dict[str, Any]]) -> str:
        linhas = [f"Resumo — {_data_br(self.data)}, {self.salao['nomeSalao']} ({self.salao['endereco']}):"]
        linhas += [f'  • {item["inicio"]} — {item["nome"]} com {item["profissional"]} ({_brl(item["valor"])})' for item in plano]
        linhas.append(f'Total: {_brl(sum(item["valor"] for item in plano))}.')
        return "\n".join(linhas)

    def _agendar(self, plano: list[dict[str, Any]], partes: list[str], fontes: list[str]) -> dict[str, Any]:
        bloqueio = verificar_escrita_conversa(self.pedido_explicito, plano, [s["idServico"] for s in self.recomendados], self.horarios_consultados, bool(self.ids_agendamentos))
        if bloqueio:  # fail-closed: nada é escrito
            self.eventos.append({"tipo": "escrita_bloqueada", "motivo": bloqueio})
            partes.append(f"A escrita foi bloqueada por um controle de segurança ({bloqueio}). " + NENHUM)
            return self._saida("\n".join(partes), "escrita_bloqueada", False, fontes)
        resposta = self._ferramenta("criar_agendamentos", self.ferramentas.criar_agendamentos, id_unidade=self.salao["idUnidade"], itens=plano)
        if not resposta.get("ok"):
            mensagem = resposta.get("erro", {}).get("mensagem", "a API recusou o pedido")
            self.horarios = {chave: valor for chave, valor in self.horarios.items() if chave[0] != self.data.isoformat()}
            self.hora = None
            partes.append(f"Não consegui agendar: {mensagem} {NENHUM} Quer escolher outro horário?")
            return self._saida("\n".join(partes), "aguardando_cliente", False, fontes)
        self.ids_agendamentos = list(resposta.get("idsAgendamentos", []))
        partes.append(f"Agendamento confirmado! {self._texto_plano(plano)}\nCódigos: {', '.join(map(str, self.ids_agendamentos))}.")
        return self._saida("\n".join(partes), "agendamento_confirmado", True, fontes)
