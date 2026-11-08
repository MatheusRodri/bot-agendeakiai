"""Remove memórias, checkpoints e logs associados a um cliente."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .grafo import CHECKPOINTER
from .memoria import carregar, salvar
from .telemetria import ARQUIVO_TRACES


ROOT = Path(__file__).resolve().parents[1]


def remover_traces(cliente_id: str, arquivo: Path = ARQUIVO_TRACES) -> int:
    """Apaga do JSONL de traces todo trace cuja raiz tem o cliente_id (a raiz e seus spans filhos)."""
    if not arquivo.exists():
        return 0
    linhas = [linha for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha.strip()]
    spans = [json.loads(linha) for linha in linhas]
    removidos = {span["trace_id"] for span in spans if span.get("atributos", {}).get("cliente_id") == cliente_id}
    restantes = [linha for linha, span in zip(linhas, spans) if span["trace_id"] not in removidos]
    arquivo.write_text("".join(linha + "\n" for linha in restantes), encoding="utf-8")
    return len(removidos)


def remover_dados_cliente(cliente_id: str) -> dict[str, int]:
    memoria = carregar()
    antes = len(memoria["episodios"])
    memoria["episodios"] = [item for item in memoria["episodios"] if item["cliente_id"] != cliente_id]
    episodios = antes - len(memoria["episodios"])
    memoria["preferencias"].pop(cliente_id, None)
    salvar(memoria)

    conversas = {
        item.config.get("configurable", {}).get("thread_id")
        for item in CHECKPOINTER.list(None)
        if item.checkpoint.get("channel_values", {}).get("cliente_id") == cliente_id
    }
    logs_removidos = 0
    for caminho in (ROOT / "logs").glob("*.json"):
        try:
            log = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if log.get("entrada", {}).get("cliente_id") == cliente_id:
            conversa = log.get("entrada", {}).get("conversa_id")
            if conversa:
                conversas.add(conversa)
            caminho.unlink()
            logs_removidos += 1
    for conversa in conversas:
        CHECKPOINTER.delete_thread(conversa)
    return {"episodios_removidos": episodios, "checkpoints_removidos": len(conversas), "logs_removidos": logs_removidos, "traces_removidos": remover_traces(cliente_id)}


def main() -> int:
    analisador = argparse.ArgumentParser(description="Apaga dados locais de um cliente fictício")
    analisador.add_argument("--cliente-id", required=True)
    analisador.add_argument("--confirmar", action="store_true", help="confirma a remoção permanente dos dados locais")
    argumentos = analisador.parse_args()
    if not argumentos.confirmar:
        analisador.error("informe --confirmar para remover memórias, checkpoints e logs")
    print(json.dumps(remover_dados_cliente(argumentos.cliente_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
