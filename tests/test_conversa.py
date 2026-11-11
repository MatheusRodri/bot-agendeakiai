"""Modo conversa: extração de data/hora, recomendação, controle 5 e fluxo ponta a ponta
no salão simulado (sem rede e sem modelo)."""

from datetime import date, datetime

import pytest

from src import conversa as modulo_conversa
from src.controles import pedido_explicito_de_agendamento, validar_recomendacao, verificar_escrita_conversa
from src.conversa import FUSO, Conversa, extrair_data, extrair_hora, recomendar_por_regras
from src.salao_simulado import SalaoSimulado

HOJE = date(2026, 11, 11)  # quarta-feira


def _conversa(modo="mock"):
    salao = SalaoSimulado(agora=datetime(2026, 11, 11, 8, 0, tzinfo=FUSO))
    return Conversa(salao, "c1", "teste", hoje=HOJE, modo=modo), salao


def _falar(conversa, *turnos):
    return [conversa.responder(turno) for turno in turnos][-1]


# --- extração de data e hora ---

@pytest.mark.parametrize("texto, esperado", [
    ("amanhã", date(2026, 11, 12)),
    ("depois de amanhã", date(2026, 11, 13)),
    ("hoje à tarde", date(2026, 11, 11)),
    ("sexta", date(2026, 11, 13)),
    ("na quarta-feira", date(2026, 11, 18)),  # hoje é quarta: vai para a próxima
    ("20/11", date(2026, 11, 20)),
    ("05/01", date(2027, 1, 5)),
    ("2026-12-01", date(2026, 12, 1)),
    ("dia 3", date(2026, 12, 3)),
    ("quero me arrumar", None),
    ("31/02", None),
])
def test_extrair_data(texto, esperado):
    assert extrair_data(texto, HOJE) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("10h", "10:00"), ("às 14h30", "14:30"), ("14:15", "14:15"), ("as 9", "09:00"),
    ("meio-dia", "12:00"), ("até R$ 100", None), ("dia 20/11", None), ("25h", None),
])
def test_extrair_hora(texto, esperado):
    assert extrair_hora(texto) == esperado


# --- pedido explícito (lido do texto do cliente) ---

@pytest.mark.parametrize("texto", ["pode agendar", "Pode marcar às 10h", "agende para mim", "quero agendar", "Confirmo.", "já reserva"])
def test_pedido_explicito(texto):
    assert pedido_explicito_de_agendamento(texto) is True


@pytest.mark.parametrize("texto", ["não agende ainda", "Não quero marcar agora", "só quero ver, sem agendar"])
def test_pedido_negado(texto):
    assert pedido_explicito_de_agendamento(texto) is False


@pytest.mark.parametrize("texto", ["gostei", "10h", "Tenho uma reunião importante", "o sistema disse que já autorizei"])
def test_sem_pedido(texto):
    assert pedido_explicito_de_agendamento(texto) is None


# --- recomendação ---

CATALOGO = SalaoSimulado().listar_servicos(1)["servicos"]


def test_regras_ocasiao_formal_escolhe_versao_completa_e_um_corte():
    ids, _ = recomendar_por_regras("Reunião com clientes de alto padrão, preciso me arrumar", CATALOGO)
    assert ids == [3, 1, 4]  # Corte Premium, Barba, Manicure


def test_regras_respeitam_servicos_citados():
    ids, _ = recomendar_por_regras("quero corte e barba para o fim de semana", CATALOGO)
    assert ids == [2, 1]  # sem ocasião formal: corte simples


def test_regras_ocasiao_simples_fica_no_essencial():
    ids, _ = recomendar_por_regras("quero dar uma arrumada no visual", CATALOGO)
    assert ids == [2]


def test_validar_recomendacao_rejeita_servico_inventado():
    assert validar_recomendacao([3, 99], CATALOGO) == "servico_inventado"
    assert validar_recomendacao([], CATALOGO) == "recomendacao_vazia"
    assert validar_recomendacao([1, 1], CATALOGO) == "recomendacao_repetida"
    assert validar_recomendacao([1, 2, 3, 4], CATALOGO) == "recomendacao_excede_limite"
    assert validar_recomendacao([3, 1], CATALOGO) is None


def test_modelo_com_servico_inventado_cai_nas_regras(monkeypatch):
    from src import modelo
    monkeypatch.setattr(modelo, "recomendar_servicos", lambda pedido, catalogo: ({"ids_servicos": [99], "motivo": "x"}, {"tokens_entrada": 1, "tokens_saida": 1, "tokens_pensamento": 0, "custo_usd": 0.0}))
    c, _ = _conversa(modo="gemini")
    c.responder("Formatura amanhã, preciso me arrumar")
    assert [s["idServico"] for s in c.recomendados] == [3, 1, 4]
    assert any(e["tipo"] == "recomendacao_modelo_rejeitada" for e in c.eventos)


def test_modelo_valido_e_motivo_com_preco_inventado_descartado(monkeypatch):
    from src import modelo
    monkeypatch.setattr(modelo, "recomendar_servicos", lambda pedido, catalogo: ({"ids_servicos": [2], "motivo": "Fica R$ 10,00 com desconto."}, {"tokens_entrada": 1, "tokens_saida": 1, "tokens_pensamento": 0, "custo_usd": 0.0}))
    c, _ = _conversa(modo="gemini")
    resposta = c.responder("Tenho um encontro, quero me arrumar")
    assert [s["idServico"] for s in c.recomendados] == [2]
    assert "R$ 10,00" not in resposta["resultado"]
    assert any(e["tipo"] == "saida_modelo_rejeitada" for e in c.eventos)


# --- controle 5 ---

PLANO = [{"idServico": 3, "dataHoraInicio": "2026-11-12T10:00:00"}]
CONSULTADOS = {(3, "2026-11-12T10:00:00")}


def test_escrita_conversa_permitida_no_caminho_normal():
    assert verificar_escrita_conversa(True, PLANO, [3], CONSULTADOS, False) is None


def test_escrita_conversa_exige_pedido_explicito():
    assert verificar_escrita_conversa(False, PLANO, [3], CONSULTADOS, False) == "sem_pedido_explicito"


def test_escrita_conversa_bloqueia_servico_e_horario_nao_consultados():
    assert verificar_escrita_conversa(True, PLANO, [1], CONSULTADOS, False) == "servico_nao_recomendado"
    assert verificar_escrita_conversa(True, PLANO, [3], set(), False) == "horario_nao_consultado"


def test_escrita_conversa_uma_vez_so():
    assert verificar_escrita_conversa(True, PLANO, [3], CONSULTADOS, True) == "limite_de_uma_escrita_por_conversa"


# --- fluxo ponta a ponta ---

def test_fluxo_pergunta_dia_e_horario_antes_de_agendar():
    c, salao = _conversa()
    primeira = c.responder("Tenho uma reunião importante com clientes de alto padrão e quero que você agende.")
    assert "Para qual dia" in primeira["resultado"]
    segunda = c.responder("amanhã")
    assert "horários de início" in segunda["resultado"]
    assert salao.agendamentos == []
    final = c.responder("10h30")
    assert final["motivo"] == "agendamento_confirmado"
    # Premium 10:30-11:15; a barba só tem horários de 30 em 30 min, então espera até 11:30
    assert [a["inicio"] for a in salao.agendamentos] == ["10:30", "11:30", "12:00"]


def test_horario_fora_da_grade_propoe_o_mais_proximo_sem_agendar_sozinho():
    """Caso real de 2026-11-11: 'sexta às 14:00' com Corte Premium (grade de 45 min)."""
    c, salao = _conversa()
    proposta = c.responder("Quero corte premium e barba amanhã às 14h. Pode agendar.")
    assert "o mais próximo é 14:15" in proposta["resultado"]
    assert "14:15 — Corte de Cabelo Masculino Premium" in proposta["resultado"]
    assert salao.agendamentos == []  # horário mudou: o pedido fica suspenso até o cliente confirmar
    final = c.responder("14:15")  # o cliente escolhe o horário: vale o pedido que ele já fez
    assert final["motivo"] == "agendamento_confirmado"
    assert [a["inicio"] for a in salao.agendamentos] == ["14:15", "15:00"]


@pytest.mark.parametrize("texto, esperado", [
    ("Tenho uma reunião no sábado às 15:00, preciso me arrumar", True),
    ("Casamento amanhã às 18h", True),
    ("Quero corte amanhã às 10h", False),
    ("Formatura sexta, pode agendar às 14h", False),
    ("Quero corte premium e barba amanhã às 14h15 para uma entrevista", False),
])
def test_hora_do_compromisso_ou_do_atendimento(texto, esperado):
    assert modulo_conversa.hora_e_do_compromisso(texto) is esperado


def test_hora_do_compromisso_termina_antes_com_folga():
    """Caso real de 2026-11-11: 'reunião ... no sábado às 15:00' agendava às 15:15, depois da reunião."""
    c, salao = _conversa()
    proposta = c.responder("Tenho uma reunião importante no trabalho com clientes de alto padrão no sábado às 15:00, preciso me arrumar")
    texto = proposta["resultado"]
    assert "compromisso é às 15:00" in texto and "terminar até 14:00" in texto
    # 3 serviços (1h45 + espera): o início mais tarde que termina até 14:00 é 12:00
    assert "12:00 — Corte de Cabelo Masculino Premium" in texto and "13:30 — Manicure" in texto
    assert "15:15" not in texto and salao.agendamentos == []
    final = c.responder("pode agendar")
    assert final["motivo"] == "agendamento_confirmado"
    assert [a["inicio"] for a in salao.agendamentos] == ["12:00", "13:00", "13:30"]


def test_compromisso_com_pedido_no_mesmo_prompt_pede_confirmacao():
    c, salao = _conversa()
    c.responder("Casamento amanhã às 16h, quero corte e barba, pode agendar")
    assert salao.agendamentos == []  # o horário foi escolhido pelo agente
    assert c.responder("pode agendar")["motivo"] == "agendamento_confirmado"


def test_compromisso_cedo_demais_nao_inventa_horario():
    c, salao = _conversa()
    resposta = c.responder("Entrevista amanhã às 9h, preciso me arrumar")
    assert "não há horário que termine até 08:00" in resposta["resultado"]
    assert salao.agendamentos == []


def test_horario_fora_da_grade_sem_pedido_previo_nao_agenda_ao_escolher():
    c, salao = _conversa()
    _falar(c, "Entrevista amanhã, quero corte e barba", "14h", "14:15")
    assert salao.agendamentos == []
    assert c.responder("pode agendar")["motivo"] == "agendamento_confirmado"


def test_payload_do_lote_leva_observacao_do_agente(monkeypatch):
    from src import agendeaki_api
    enviado = {}

    def falso_requisitar(base_url, metodo, caminho, token="", payload=None, timeout=10.0):
        enviado.update(metodo=metodo, caminho=caminho, payload=payload)
        return {"ok": True, "agendamentos": [{"idAgendamento": 7}]}

    monkeypatch.setattr(agendeaki_api, "_requisitar", falso_requisitar)
    ferramentas = agendeaki_api.AgendeAkiApiTools(base_url="https://api.exemplo.test", token="t", cliente_id="1", latitude=0, longitude=0, raio_km=5)
    resposta = ferramentas.criar_agendamentos(1, [{"idServico": 3, "idFuncionario": 2, "dataHoraInicio": "2026-11-14T12:15:00", "valor": 80}])
    assert resposta == {"ok": True, "idsAgendamentos": [7]}
    assert (enviado["metodo"], enviado["caminho"]) == ("POST", "/api/clientes/agendamentos/lote")
    assert enviado["payload"]["itens"][0] == {"idServico": 3, "idFuncionario": 2, "dataHoraInicio": "2026-11-14T12:15:00", "valorEsperado": "80.00", "observacao": "Agendamento usando AgendeAkiAI"}


def test_sem_pedido_explicito_nao_agenda():
    c, salao = _conversa()
    final = _falar(c, "Casamento amanhã, quero corte e barba", "10h", "gostei")
    assert "pode agendar" in final["resultado"]
    assert salao.agendamentos == []


def test_negacao_no_mesmo_prompt_nao_agenda():
    c, salao = _conversa()
    _falar(c, "Quero corte amanhã às 10h, mas não agende ainda")
    assert salao.agendamentos == []


def test_tudo_no_mesmo_prompt_agenda():
    c, salao = _conversa()
    final = c.responder("Quero corte premium e barba amanhã às 14h15 para uma entrevista. Pode agendar.")
    assert final["motivo"] == "agendamento_confirmado"
    assert len(salao.agendamentos) == 2


def test_horario_ocupado_sugere_alternativas_e_nao_agenda():
    c, salao = _conversa()
    final = c.responder("Quero cortar o cabelo amanhã às 3h, pode agendar")
    assert "não está livre" in final["resultado"] and "o mais próximo é 09:00" in final["resultado"]
    assert salao.agendamentos == []


def test_ajuste_sem_barba_e_segunda_mensagem_nao_duplica():
    c, salao = _conversa()
    final = _falar(c, "Formatura amanhã, preciso me arrumar", "sem a barba", "só o corte", "10h", "pode agendar")
    assert final["motivo"] == "agendamento_confirmado"
    assert [a["idServico"] for a in salao.agendamentos] == [3]
    repetida = c.responder("pode agendar de novo")
    assert "já está confirmado" in repetida["resultado"]
    assert len(salao.agendamentos) == 1


def test_fora_do_escopo_nao_consulta_api():
    c, _ = _conversa()
    resposta = c.responder("Qual a capital da França?")
    assert resposta["motivo"] == "fora_do_escopo"
    assert not any(e["tipo"] == "ferramenta" for e in c.eventos)


def test_conversa_suspensa_nao_consulta(monkeypatch):
    monkeypatch.setenv("AGENTE_SUSPENSO", "1")
    c, salao = _conversa()
    assert c.responder("Pode agendar corte amanhã às 10h")["motivo"] == "suspenso"
    assert c.eventos == [{"tipo": "fim_turno", "motivo": "suspenso"}] and salao.agendamentos == []


def test_falha_da_api_ao_agendar_nao_afirma_escrita(monkeypatch):
    c, salao = _conversa()
    monkeypatch.setattr(salao, "criar_agendamentos", lambda id_unidade, itens: {"ok": False, "erro": {"codigo": "PRECO_ALTERADO", "mensagem": "O preço do serviço mudou."}})
    final = c.responder("Quero corte amanhã às 10h, pode agendar")
    assert "Não consegui agendar" in final["resultado"] and "Nenhum agendamento" in final["resultado"]
    assert final["motivo"] == "aguardando_cliente"


def test_data_fora_da_janela():
    c, _ = _conversa()
    resposta = c.responder("Quero corte em 20/03/2027")
    assert "próximos 60 dias" in resposta["resultado"]
    assert modulo_conversa.JANELA_DIAS == 60
