"""
regras.py — Carregamento das regras da NBR 9050 a partir de nbr9050_rules.json.
"""
import json
from pathlib import Path

import streamlit as st


# ── Regras da NBR 9050 — agora carregadas de nbr9050_rules.json ─────────────
# ANTES: ~130 linhas de dicionário Python hardcoded (REGRAS_NBR9050).
# DEPOIS: fonte única em JSON, versionável e editável sem tocar neste arquivo.
RULES_PATH = Path(__file__).parent / "nbr9050_rules.json"


@st.cache_data(show_spinner=False)
def carregar_regras(path: Path = RULES_PATH) -> dict:
    """
    Carrega nbr9050_rules.json uma vez por sessão (cache do Streamlit evita
    reler o arquivo do disco a cada interação do usuário).
    """
    if not path.exists():
        st.error(
            f"⚠️ Arquivo de regras não encontrado em `{path}`. "
            "Verifique se nbr9050_rules.json está na raiz do repositório, "
            "junto de nbr9050_app.py."
        )
        return {"itens": []}
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if "itens" not in payload or not isinstance(payload["itens"], list):
        st.error("⚠️ nbr9050_rules.json malformado: chave 'itens' ausente ou inválida.")
        return {"itens": []}
    return payload


def obter_regras_lista() -> list[dict]:
    """Lista de itens no novo formato (entidades/estrategias aninhados, prompt_llm)."""
    return carregar_regras()["itens"]
