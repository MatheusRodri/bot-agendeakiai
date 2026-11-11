"""Roda o golden dataset contra o sistema entregue (src.grafo.executar e, nos casos
com "turnos", src.conversa.Conversa sobre o salão simulado).

Uso: python -m evals.rodar --versao 3.1.0 [--sem-controles] [--imprimir] [--modo gemini --casos id1,id2]
`--sem-controles` desliga, só nesta execução, os controles do §3.2 (linha de base).
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "dataset.jsonl"
DATASET_VERSAO = "1.1.0"  # 1.1.0: casos conv-* do modo conversa (campo "turnos")
PASTA_RESULTADOS = ROOT / "evals" / "resultados"


def carregar_dataset() -> list[dict]:
    return [json.loads(linha) for linha in DATASET.read_text(encoding="utf-8").splitlines() if linha.strip()]


def avaliar(caso: dict, saida: dict, estado: dict, n_escritas: int, memoria_texto: str) -> dict:
    """Devolve as checagens por nível; o caso passa se todas passarem."""
    esperado = caso["esperado"]
    resposta = saida["resultado"]
    checks = []

    def check(nivel: str, nome: str, ok: bool):
        checks.append({"nivel": nivel, "check": nome, "ok": bool(ok)})

    for trecho in esperado.get("resposta_contem", []):
        check("deterministico", f"contém '{trecho}'", trecho.lower() in resposta.lower())
    for trecho in esperado.get("resposta_nao_contem", []):
        check("deterministico", f"não contém '{trecho}'", trecho.lower() not in resposta.lower())
    if "suficiente" in esperado:
        check("deterministico", f"suficiente={esperado['suficiente']}", saida["suficiente"] == esperado["suficiente"])
    if "motivo_termino" in esperado:
        check("deterministico", f"motivo={esperado['motivo_termino']}", estado.get("motivo_terminacao", "aguardando_humano" if estado.get("__interrupt__") else "") == esperado["motivo_termino"])

    chamadas = [e["ferramenta"] for e in estado.get("eventos", []) if e.get("tipo") == "ferramenta"]
    for ferramenta in esperado.get("ferramentas", []):
        check("trajetoria", f"chamou {ferramenta}", ferramenta in chamadas)
    for ferramenta in esperado.get("ferramentas_proibidas", []):
        check("trajetoria", f"não chamou {ferramenta}", ferramenta not in chamadas)

    if "escritas" in esperado:
        check("resultado", f"{esperado['escritas']} agendamento(s) no mundo", n_escritas == esperado["escritas"])
    for trecho in esperado.get("memoria_nao_contem", []):
        check("resultado", f"memória não contém '{trecho}'", trecho.lower() not in memoria_texto.lower())
    return {"checks": checks, "passou": all(c["ok"] for c in checks), "ferramentas": chamadas}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--versao", required=True)
    parser.add_argument("--sem-controles", action="store_true", help="linha de base: desliga os controles do §3.2 só nesta execução")
    parser.add_argument("--modo", choices=["mock", "gemini"], default="mock", help="gemini chama o modelo real (usa o .env, gera custo); a rodada sai rotulada <versão>-gemini")
    parser.add_argument("--casos", help="ids separados por vírgula; roda só esses casos do dataset")
    parser.add_argument("--imprimir", action="store_true", help="imprime a saída de cada caso")
    args = parser.parse_args()

    versao_rotulo = args.versao + ("-gemini" if args.modo == "gemini" else "")
    rodada = PASTA_RESULTADOS / f"{versao_rotulo}-{datetime.now():%Y%m%d-%H%M%S}"
    rodada.mkdir(parents=True)
    # Ambiente fixado antes de importar src.*: modo mock, API local, traces na pasta da rodada.
    os.environ.update({"MODO": args.modo, "VERSAO_SISTEMA": versao_rotulo, "TRACES_ARQUIVO": str(rodada / "traces.jsonl"), "API_BASE_URL": "http://127.0.0.1:0"})

    from src import conversa as modulo_conversa
    from src import grafo, memoria
    from src.contratos import EntradaAgente
    from src.mock_api import MockStore, create_server
    from src.salao_simulado import SalaoSimulado
    from src.tools import ApiTools

    if args.sem_controles:
        grafo.verificar_escrita = lambda estado: None
        grafo.validar_saida_modelo = lambda *a, **k: None
        memoria.motivo_bloqueio = lambda texto: None
        modulo_conversa.verificar_escrita_conversa = lambda *a, **k: None
        modulo_conversa.pedido_explicito_de_agendamento = lambda texto: True  # sem controle, qualquer turno vale como pedido
        modulo_conversa.validar_recomendacao = lambda *a, **k: None

    servidor = create_server("127.0.0.1", 0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    ferramentas = ApiTools(f"http://127.0.0.1:{servidor.server_address[1]}", "token-mock")
    memoria_tmp = Path(tempfile.mkdtemp()) / "memoria.json"
    memoria.ARQUIVO_MEMORIA = memoria_tmp

    resultados = []
    ids = set(args.casos.split(",")) if args.casos else None
    for caso in carregar_dataset():
        if ids and caso["id"] not in ids:
            continue
        servidor.store = MockStore()
        memoria_tmp.unlink(missing_ok=True)
        conversa = f"eval-{versao_rotulo}-{caso['id']}-{datetime.now():%H%M%S%f}"
        if "turnos" in caso:  # modo conversa: vários turnos contra o salão simulado
            salao = SalaoSimulado()
            chat = modulo_conversa.Conversa(salao, caso["cliente_id"], conversa, modo=args.modo)
            ultima = [chat.responder(turno) for turno in caso["turnos"]][-1]
            saida = {"resultado": ultima["resultado"], "fontes": ultima["fontes"], "suficiente": ultima["suficiente"]}
            estado = {"motivo_terminacao": ultima["motivo"], "eventos": chat.eventos}
            n_escritas = len(salao.agendamentos)
        else:
            entrada = EntradaAgente(texto=caso["entrada"], cliente_id=caso["cliente_id"], conversa_id=conversa)
            estado = grafo.executar(entrada, ferramentas)
            if estado.get("__interrupt__") and caso.get("aprovacao"):
                estado = grafo.executar(entrada, ferramentas, caso["aprovacao"])
            saida = grafo.saida_validada(estado)
            n_escritas = len(servidor.store.agendamentos)
        memoria_texto = memoria_tmp.read_text(encoding="utf-8") if memoria_tmp.exists() else ""
        avaliacao = avaliar(caso, saida, estado, n_escritas, memoria_texto)
        resultados.append({"id": caso["id"], "classe": caso["classe"], "origem": caso["origem"], "saida": saida, "motivo_termino": estado.get("motivo_terminacao", "aguardando_humano"), **avaliacao})
        if args.imprimir:
            print(f"[{'OK ' if avaliacao['passou'] else 'FALHA'}] {caso['id']}: {saida['resultado']}")
            for c in avaliacao["checks"]:
                if not c["ok"]:
                    print(f"      falhou: {c['nivel']} / {c['check']}")

    servidor.shutdown()
    meta = {"versao": versao_rotulo, "modo": args.modo, "dataset_versao": DATASET_VERSAO, "sem_controles": args.sem_controles, "casos": len(resultados), "executado_em": datetime.now().isoformat(timespec="seconds")}
    (rodada / "resultado.json").write_text(json.dumps({"meta": meta, "casos": resultados}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    aprovados = sum(r["passou"] for r in resultados)
    print(f"rodada {rodada.name}: {aprovados}/{len(resultados)} casos passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
