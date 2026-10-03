"""
teste_progresso.py
------------------
Página de demonstração do "momento Manus". NÃO usa o seu pipeline real:
simula as etapas com pausas, só para você ver o visual antes de integrar.

Rodar localmente:   streamlit run teste_progresso.py
"""

import time

import streamlit as st

from progresso_auditoria import ProgressoAuditoria, mostrar_ultimo_log

st.set_page_config(page_title="Teste · Progresso da auditoria", layout="centered")
st.title("Teste do progresso da auditoria")
st.caption("Simulação: os números abaixo são fictícios.")


def auditoria_simulada(avisar):
    """Imita o pipeline. No app real, esta função seria o seu pipeline,
    recebendo 'avisar' como parâmetro."""
    time.sleep(0.6)
    avisar("IFC lido · IFC2X3 · 312 elementos")

    time.sleep(0.5)
    avisar("47 portas, 2 rampas, 6 barras de apoio identificadas")

    time.sleep(0.4)
    avisar("Vão livre das portas · 44 conformes, 3 não conformes",
           fonte="python", confianca="ALTA", alerta=True)

    time.sleep(0.4)
    avisar("Inclinação das rampas · 2/2 conformes",
           fonte="python", confianca="ALTA")

    time.sleep(0.4)
    avisar("Área de giro Ø 1,50 m · 5/6 ambientes conformes",
           fonte="python", confianca="MÉDIA", alerta=True)

    avisar.titulo_atual("Consultando LLM...")
    time.sleep(1.5)
    avisar("Item 6.11 (sanitários acessíveis) interpretado",
           fonte="llm", confianca="MÉDIA")

    time.sleep(1.2)
    avisar("Laudo redigido · 12 itens avaliados", fonte="llm")


if st.button("Auditar (simulação)", type="primary"):
    with ProgressoAuditoria("Auditando WC_TESTE.ifc") as avisar:
        auditoria_simulada(avisar)
else:
    mostrar_ultimo_log()

st.divider()
st.write("Clique em outra coisa (abaixo) e veja que o log continua na tela:")
st.radio("Aba fictícia", ["Dashboard", "Por elemento", "3D"], horizontal=True)
