"""Executa os quatro casos obrigatórios e grava seus logs."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib import request

from .main import build_agent, state_as_log


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    {
        "arquivo": "01-caso-simples.json",
        "nome": "caso simples com escrita confirmada",
        "cliente_id": "cliente-001",
        "confirmado": True,
        "mensagem": (
            "Quero um penteado clássico para um casamento em clima quente, no Centro, até R$ 150. "
            "Confirmo o agendamento da melhor opção encontrada."
        ),
    },
    {
        "arquivo": "02-divergencia.json",
        "nome": "preferência atual diverge do histórico",
        "cliente_id": "cliente-001",
        "confirmado": False,
        "mensagem": "Apesar de eu normalmente escolher algo moderno, hoje quero penteado clássico no Centro até R$ 150.",
    },
    {
        "arquivo": "03-registro-inexistente.json",
        "nome": "cliente inexistente",
        "cliente_id": "cliente-inexistente",
        "confirmado": False,
        "mensagem": "Quero um corte profissional para entrevista em Moema até R$ 100.",
    },
    {
        "arquivo": "04-sem-acao-principal.json",
        "nome": "consulta sem autorização de escrita",
        "cliente_id": "cliente-002",
        "confirmado": False,
        "mensagem": "Só quero comparar maquiagem natural para formatura até R$ 150; não quero reservar agora.",
    },
]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_api(url: str) -> None:
    for _ in range(30):
        try:
            with request.urlopen(f"{url}/saude", timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("A API mock não iniciou a tempo.")


def main() -> int:
    port = _free_port()
    api_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    processo = subprocess.Popen(
        [sys.executable, "-m", "src.mock_api", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_api(api_url)
        logs_dir = ROOT / "logs"
        logs_dir.mkdir(exist_ok=True)
        for case in CASES:
            agent = build_agent(case["cliente_id"], use_mock=True, api_url=api_url)
            state = agent.run(case["mensagem"], case["cliente_id"], case["confirmado"])
            log = state_as_log(state, agent.model.name)
            log["caso"] = case["nome"]
            (logs_dir / case["arquivo"]).write_text(
                json.dumps(log, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f'{case["arquivo"]}: {state.motivo_terminacao} — {state.resposta}')
        return 0
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=2)
        except subprocess.TimeoutExpired:
            processo.kill()


if __name__ == "__main__":
    raise SystemExit(main())
