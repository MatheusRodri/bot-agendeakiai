"""Versão do sistema, gravada em todo trace (atributo da raiz)."""

import os

# VERSAO_SISTEMA no ambiente permite a suíte rodar rotulada como a versão anterior (ver docs/evals.md).
VERSAO_SISTEMA = os.getenv("VERSAO_SISTEMA", "3.1.0")
