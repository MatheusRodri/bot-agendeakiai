"""Traces OpenTelemetry (convenções GenAI) exportados para arquivo JSONL."""

from __future__ import annotations

import json
import os
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

ROOT = Path(__file__).resolve().parents[1]
ARQUIVO_TRACES = Path(os.getenv("TRACES_ARQUIVO") or ROOT / "logs" / "traces.jsonl")


class ExportadorJsonl(SpanExporter):
    """Grava um span por linha: simples de ler, de filtrar e de versionar."""

    def export(self, spans) -> SpanExportResult:
        ARQUIVO_TRACES.parent.mkdir(parents=True, exist_ok=True)
        with ARQUIVO_TRACES.open("a", encoding="utf-8") as arquivo:
            for span in spans:
                contexto = span.get_span_context()
                linha = {
                    "trace_id": format(contexto.trace_id, "032x"),
                    "span_id": format(contexto.span_id, "016x"),
                    "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
                    "nome": span.name,
                    "inicio_ns": span.start_time,
                    "duracao_ms": round((span.end_time - span.start_time) / 1e6, 3),
                    "status": span.status.status_code.name,
                    "atributos": dict(span.attributes or {}),
                }
                arquivo.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
        return SpanExportResult.SUCCESS


_provedor = TracerProvider()
_provedor.add_span_processor(SimpleSpanProcessor(ExportadorJsonl()))
TRACER = _provedor.get_tracer("agendeakiai")


def json_curto(valor, limite: int = 2000) -> str:
    """Serializa para atributo de span, com teto de tamanho."""
    texto = json.dumps(valor, ensure_ascii=False, default=str)
    return texto if len(texto) <= limite else texto[:limite] + "...(truncado)"


__all__ = ["TRACER", "json_curto", "trace"]
