"""
progresso_auditoria.py
----------------------
"Momento Manus" do Auditor NBR 9050: mostra, em tempo real, cada etapa da
auditoria dentro de um st.status, deixando visível a separação entre
Python (cálculo determinístico) e LLM (interpretação normativa).

Uso básico (dentro do app Streamlit):

    from progresso_auditoria import ProgressoAuditoria, mostrar_ultimo_log

    with ProgressoAuditoria("Auditando WC_TESTE.ifc") as avisar:
        avisar("IFC lido · IFC2X3 · 312 elementos")
        avisar("Vão livre das portas · 44 conformes, 3 não conformes",
               fonte="python", confianca="ALTA", alerta=True)
        avisar("Interpretando item 6.11 (sanitários)", fonte="llm",
               confianca="MÉDIA")

    # Em reruns (clique numa aba, filtro etc.), reexibe o último log:
    mostrar_ultimo_log()

O objeto "avisar" é um callback: pode ser passado para as funções do
pipeline, que chamam avisar("mensagem", ...) a cada etapa concluída.
Os módulos de auditoria NÃO precisam importar o Streamlit.
"""

from __future__ import annotations

import time
from html import escape

import streamlit as st

# Cores do sistema de design (Zigurat)
COR_PYTHON = "#009B77"   # verde oceânico  -> cálculo determinístico
COR_LLM = "#0066FF"      # azul elétrico   -> interpretação normativa
COR_ALERTA = "#C77700"   # âmbar           -> não conformidade encontrada
COR_TEXTO_SUAVE = "#6B6B6B"

CHAVE_LOG = "_log_auditoria"

_FONTES = {
    "python": ("Python · determinístico", COR_PYTHON),
    "llm": ("LLM · interpretativo", COR_LLM),
}


def avisar_nulo(*args, **kwargs) -> None:
    """Callback 'vazio': use como padrão nas funções do pipeline
    (ex.: def auditar(ifc, avisar=avisar_nulo)), para que elas funcionem
    também sem interface (benchmark, testes)."""
    return None


def _selo(texto: str, cor: str) -> str:
    """Pequena etiqueta colorida (badge) em HTML."""
    return (
        f'<span style="background:{cor}1A;color:{cor};border:1px solid {cor}55;'
        f'border-radius:6px;padding:1px 7px;font-size:0.72rem;font-weight:600;'
        f'margin-right:6px;white-space:nowrap;">{escape(texto)}</span>'
    )


def _linha_html(item: dict) -> str:
    """Monta uma linha do log a partir do dicionário salvo."""
    if item.get("erro"):
        icone = "✗"
        cor_icone = "#C0392B"
    elif item.get("alerta"):
        icone = "⚠"
        cor_icone = COR_ALERTA
    else:
        icone = "✓"
        cor_icone = COR_PYTHON

    partes = [
        f'<span style="color:{cor_icone};font-weight:700;margin-right:8px;">{icone}</span>'
    ]

    fonte = item.get("fonte")
    if fonte in _FONTES:
        rotulo, cor = _FONTES[fonte]
        partes.append(_selo(rotulo, cor))

    partes.append(f"<span>{escape(item['msg'])}</span>")

    if item.get("confianca"):
        partes.append(
            f'<span style="color:{COR_TEXTO_SUAVE};font-size:0.78rem;margin-left:8px;">'
            f'confiança {escape(str(item["confianca"]))}</span>'
        )

    if item.get("duracao") is not None:
        partes.append(
            f'<span style="color:{COR_TEXTO_SUAVE};font-size:0.75rem;margin-left:8px;">'
            f'{item["duracao"]:.1f} s</span>'
        )

    return (
        '<div style="display:flex;flex-wrap:wrap;align-items:center;'
        'gap:2px;padding:3px 0;line-height:1.5;">' + "".join(partes) + "</div>"
    )


class ProgressoAuditoria:
    """Context manager que abre um st.status, registra as etapas e fecha
    com check verde (sucesso) ou vermelho (erro), guardando o log no
    st.session_state para sobreviver aos reruns do Streamlit."""

    def __init__(self, titulo: str = "Auditando modelo...",
                 recolher_ao_final: bool = True):
        self.titulo = titulo
        self.recolher_ao_final = recolher_ao_final
        self._status = None
        self._inicio = 0.0
        self._ultima = 0.0
        self._itens: list[dict] = []

    # -- abertura / fechamento ------------------------------------------
    def __enter__(self):
        self._inicio = self._ultima = time.perf_counter()
        self._itens = []
        self._status = st.status(self.titulo, expanded=True, state="running")
        return self

    def __exit__(self, exc_type, exc, tb):
        total = time.perf_counter() - self._inicio
        if exc_type is None:
            rotulo = f"Auditoria concluída em {total:.1f} s"
            estado = "complete"
        else:
            self.__call__(f"Erro: {exc}", erro=True)
            rotulo = f"Auditoria interrompida após {total:.1f} s"
            estado = "error"

        self._status.update(
            label=rotulo,
            state=estado,
            expanded=(estado == "error") or not self.recolher_ao_final,
        )
        st.session_state[CHAVE_LOG] = {
            "rotulo": rotulo,
            "estado": estado,
            "itens": list(self._itens),
        }
        return False  # não esconde exceções: o erro continua visível

    # -- callback --------------------------------------------------------
    def __call__(self, msg: str, fonte: str | None = None,
                 confianca: str | None = None, alerta: bool = False,
                 erro: bool = False, mostrar_tempo: bool = True) -> None:
        """Registra uma etapa.

        msg        texto da etapa ("47 portas identificadas")
        fonte      "python", "llm" ou None (etapas gerais, ex.: leitura do IFC)
        confianca  "ALTA", "MÉDIA", "BAIXA" ou None
        alerta     True quando a etapa encontrou não conformidade (ícone ⚠)
        erro       True para falhas (ícone ✗)
        """
        agora = time.perf_counter()
        item = {
            "msg": str(msg),
            "fonte": (fonte or "").lower() or None,
            "confianca": confianca,
            "alerta": alerta,
            "erro": erro,
            "duracao": (agora - self._ultima) if mostrar_tempo else None,
        }
        self._ultima = agora
        self._itens.append(item)

        if self._status is not None:
            with self._status:
                st.markdown(_linha_html(item), unsafe_allow_html=True)

    def titulo_atual(self, texto: str) -> None:
        """Troca o título enquanto roda (ex.: 'Consultando LLM...')."""
        if self._status is not None:
            self._status.update(label=texto)


def mostrar_ultimo_log() -> None:
    """Reexibe o log da última auditoria (recolhido), para que ele não
    desapareça quando o usuário interage com o app."""
    log = st.session_state.get(CHAVE_LOG)
    if not log:
        return
    with st.status(log["rotulo"], state=log["estado"], expanded=False):
        for item in log["itens"]:
            st.markdown(_linha_html(item), unsafe_allow_html=True)


def limpar_log() -> None:
    """Apaga o log salvo (ex.: quando um novo IFC é carregado)."""
    st.session_state.pop(CHAVE_LOG, None)
