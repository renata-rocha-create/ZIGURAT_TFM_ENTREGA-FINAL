"""
dashboard.py — Visualizações dos resultados da auditoria.

Etapa 2: aba "Por Elemento" — tabela de verificação elemento a elemento,
nível de confiança e comparação LLM × Python.
(Etapa 3 acrescenta aqui os KPIs e gráficos do dashboard.)
"""
import pandas as pd
import streamlit as st

ICONE_STATUS = {
    "Conforme": "✅ Conforme",
    "Não Conforme": "❌ Não Conforme",
    "Parcial": "▲ Parcial",
    "Indeterminado": "⚠️ Indeterminado",
    "N/A": "— N/A",
}
ICONE_CONF = {"ALTA": "🟢 Alta", "MEDIA": "🟡 Média", "BAIXA": "🔴 Baixa"}


def _card(valor, rotulo, cor=""):
    return (f'<div class="metric-card"><div class="metric-num {cor}">{valor}</div>'
            f'<div class="metric-label">{rotulo}</div></div>')


def render_aba_elementos(linhas: list[dict] | None, comparacao: dict | None) -> None:
    if not linhas:
        st.markdown(
            '<div class="info-box">Nenhuma verificação por elemento disponível. '
            'Execute a auditoria na aba <strong>Arquivos &amp; Execução</strong>.</div>',
            unsafe_allow_html=True)
        return

    df = pd.DataFrame(linhas)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    n = len(df)
    conf = (df.status == "Conforme").sum()
    nconf = (df.status == "Não Conforme").sum()
    indet = (df.status == "Indeterminado").sum()
    alta = (df.confianca == "ALTA").sum()
    taxa = comparacao.get("taxa_concordancia") if comparacao else None
    cards = [
        _card(n, "Verificações (elemento × item)", "c-blue"),
        _card(conf, "Conformes", "c-green"),
        _card(nconf, "Não conformes", "c-red"),
        _card(indet, "Indeterminados", "c-amber"),
        _card(f"{alta}/{n}", "Confiança alta", "c-muted"),
        _card(f"{taxa}%" if taxa is not None else "—", "Concordância LLM × Python", "c-purple"),
    ]
    st.markdown(f'<div class="metric-row">{"".join(cards)}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="info-box"><strong>Como ler esta aba:</strong> cada linha é um '
        '<em>elemento</em> verificado contra um <em>item</em> da NBR 9050, com a conta '
        'feita em Python (determinística). A <strong>confiança</strong> vem da origem do '
        'dado: 🟢 propriedade explícita do modelo · 🟡 geometria ou proxy (ex: cota Z) · '
        '🔴 inferência pelo nome do elemento.</div>', unsafe_allow_html=True)

    # ── Comparação LLM × Python ───────────────────────────────────────────────
    if comparacao and comparacao.get("tabela"):
        st.markdown('<div class="section-title">🤝 Status do item: LLM × Python</div>',
                    unsafe_allow_html=True)
        dc = pd.DataFrame(comparacao["tabela"])
        dc["status_llm"] = dc["status_llm"].map(lambda s: ICONE_STATUS.get(s, s))
        dc["status_python"] = dc["status_python"].map(lambda s: ICONE_STATUS.get(s, s))
        dc["concorda"] = dc["concorda"].map({True: "✔️", False: "✖️ divergente", None: "—"})
        st.dataframe(
            dc, hide_index=True, use_container_width=True,
            column_config={
                "item_nbr": "Item NBR", "categoria": "Categoria",
                "status_llm": "Status LLM", "status_python": "Status Python",
                "concorda": "Concorda?", "tipo": "Tipo de verificação",
            })
        st.caption(f"{comparacao['concordantes']} de {comparacao['comparaveis']} itens "
                   "comparáveis com o mesmo status. Divergências merecem inspeção: "
                   "ou o LLM errou, ou a regra em Python precisa de ajuste.")

    # ── Filtros ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🔎 Verificação por elemento</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
    f_status = c1.multiselect("Status", sorted(df.status.unique()), key="fe_status")
    f_item = c2.multiselect("Item NBR", sorted(df.item_nbr.unique()), key="fe_item")
    f_conf = c3.multiselect("Confiança", ["ALTA", "MEDIA", "BAIXA"], key="fe_conf")
    f_gid = c4.text_input("Buscar GlobalId", key="fe_gid")

    dv = df.copy()
    if f_status: dv = dv[dv.status.isin(f_status)]
    if f_item:   dv = dv[dv.item_nbr.isin(f_item)]
    if f_conf:   dv = dv[dv.confianca.isin(f_conf)]
    if f_gid:    dv = dv[dv.global_id.str.contains(f_gid.strip(), case=False, na=False)]

    dv_show = dv.assign(
        status=dv.status.map(lambda s: ICONE_STATUS.get(s, s)),
        confianca=dv.confianca.map(lambda c: ICONE_CONF.get(c, c)),
    )[["item_nbr", "categoria", "status", "confianca", "nome", "global_id", "pavimento",
       "valor_medido", "valor_exigido", "mensagem", "ifc_class", "fonte_dado"]]

    st.dataframe(
        dv_show, hide_index=True, use_container_width=True, height=420,
        column_config={
            "item_nbr": "Item", "categoria": "Categoria", "status": "Status",
            "confianca": "Confiança", "nome": "Elemento", "global_id": "GlobalId",
            "pavimento": "Pavimento", "valor_medido": "Medido", "valor_exigido": "Exigido",
            "mensagem": "Observação", "ifc_class": "Classe IFC", "fonte_dado": "Origem do dado",
        })
    st.caption(f"Exibindo {len(dv)} de {n} verificações.")

    st.download_button(
        "⬇️ Baixar tabela por elemento (CSV)",
        data=df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="verificacao_por_elemento.csv", mime="text/csv",
    )
