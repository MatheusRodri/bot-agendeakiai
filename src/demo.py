"""Executa os cenários locais e grava logs reais do grafo."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

from .contratos import EntradaAgente
from .grafo import _GRAFO_CACHE, executar, saida_validada
from .tools import ApiTools


ROOT = Path(__file__).resolve().parents[1]
PORTA = 8765
CASOS = [
    ("01-caso-simples.json", "caso simples com escrita confirmada", "cliente-001", "Quero um penteado clássico para casamento no Centro até R$ 150. Confirmo o agendamento da melhor opção encontrada."),
    ("02-divergencia.json", "preferência atual diverge do histórico", "cliente-001", "Apesar de eu normalmente escolher algo moderno, hoje quero penteado clássico no Centro até R$ 150."),
    ("03-registro-inexistente.json", "cliente inexistente", "cliente-inexistente", "Quero um corte profissional para entrevista em Moema até R$ 100."),
    ("04-sem-acao-principal.json", "consulta sem autorização de escrita", "cliente-002", "Só quero comparar maquiagem natural para formatura até R$ 150; não quero reservar agora."),
    ("05-fora-do-corpus.json", "pergunta sem resposta no corpus", "cliente-002", "Qual produto devo usar para tratar minha alergia na pele?"),
    ("06-aprovacao-editada.json", "aprovação editada e repetida", "cliente-002", "Quero penteado clássico no Centro até R$ 150. Confirmo o agendamento."),
    ("07-incompleta.json", "entrada incompleta", "cliente-002", "Quero ajuda para me arrumar para um evento."),
    ("08-ambigua.json", "entrada ambígua", "cliente-002", "Quero maquiagem para formatura até R$ 200."),
    ("09-fora-escopo.json", "entrada fora do escopo", "cliente-002", "Como preparo uma planilha de orçamento doméstico?"),
    ("10-aprovacao-expirada.json", "aprovação expirada", "cliente-002", "Quero agendar penteado clássico no Centro até R$ 150. Confirmo."),
]


def _iniciar_api() -> subprocess.Popen:
    processo = subprocess.Popen([sys.executable, "-m", "src.mock_api", "--port", str(PORTA)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            with request.urlopen(f"http://127.0.0.1:{PORTA}/saude", timeout=0.2):
                return processo
        except OSError:
            time.sleep(0.1)
    processo.terminate()
    raise RuntimeError("A API mock não iniciou na porta 8765.")


def _registrar_log(arquivo: str, caso: str, cliente_id: str, conversa_id: str, texto: str, estado: dict, pausa: dict | None = None, repeticao: dict | None = None) -> None:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip() or "desconhecido"
    codigo_alterado = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src"], cwd=ROOT, check=False).returncode != 0
    impressao = hashlib.sha256()
    arquivos_codigo = sorted((ROOT / "src").rglob("*.py")) + [ROOT / "src" / "prompts" / "agente-v1.txt"]
    for caminho in arquivos_codigo:
        impressao.update(str(caminho.relative_to(ROOT)).encode("utf-8"))
        impressao.update(caminho.read_bytes())
    saida = saida_validada(estado)
    log = {
        "caso": caso,
        "entrada": {"texto": texto, "cliente_id": cliente_id, "conversa_id": conversa_id},
        "executado_em": datetime.now(timezone.utc).isoformat(),
        "commit_base": commit,
        "arvore_de_trabalho_alterada": codigo_alterado,
        "impressao_do_codigo": impressao.hexdigest(),
        "saida_validada": saida,
        "eventos": estado.get("eventos", []),
        "estado_final": {"agendamento": estado.get("agendamento", {}), "motivo_terminacao": estado.get("motivo_terminacao", ""), "passos": estado.get("passos", 0)},
    }
    if pausa is not None:
        log["pausa_humana"] = pausa
    if repeticao is not None:
        log["repeticao_idempotente"] = repeticao
    pasta = ROOT / "logs"
    pasta.mkdir(exist_ok=True)
    (pasta / arquivo).write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{arquivo}: {saida['resultado']}")


def main() -> int:
    processo = _iniciar_api()
    ferramentas = ApiTools(f"http://127.0.0.1:{PORTA}", "token-mock")
    try:
        for arquivo, nome, cliente_id, texto in CASOS:
            conversa_id = f"demo-{Path(arquivo).stem}-{int(time.time() * 1000)}"
            entrada = EntradaAgente(texto=texto, cliente_id=cliente_id, conversa_id=conversa_id)
            estado = executar(entrada, ferramentas)
            pausa = None
            repeticao = None
            if arquivo in ("01-caso-simples.json", "06-aprovacao-editada.json", "10-aprovacao-expirada.json"):
                interrupcoes = estado.get("__interrupt__", [])
                if interrupcoes:
                    pausa = interrupcoes[0].value
                    if arquivo.startswith("10-"):
                        grafo = _GRAFO_CACHE[(type(ferramentas), ferramentas.base_url)]
                        configuracao = {"configurable": {"thread_id": conversa_id}}
                        pendente = estado["aprovacao_pendente"]
                        pendente["expira_em"] = "2000-01-01T00:00:00+00:00"
                        estado = grafo.update_state(configuracao, {"aprovacao_pendente": pendente})
                        decisao = {"acao": "aprovar"}
                    else:
                        decisao = {"acao": "aprovar"} if arquivo.startswith("01-") else {"acao": "editar", "opcao_id": "opc-005"}
                    estado = executar(entrada, ferramentas, decisao)
                    if arquivo.startswith("06-"):
                        evento = next(item for item in estado["eventos"] if item.get("ferramenta") == "confirmar_agendamento")
                        opcao = next(item for item in estado["eventos"] if item.get("tipo") == "aprovacao_humana")["opcao_id"]
                        segunda = ferramentas.confirmar_agendamento(next(o for o in estado.get("opcoes", []) if o["opcaoId"] == opcao), evento["argumentos"]["chave_idempotencia"], cliente_id)
                        identificadores = {evento["resultado"].get("agendamento", {}).get("idAgendamento"), segunda.get("agendamento", {}).get("idAgendamento")}
                        identificadores.discard(None)
                        repeticao = {"primeira_escrita": evento["resultado"], "segunda_chamada": segunda, "agendamentos_unicos": len(identificadores)}
            _registrar_log(arquivo, nome, cliente_id, conversa_id, texto, estado, pausa, repeticao)
        return 0
    finally:
        processo.terminate()
        processo.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
