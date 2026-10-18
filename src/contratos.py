"""Contratos de entrada e saída do agente."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntradaAgente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str
    cliente_id: str
    conversa_id: str
    aprovar: bool = False

    @field_validator("texto", "cliente_id", "conversa_id")
    @classmethod
    def exigir_valor_nao_vazio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O campo não pode ficar vazio.")
        return valor


class SaidaAgente(BaseModel):
    resultado: str
    fontes: list[str] = Field(default_factory=list)
    suficiente: bool = False
