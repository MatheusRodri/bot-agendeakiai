"""Contratos de entrada e saída do agente."""

from pydantic import BaseModel, ConfigDict, Field


class EntradaAgente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str
    cliente_id: str
    conversa_id: str
    aprovar: bool = False


class SaidaAgente(BaseModel):
    resultado: str
    fontes: list[str] = Field(default_factory=list)
    suficiente: bool = False
