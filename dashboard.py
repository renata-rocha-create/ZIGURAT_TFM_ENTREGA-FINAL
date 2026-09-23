"""
dashboard.py — Visualizações dos resultados da auditoria.

Etapa 2: aba "Por Elemento" — tabela de verificação elemento a elemento,
nível de confiança e comparação LLM × Python.
(Etapa 3: aba "Dashboard" — KPIs, gráficos Altair e lista de ação.)
"""
import altair as alt
import pandas as pd
import streamlit as st

from verificacoes import classificar_prototipo, CATEGORIAS

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


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
# Gráficos em Altair — biblioteca que JÁ vem instalada junto com o Streamlit,
# então não é preciso mexer no requirements.txt.

CORES_STATUS = {
    "Conforme": "#1ab87a", "Parcial": "#7c3ac4", "Não Conforme": "#e03c3c",
    "Indeterminado": "#e8920a", "N/A": "#9ca3af",
}
CORES_CONF = {"ALTA": "#1ab87a", "MEDIA": "#f2c94c", "BAIXA": "#e03c3c"}
ROTULO_CONF = {"ALTA": "Alta", "MEDIA": "Média", "BAIXA": "Baixa"}
FONTE = "Trebuchet MS"


def _escala(mapa, dominio=None):
    dom = dominio or list(mapa.keys())
    return alt.Scale(domain=dom, range=[mapa[d] for d in dom])


def _estilo(chart, altura):
    return (chart.properties(height=altura)
            .configure(font=FONTE)
            .configure_axis(labelFontSize=11, titleFontSize=11, grid=False)
            .configure_legend(orient="bottom", labelFontSize=11, titleFontSize=11)
            .configure_view(strokeWidth=0))


def _grafico_status_por_item(df):
    d = df.groupby(["item_label", "status"]).size().reset_index(name="qtd")
    ordem = sorted(df.item_label.unique())
    dom = [s for s in CORES_STATUS if s in set(d.status)]
    ch = alt.Chart(d).mark_bar().encode(
        y=alt.Y("item_label:N", title=None, sort=ordem),
        x=alt.X("qtd:Q", title="Nº de elementos verificados"),
        color=alt.Color("status:N", title="Status", scale=_escala(CORES_STATUS, dom)),
        tooltip=[alt.Tooltip("item_label:N", title="Item"),
                 alt.Tooltip("status:N", title="Status"),
                 alt.Tooltip("qtd:Q", title="Elementos")],
    )
    return _estilo(ch, max(160, 34 * len(ordem)))


def _heatmap_pavimento_item(df):
    aval = df[df.status.isin(["Conforme", "Não Conforme"])]
    if aval.empty:
        return None
    g = (aval.assign(nc=(aval.status == "Não Conforme").astype(int))
             .groupby(["pavimento", "item_label"])
             .agg(nc=("nc", "sum"), total=("nc", "size")).reset_index())
    g["pct_nc"] = (g.nc / g.total * 100).round(0)
    g["rotulo"] = g.nc.astype(str) + "/" + g.total.astype(str)
    base = alt.Chart(g).encode(
        x=alt.X("item_label:N", title=None, axis=alt.Axis(labelAngle=-30)),
        y=alt.Y("pavimento:N", title=None),
    )
    rect = base.mark_rect(cornerRadius=4).encode(
        color=alt.Color("pct_nc:Q", title="% não conforme",
                        scale=alt.Scale(domain=[0, 100], range=["#e6faf3", "#e03c3c"])),
        tooltip=[alt.Tooltip("pavimento:N", title="Pavimento"),
                 alt.Tooltip("item_label:N", title="Item"),
                 alt.Tooltip("rotulo:N", title="Não conformes / avaliados"),
                 alt.Tooltip("pct_nc:Q", title="% não conforme")],
    )
    txt = base.mark_text(fontSize=12, fontWeight="bold").encode(
        text="rotulo:N",
        color=alt.condition("datum.pct_nc > 50", alt.value("white"), alt.value("#1a1d26")),
    )
    n_pav = g.pavimento.nunique()
    return _estilo(rect + txt, max(90, 55 * n_pav))


def _grafico_confianca(df):
    d = df.groupby(["item_label", "confianca"]).size().reset_index(name="qtd")
    d["conf_rotulo"] = d.confianca.map(ROTULO_CONF)
    ordem = sorted(df.item_label.unique())
    ch = alt.Chart(d).mark_bar().encode(
        y=alt.Y("item_label:N", title=None, sort=ordem),
        x=alt.X("qtd:Q", title="Nº de verificações", stack="normalize",
                axis=alt.Axis(format="%")),
        color=alt.Color("conf_rotulo:N", title="Confiança",
                        scale=alt.Scale(domain=["Alta", "Média", "Baixa"],
                                        range=[CORES_CONF["ALTA"], CORES_CONF["MEDIA"],
                                               CORES_CONF["BAIXA"]])),
        tooltip=[alt.Tooltip("item_label:N", title="Item"),
                 alt.Tooltip("conf_rotulo:N", title="Confiança"),
                 alt.Tooltip("qtd:Q", title="Verificações")],
    )
    return _estilo(ch, max(160, 34 * len(ordem)))


def render_dashboard(linhas: list[dict] | None, resultado: dict | None) -> None:
    if not linhas:
        st.markdown(
            '<div class="info-box">Execute a auditoria na aba <strong>Arquivos &amp; '
            'Execução</strong> para ver o dashboard.</div>', unsafe_allow_html=True)
        return

    df = pd.DataFrame(linhas)
    df["item_label"] = df.item_nbr + " · " + df.item_nbr.map(CATEGORIAS).fillna("")

    # ── Filtro de pavimento (vale para todo o dashboard) ─────────────────────
    pavs = sorted(df.pavimento.unique())
    if len(pavs) > 1:
        sel = st.multiselect("Filtrar pavimentos", pavs, key="dash_pav")
        if sel:
            df = df[df.pavimento.isin(sel)]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    aval = df[df.status.isin(["Conforme", "Não Conforme"])]
    pct = round((aval.status == "Conforme").mean() * 100, 1) if len(aval) else None
    proto = classificar_prototipo((resultado or {}).get("resultados", []))
    cor_proto = {"Completo": "c-green", "Parcial": "c-amber", "Incompleto": "c-red"}[proto["classe"]]
    alta_pct = round((df.confianca == "ALTA").mean() * 100) if len(df) else 0
    cards = [
        _card(f"{pct}%" if pct is not None else "—", "Conformidade por elemento", "c-green"),
        _card((df.status == "Não Conforme").sum(), "Elementos não conformes", "c-red"),
        _card(df.global_id.nunique(), "Elementos distintos auditados", "c-blue"),
        _card(f"{alta_pct}%", "Verificações c/ confiança alta", "c-muted"),
        _card(proto["classe"], f"Protótipo · {proto['avaliados']}/{proto['aplicaveis']} itens avaliados",
              cor_proto),
    ]
    st.markdown(f'<div class="metric-row">{"".join(cards)}</div>', unsafe_allow_html=True)

    # ── Gráficos ──────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-title">📊 Status por item da NBR</div>',
                    unsafe_allow_html=True)
        st.altair_chart(_grafico_status_por_item(df), use_container_width=True)
    with col2:
        st.markdown('<div class="section-title">🎯 Confiança dos dados por item</div>',
                    unsafe_allow_html=True)
        st.altair_chart(_grafico_confianca(df), use_container_width=True)

    st.markdown('<div class="section-title">🗺️ Onde estão os problemas: pavimento × item</div>',
                unsafe_allow_html=True)
    hm = _heatmap_pavimento_item(df)
    if hm is not None:
        st.altair_chart(hm, use_container_width=True)
        st.caption("Cada célula mostra não conformes / elementos avaliados. "
                   "Quanto mais vermelha, maior a concentração de falhas.")
    else:
        st.caption("Sem elementos avaliados (Conforme/Não Conforme) para o mapa.")

    # ── Lista de ação: não conformidades ─────────────────────────────────────
    nc = df[df.status == "Não Conforme"].sort_values(["item_nbr", "pavimento"])
    st.markdown(f'<div class="section-title">🛠️ Lista de ação — {len(nc)} não conformidades</div>',
                unsafe_allow_html=True)
    if nc.empty:
        st.caption("Nenhuma não conformidade por elemento. 🎉")
    else:
        st.dataframe(
            nc[["item_label", "nome", "pavimento", "valor_medido", "valor_exigido",
                "mensagem", "global_id"]].assign(),
            hide_index=True, use_container_width=True,
            column_config={
                "item_label": "Item", "nome": "Elemento", "pavimento": "Pavimento",
                "valor_medido": "Medido", "valor_exigido": "Exigido",
                "mensagem": "Observação", "global_id": "GlobalId",
            })
