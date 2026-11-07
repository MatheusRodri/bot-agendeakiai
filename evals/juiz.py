"""Juiz LLM para a propriedade FIDELIDADE, e sua validação contra rótulos humanos (§1.3).

  python -m evals.juiz preparar   cria evals/juiz_amostra.json (20 saídas reais do Gemini, sem rótulo)
  python -m evals.juiz julgar     o juiz preenche juiz_aprovado/juiz_motivo (rode DEPOIS da rotulagem humana)
  python -m evals.juiz validar    matriz de concordância, desacordos e evals/juiz_resultado.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
AMOSTRA = ROOT / "evals" / "juiz_amostra.json"
RESULTADO = ROOT / "evals" / "juiz_resultado.json"
RUBRICA = ROOT / "evals" / "rubrica-fidelidade-v1.txt"
RUBRICA_VERSAO = "1.0.0"
FONTE = ROOT / "dados" / "resultado-avaliacao-prompt.json"
# Limiar declarado ANTES de medir: o juiz só é adotado se concordar com o humano em >= 85% das 20 saídas.
LIMIAR_PCT = 85


class Veredito(BaseModel):
    aprovado: bool
    motivo: str


def _ler() -> list[dict]:
    return json.loads(AMOSTRA.read_text(encoding="utf-8"))


def _gravar(itens: list[dict]) -> None:
    AMOSTRA.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in itens), encoding="utf-8")


def preparar() -> None:
    casos = json.loads(FONTE.read_text(encoding="utf-8"))["casos"]
    itens = [{"id": f"{c['variante']}-{c['indice']:02d}", "pergunta": c["pergunta"], "esperada": c["resposta_esperada"], "resposta": c["saida"]["resultado"], "humano_aprovado": None, "humano_nota": "", "juiz_aprovado": None, "juiz_motivo": ""} for c in casos]
    assert len(itens) == 20, len(itens)
    _gravar(itens)
    print(f"{len(itens)} itens em {AMOSTRA}. Preencha humano_aprovado (true/false) e humano_nota em cada linha.")


def julgar() -> None:
    from dotenv import load_dotenv
    from google import genai
    from google.genai import types

    load_dotenv(ROOT / ".env")
    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    itens = _ler()
    for item in itens:
        pedido = f"pergunta: {item['pergunta']}\nRESPOSTA ESPERADA: {item['esperada']}\nRESPOSTA A AVALIAR: {item['resposta']}"
        r = cliente.models.generate_content(model=os.getenv("LLM_MODELO") or "gemini-3.8-flash", contents=pedido, config=types.GenerateContentConfig(system_instruction=RUBRICA.read_text(encoding="utf-8"), response_mime_type="application/json", response_schema=Veredito, temperature=0, max_output_tokens=800))
        v = Veredito.model_validate(json.loads(r.text))
        item["juiz_aprovado"], item["juiz_motivo"] = v.aprovado, v.motivo
        _gravar(itens)  # grava a cada item: retomável
        print(item["id"], v.aprovado)


def validar() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    itens = _ler()
    if any(i["humano_aprovado"] is None or i["juiz_aprovado"] is None for i in itens):
        raise SystemExit("Faltam rótulos humanos ou do juiz.")
    m = {(h, j): 0 for h in (True, False) for j in (True, False)}
    for i in itens:
        m[(i["humano_aprovado"], i["juiz_aprovado"])] += 1
    concordancia = round(100 * (m[(True, True)] + m[(False, False)]) / len(itens), 1)
    print("matriz (linhas=humano, colunas=juiz)\n               juiz aprova  juiz reprova")
    print(f"humano aprova  {m[(True, True)]:>11}  {m[(True, False)]:>12}")
    print(f"humano reprova {m[(False, True)]:>11}  {m[(False, False)]:>12}")
    print(f"concordância {concordancia}%  limiar {LIMIAR_PCT}%  -> {'ADOTADO' if concordancia >= LIMIAR_PCT else 'NÃO ADOTADO'}")
    desacordos = [i for i in itens if i["humano_aprovado"] != i["juiz_aprovado"]]
    for i in desacordos:
        print(f"\nDESACORDO {i['id']}: humano={i['humano_aprovado']} juiz={i['juiz_aprovado']}\n  resposta: {i['resposta']}\n  nota humana: {i['humano_nota']}\n  motivo juiz: {i['juiz_motivo']}\n  (classifique: defeito do juiz | da rubrica | do rótulo humano)")
    RESULTADO.write_text(json.dumps({"rubrica_versao": RUBRICA_VERSAO, "n": len(itens), "matriz": {f"humano_{h}_juiz_{j}": n for (h, j), n in m.items()}, "concordancia_pct": concordancia, "limiar_pct": LIMIAR_PCT, "adotado": concordancia >= LIMIAR_PCT, "desacordos": [i["id"] for i in desacordos]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    {"preparar": preparar, "julgar": julgar, "validar": validar}[sys.argv[1]]()
