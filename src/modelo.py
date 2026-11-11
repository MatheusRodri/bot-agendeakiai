"""Chamadas opcionais ao Gemini: redigir a resposta final e recomendar serviços."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from .contratos import SaidaAgente


ROOT = Path(__file__).resolve().parents[1]
MAX_CUSTO_USD = 0.01
MAX_TOKENS_TOTAIS = 4000
MAX_TOKENS_SAIDA = 800


def responder_com_gemini(
    texto: str,
    resposta_base: str,
    fontes: list[str],
    suficiente: bool,
    *,
    prompt_override: str | None = None,
    custo_maximo_usd: float = MAX_CUSTO_USD,
) -> tuple[dict[str, Any], dict[str, int | float]]:
    load_dotenv(ROOT / ".env")
    chave = os.getenv("GEMINI_API_KEY", "")
    if not chave:
        raise ValueError("Defina GEMINI_API_KEY no .env para usar o modo Gemini.")
    if prompt_override is not None:
        prompt = prompt_override
    else:  # memória procedural: regras aprendidas, em texto, no system prompt
        prompt = (ROOT / "src" / "prompts" / "agente-v1.txt").read_text(encoding="utf-8")
        prompt += "\n\n" + (ROOT / "src" / "prompts" / "memoria-procedural.txt").read_text(encoding="utf-8")
    pedido = json.dumps({"pedido": texto, "resposta_verificada": resposta_base, "fontes": fontes, "suficiente": suficiente}, ensure_ascii=False)
    # Cada token consome pelo menos um byte; os bytes dão um teto conservador antes da chamada.
    entrada_estimada = len(prompt.encode("utf-8")) + len(pedido.encode("utf-8")) + 100
    entrada_usd = os.getenv("LLM_CUSTO_USD_POR_MILHAO_ENTRADA", "")
    saida_usd = os.getenv("LLM_CUSTO_USD_POR_MILHAO_SAIDA", "")
    if not entrada_usd or not saida_usd:
        raise ValueError("Informe os custos atuais por milhão de tokens antes de habilitar o modo Gemini.")
    taxa_entrada = float(entrada_usd)
    taxa_saida = float(saida_usd)
    custo_estimado = (entrada_estimada * taxa_entrada + MAX_TOKENS_SAIDA * taxa_saida) / 1_000_000
    limite_chamada = min(MAX_CUSTO_USD, custo_maximo_usd)
    if entrada_estimada + MAX_TOKENS_SAIDA > MAX_TOKENS_TOTAIS or custo_estimado > limite_chamada:
        raise ValueError(f"A chamada Gemini excederia o limite local de tokens ou de US$ {limite_chamada:.2f}.")
    cliente = genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=120_000))
    # Técnica: zero-shot; o modelo apenas reescreve fatos já conferidos pelo código.
    # Contrato: JSON SaidaAgente; schema e validação impedem campos extras e tipos inválidos.
    # Limite: fontes e suficiência vêm do fluxo local, que segue responsável por aprovação e escrita.
    resposta = cliente.models.generate_content(
        model=os.getenv("LLM_MODELO") or "gemini-3.8-flash",
        contents=pedido,
        config=types.GenerateContentConfig(
            system_instruction=prompt,
            response_mime_type="application/json",
            response_schema=SaidaAgente,
            temperature=0.2,
            max_output_tokens=MAX_TOKENS_SAIDA,
        ),
    )
    conteudo = resposta.text or "{}"
    objeto = SaidaAgente.model_validate(json.loads(conteudo)).model_dump()
    uso = resposta.usage_metadata
    tokens_entrada = (uso.prompt_token_count or 0) if uso else 0
    tokens_saida = (uso.candidates_token_count or 0) if uso else 0
    tokens_pensamento = (uso.thoughts_token_count or 0) if uso else 0
    custo_usd = (tokens_entrada * taxa_entrada + (tokens_saida + tokens_pensamento) * taxa_saida) / 1_000_000
    return objeto, {
        "tokens_entrada": tokens_entrada,
        "tokens_saida": tokens_saida,
        "tokens_pensamento": tokens_pensamento,
        "custo_usd": custo_usd,
    }


class RecomendacaoModelo(BaseModel):
    ids_servicos: list[int]
    motivo: str


TIMEOUT_RECOMENDACAO_MS = 15_000  # no chat o cliente espera na tela; acima disso usa as regras


def recomendar_servicos(pedido: str, catalogo: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, int | float]]:
    """O modelo escolhe serviços do catálogo; quem valida é controles.validar_recomendacao."""
    load_dotenv(ROOT / ".env")
    chave = os.getenv("GEMINI_API_KEY", "")
    if not chave:
        raise ValueError("Defina GEMINI_API_KEY no .env para usar o modo Gemini.")
    prompt = (ROOT / "src" / "prompts" / "recomendacao-v1.txt").read_text(encoding="utf-8")
    itens = [
        {"idServico": s["idServico"], "nome": s["nome"], "descricao": s.get("descricao", "")[:120], "valor": s["valor"], "duracaoMinutos": s["duracaoMinutos"]}
        for s in catalogo[:30]
    ]
    entrada = json.dumps({"pedido": pedido, "catalogo": itens}, ensure_ascii=False)
    entrada_estimada = len(prompt.encode("utf-8")) + len(entrada.encode("utf-8")) + 100
    entrada_usd = os.getenv("LLM_CUSTO_USD_POR_MILHAO_ENTRADA", "")
    saida_usd = os.getenv("LLM_CUSTO_USD_POR_MILHAO_SAIDA", "")
    if not entrada_usd or not saida_usd:
        raise ValueError("Informe os custos atuais por milhão de tokens antes de habilitar o modo Gemini.")
    taxa_entrada, taxa_saida = float(entrada_usd), float(saida_usd)
    custo_estimado = (entrada_estimada * taxa_entrada + MAX_TOKENS_SAIDA * taxa_saida) / 1_000_000
    if entrada_estimada + MAX_TOKENS_SAIDA > MAX_TOKENS_TOTAIS or custo_estimado > MAX_CUSTO_USD:
        raise ValueError(f"A chamada Gemini excederia o limite local de tokens ou de US$ {MAX_CUSTO_USD:.2f}.")
    cliente = genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=TIMEOUT_RECOMENDACAO_MS))
    resposta = cliente.models.generate_content(
        model=os.getenv("LLM_MODELO") or "gemini-3.8-flash",
        contents=entrada,
        config=types.GenerateContentConfig(
            system_instruction=prompt,
            response_mime_type="application/json",
            response_schema=RecomendacaoModelo,
            temperature=0.2,
            max_output_tokens=MAX_TOKENS_SAIDA,
        ),
    )
    objeto = RecomendacaoModelo.model_validate(json.loads(resposta.text or "{}")).model_dump()
    uso = resposta.usage_metadata
    tokens_entrada = (uso.prompt_token_count or 0) if uso else 0
    tokens_saida = (uso.candidates_token_count or 0) if uso else 0
    tokens_pensamento = (uso.thoughts_token_count or 0) if uso else 0
    custo_usd = (tokens_entrada * taxa_entrada + (tokens_saida + tokens_pensamento) * taxa_saida) / 1_000_000
    return objeto, {"tokens_entrada": tokens_entrada, "tokens_saida": tokens_saida, "tokens_pensamento": tokens_pensamento, "custo_usd": custo_usd}
