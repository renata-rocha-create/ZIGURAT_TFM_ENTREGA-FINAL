"""
♿ Auditor de Acessibilidade BIM — NBR 9050:2020
Streamlit App — Verificação Automatizada de Conformidade
Master Internacional em IA para Arquitetura e Construção — Zigurat Institute of Technology

Este arquivo contém apenas a INTERFACE (sidebar, abas, botões).
A lógica fica nos módulos:
    ui_style.py      → identidade visual (CSS) e badges
    extracao.py      → leitura do IFC
    regras.py        → regras da NBR 9050 (nbr9050_rules.json)
    llm_auditor.py   → prompt e chamada ao Claude/Gemini
    verificacoes.py  → classificação de status e resumo determinístico
    relatorios.py    → HTML e XLSX
"""

import streamlit as st
import json
import os
import tempfile
from datetime import datetime

# ── Page config (precisa ser o PRIMEIRO comando Streamlit) ───────────────────
st.set_page_config(
    page_title="Auditor NBR 9050 — BIM",
    page_icon="♿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Módulos do projeto ───────────────────────────────────────────────────────
from ui_style import aplicar_estilo, status_badge
from extracao import extract_ifc_elements
from regras import obter_regras_lista
from llm_auditor import build_audit_prompt, call_anthropic, call_gemini
from verificacoes import (classificar_status, calcular_resumo,
                          gerar_verificacoes, comparar_com_llm)
from dashboard import render_aba_elementos
from relatorios import gerar_relatorio_html, gerar_excel

aplicar_estilo()


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k, v in {
    "resultado": None,
    "elementos": None,
    "logs": [],
    "running": False,
    "ifc_nome": "",
    "verificacoes": None,   # tabela por elemento (Etapa 2)
    "comparacao": None,     # status LLM × Python (Etapa 2)
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 1.5rem 0;border-bottom:2px solid rgb(68,205,148);margin-bottom:1rem">
      <img src="https://www.e-zigurat.com/images/logo.svg"
           style="height:28px;display:block;margin-bottom:0.75rem" alt="Zigurat" />
      <div style="font-family:'Trebuchet MS',Trebuchet,sans-serif;font-size:1rem;font-weight:700;color:rgb(28,96,241)">
        &#9855; NBR 9050 Auditor
      </div>
      <div style="font-family:'Trebuchet MS',Trebuchet,sans-serif;font-size:0.65rem;color:rgb(77,83,99);text-transform:uppercase;letter-spacing:0.1em">
        BIM Accessibility Checker
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**🔑 Provedor de IA**")
    st.markdown("""
    <div style="font-family:'Trebuchet MS',sans-serif;font-size:0.7rem;font-weight:700;
                color:rgb(77,83,99);text-transform:uppercase;letter-spacing:0.1em;
                margin-bottom:0.5rem">
      ⚙️ Configuração
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Provedor de IA**")
    provider = st.selectbox("Provedor", ["Anthropic (Claude)", "Google (Gemini)"], label_visibility="collapsed")

    st.markdown("""
    <div style="font-family:'Trebuchet MS',sans-serif;font-size:0.78rem;font-weight:600;
                color:#1a1d26;margin-bottom:2px">
      🔑 Chave API
    </div>
    <div style="font-family:'Trebuchet MS',sans-serif;font-size:0.65rem;color:#6b7280;
                margin-bottom:4px">
      Não armazenada • Apenas nesta sessão
    </div>
    """, unsafe_allow_html=True)
    api_key = st.text_input(
        "Chave API",
        type="password",
        placeholder="sk-ant-..." if "Anthropic" in provider else "AIza...",
        help="Sua chave de API. Não é armazenada nem enviada a terceiros.",
        label_visibility="collapsed"
    )

    st.markdown("**🤖 Modelo LLM**")
    if "Anthropic" in provider:
        model_options = [
            "claude-haiku-4-5",
            "claude-sonnet-4-5",
            "claude-opus-4-5",
        ]
        model_labels = {
            "claude-haiku-4-5":  "Claude Haiku 4.5 (rápido, econômico)",
            "claude-sonnet-4-5": "Claude Sonnet 4.5 (balanceado)",
            "claude-opus-4-5":   "Claude Opus 4.5 (máxima qualidade)",
        }
    else:
        model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
        model_labels = {
            "gemini-1.5-flash": "Gemini 1.5 Flash (rápido)",
            "gemini-1.5-pro": "Gemini 1.5 Pro (balanceado)",
            "gemini-2.0-flash": "Gemini 2.0 Flash (novo)",
        }

    selected_model = st.selectbox(
        "Modelo",
        model_options,
        format_func=lambda x: model_labels.get(x, x),
        label_visibility="collapsed"
    )

    temperature = 0.0  # Fixo em 0.0 — determinístico para auditoria normativa

    st.markdown("---")
    st.markdown("""
    <div style="font-family:'Trebuchet MS',sans-serif;padding-top:0.25rem;line-height:1.8">
      <div style="color:rgb(68,205,148);font-weight:700;font-size:0.72rem;
                  margin-bottom:0.4rem;letter-spacing:0.05em">TFM | Grupo 1</div>
      <div style="font-size:0.65rem;color:rgb(77,83,99)">
        Kevin Dias Quintian<br>
        Renata Gomes Rocha<br>
        Sergio Rosenboim<br>
        Viviane Nishizaki Suzuke<br>
        William Felipe dos Santos Moura
      </div>
      <div style="margin-top:0.6rem;padding-top:0.5rem;
                  border-top:1px solid var(--border);
                  color:#9ca3af;font-size:0.6rem">
        Master IA para AEC &middot; Zigurat Institute of Technology
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero-block">
  <div class="hero-left">
    <div class="hero-title">&#9855; Auditor de Acessibilidade BIM</div>
    <div class="hero-sub">
      Verificação Automatizada de Conformidade &nbsp;·&nbsp;
      <strong style="color:rgba(255,255,255,0.85)">ABNT NBR 9050:2020</strong>
    </div>
  </div>
  <img src="https://www.e-zigurat.com/images/logo.svg"
       style="height:36px;flex-shrink:0"
       alt="Zigurat Institute of Technology" />
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_upload, tab_resultado, tab_elementos, tab_ajuda = st.tabs(
    ["📁 Arquivos & Execução", "📊 Resultados", "🔎 Por Elemento", "❓ Ajuda"])

# ─────────────────────────────────────────────
with tab_upload:

    # ── Upload card — só o IFC (checklist agora vem sempre de nbr9050_rules.json) ──
    st.markdown("""
    <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem">
      <div class="section-title" style="margin:0">📐 Modelo BIM</div>
      <span style="background:rgb(28,96,241);color:#fff;font-size:0.6rem;
                   font-weight:700;padding:2px 8px;border-radius:10px;
                   letter-spacing:0.05em">OBRIGATÓRIO</span>
    </div>
    <div style="font-size:0.75rem;color:#6b7280;margin-bottom:0.5rem">
      Arquivo IFC exportado do Revit, ArchiCAD ou Vectorworks.
      Suporta schemas <strong>IFC2X3</strong> e <strong>IFC4</strong>.
    </div>
    """, unsafe_allow_html=True)
    ifc_file = st.file_uploader(
        "Arquivo IFC",
        type=["ifc"],
        help="Formato IFC2X3 ou IFC4. Exportado via Revit, ArchiCAD, Vectorworks etc.",
        label_visibility="collapsed"
    )
    if ifc_file:
        st.markdown(f"""
        <div style="background:rgba(68,205,148,0.08);border:1px solid rgba(68,205,148,0.4);
                    border-radius:6px;padding:0.6rem 0.85rem;margin-top:0.5rem;
                    font-size:0.8rem">
          ✅ <strong>{ifc_file.name}</strong>
          <span style="font-family:'Courier New',monospace;color:#6b7280;font-size:0.72rem;margin-left:8px">
            {ifc_file.size / 1024 / 1024:.1f} MB
          </span>
        </div>""", unsafe_allow_html=True)

    n_regras = len(obter_regras_lista())
    st.markdown(f"""
    <div style="background:#f4f6f9;border:1px solid #e5e7eb;border-radius:6px;
                padding:0.6rem 0.85rem;margin-top:0.75rem;font-size:0.75rem;color:#6b7280">
      📋 Checklist NBR carregado de <code>nbr9050_rules.json</code> — {n_regras} itens verificáveis.
    </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Stepper — 3 passos (checklist deixou de ser upload, é automático) ────
    step1 = "done" if api_key else "active"
    step2 = "done" if (api_key and ifc_file) else ("active" if api_key else "pending")
    step3 = "active" if (api_key and ifc_file) else "pending"

    def step_dot(state, n):
        colors = {"done": "rgb(68,205,148)", "active": "rgb(28,96,241)", "pending": "#d1d5de"}
        text_c = {"done": "#fff", "active": "#fff", "pending": "#9ca3af"}
        icon   = {"done": "✓", "active": str(n), "pending": str(n)}
        pulse  = 'animation:pulse 1.5s infinite' if state == "active" else ""
        return f"""<div style="width:28px;height:28px;border-radius:50%;
                    background:{colors[state]};color:{text_c[state]};
                    display:flex;align-items:center;justify-content:center;
                    font-size:0.72rem;font-weight:700;flex-shrink:0;{pulse}">
                    {icon[state]}</div>"""

    def step_label(label, sublabel, state):
        c = "rgb(28,96,241)" if state == "done" else ("#1a1d26" if state == "active" else "#9ca3af")
        return f"""<div>
          <div style="font-size:0.8rem;font-weight:700;color:{c}">{label}</div>
          <div style="font-size:0.65rem;color:#6b7280">{sublabel}</div>
        </div>"""

    arrow = '<div style="color:#d1d5de;font-size:0.9rem;padding:0 4px">→</div>'

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:6px;padding:1rem 1.25rem;
                background:#f4f6f9;border:1px solid #e5e7eb;border-radius:8px;
                margin-bottom:1.5rem;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        {step_dot(step1,1)}
        {step_label("API Key","Provedor + chave",step1)}
      </div>
      {arrow}
      <div style="display:flex;align-items:center;gap:8px">
        {step_dot(step2,2)}
        {step_label("Modelo IFC","Arquivo .ifc obrigatório",step2)}
      </div>
      {arrow}
      <div style="display:flex;align-items:center;gap:8px">
        {step_dot(step3,3)}
        {step_label("Executar","Iniciar auditoria",step3)}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── can_run e mensagens de estado ─────────────────────────────────────
    can_run = bool(ifc_file and api_key)

    # Mensagens de estado inline (sem warn-box solta)
    if not api_key and not ifc_file:
        st.markdown("""
        <div class="info-box">
          Complete os passos <strong>① e ②</strong> na barra lateral e acima para habilitar a auditoria.
        </div>""", unsafe_allow_html=True)
    elif not api_key:
        st.markdown('<div class="warn-box">⚠️ Passo ① — Insira sua chave API na barra lateral.</div>', unsafe_allow_html=True)
    elif not ifc_file:
        st.markdown('<div class="warn-box">⚠️ Passo ② — Carregue um arquivo IFC acima.</div>', unsafe_allow_html=True)

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run = st.button("▶ Executar Auditoria", disabled=not can_run, use_container_width=True)

    # ── Execution ──────────────────────────────────────────────────────────────
    if run and can_run:
        st.session_state.logs = []
        st.session_state.resultado = None
        st.session_state.verificacoes = None
        st.session_state.comparacao = None

        log_box = st.empty()
        step_box = st.empty()
        progress_bar = st.progress(0)

        def log(msg: str):
            ts = datetime.now().strftime("%H:%M:%S")
            st.session_state.logs.append(f"[{ts}] {msg}")
            log_content = "\n".join(st.session_state.logs[-20:])
            log_box.markdown(f'<div class="terminal">{log_content}</div>', unsafe_allow_html=True)

        try:
            # Step 1 — Save IFC
            log("🔄 Salvando arquivo IFC temporariamente...")
            progress_bar.progress(10)
            with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
                tmp.write(ifc_file.read())
                tmp_path = tmp.name
            st.session_state.ifc_nome = ifc_file.name
            log(f"✅ IFC salvo: {ifc_file.name} ({ifc_file.size/1024/1024:.1f} MB)")

            # Step 2 — Extract IFC elements
            log("🔍 Extraindo elementos do modelo IFC (IfcOpenShell)...")
            progress_bar.progress(25)
            elementos = extract_ifc_elements(tmp_path)
            if "error" in elementos:
                st.error(elementos["error"])
                st.stop()
            resumo_ext = {k: len(v) for k, v in elementos.get("elementos", {}).items()}
            log(f"✅ Elementos extraídos: {resumo_ext}")
            log(f"   Schema IFC detectado: {elementos.get('schema','?')}")
            st.session_state.elementos = elementos

            # Step 2b — Verificação por elemento (Python, determinística)
            linhas = gerar_verificacoes(elementos)
            st.session_state.verificacoes = linhas
            n_nc = sum(1 for l in linhas if l["status"] == "Não Conforme")
            log(f"🧮 Verificação por elemento (Python): {len(linhas)} verificações | ❌ {n_nc} não conformes")
            progress_bar.progress(45)

            # Step 3 — Load rules (sempre do JSON — sem upload de checklist)
            n_regras = len(obter_regras_lista())
            log(f"📋 Usando checklist de nbr9050_rules.json ({n_regras} itens).")
            progress_bar.progress(55)

            # Step 4 — Build prompt
            log("📝 Construindo prompt de auditoria...")
            prompt = build_audit_prompt(elementos, ifc_file.name)
            log(f"   Prompt: ~{len(prompt)//4:,} tokens estimados")
            progress_bar.progress(65)

            # Step 5 — Call LLM
            log(f"🤖 Chamando {selected_model} ({provider})...")
            log("   Aguarde — isso pode levar 30–90 segundos...")
            progress_bar.progress(70)

            if "Anthropic" in provider:
                resultado = call_anthropic(api_key, selected_model, prompt, temperature)
            else:
                resultado = call_gemini(api_key, selected_model, prompt, temperature)

            progress_bar.progress(90)
            log(f"✅ Auditoria concluída!")

            # Sobrescreve campos que o Python já conhece com certeza — não faz
            # sentido confiar que o LLM vai ecoar corretamente algo que já está
            # disponível antes mesmo da chamada (mesmo princípio do resumo abaixo).
            # Foi assim que pegamos o bug: numa rodada real, o LLM devolveu
            # "2024-01-15" no lugar da data certa (10/07/2026), ignorando o
            # exemplo que já estava no prompt.
            resultado["modelo"] = ifc_file.name
            resultado["schema_ifc"] = elementos.get("schema", resultado.get("schema_ifc", "—"))
            resultado["data_auditoria"] = datetime.now().strftime("%d/%m/%Y")

            # Recalcula o resumo em Python — determinístico, não depende do LLM
            # ter feito a soma/divisão certa (ver calcular_resumo() para o porquê).
            resultado["resumo"] = calcular_resumo(resultado.get("resultados", []))
            log("🧮 Resumo e metadados recalculados em Python (não dependem do eco do LLM).")

            # Comparação item a item: status do LLM × status calculado em Python
            comparacao = comparar_com_llm(st.session_state.verificacoes, resultado.get("resultados", []))
            st.session_state.comparacao = comparacao
            resultado["verificacoes_por_elemento"] = st.session_state.verificacoes
            resultado["comparacao_llm_python"] = comparacao
            if comparacao["taxa_concordancia"] is not None:
                log(f"🤝 Concordância LLM × Python: {comparacao['concordantes']}/{comparacao['comparaveis']} itens ({comparacao['taxa_concordancia']}%)")

            resumo = resultado["resumo"]
            log(f"   Total: {resumo.get('total',0)} | ✅ {resumo.get('conformes',0)} | ▲ {resumo.get('parciais',0)} | ❌ {resumo.get('nao_conformes',0)} | ⚠️ {resumo.get('indeterminados',0)}")
            log(f"   Conformidade: {resumo.get('percentual_conformidade')} (bruta) | {resumo.get('percentual_sobre_verificaveis')} (sobre itens verificáveis, exclui N/A)")

            st.session_state.resultado = resultado
            progress_bar.progress(100)
            log("🎉 Relatório pronto! Acesse a aba 'Resultados'.")

            # Cleanup
            os.unlink(tmp_path)

        except json.JSONDecodeError as e:
            log(f"❌ Erro ao parsear resposta JSON do modelo: {e}")
            st.error("O modelo não retornou JSON válido. Tente novamente ou ajuste o modelo/temperatura.")
        except Exception as e:
            log(f"❌ Erro: {e}")
            st.error(f"Erro durante a execução: {e}")


# ─────────────────────────────────────────────
with tab_resultado:
    if st.session_state.resultado is None:
        st.markdown("""
        <div style="text-align:center;padding:4rem 2rem;color:#334155">
          <div style="font-size:3rem;margin-bottom:1rem">📊</div>
          <div style="font-family:'Syne',sans-serif;font-size:1.1rem;color:#475569">
            Nenhuma auditoria executada ainda.
          </div>
          <div style="font-size:0.82rem;color:#334155;margin-top:0.5rem">
            Vá para a aba <strong>Arquivos & Execução</strong> e clique em <strong>Executar Auditoria</strong>.
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        resultado = st.session_state.resultado
        resumo = resultado.get("resumo", {})
        itens = resultado.get("resultados", [])

        # Metrics
        total   = resumo.get("total", len(itens))
        conf    = resumo.get("conformes", 0)
        parc    = resumo.get("parciais", 0)
        nconf   = resumo.get("nao_conformes", 0)
        indet   = resumo.get("indeterminados", 0)
        na      = resumo.get("na", 0)
        pct     = resumo.get("percentual_conformidade", "—")
        pct_ver = resumo.get("percentual_sobre_verificaveis", "—")

        st.markdown(f"""
        <div class="metric-row">
          <div class="metric-card"><div class="metric-num c-blue">{total}</div><div class="metric-label">Total</div></div>
          <div class="metric-card"><div class="metric-num c-green">{conf}</div><div class="metric-label">Conformes</div></div>
          <div class="metric-card"><div class="metric-num c-purple">{parc}</div><div class="metric-label">Parciais</div></div>
          <div class="metric-card"><div class="metric-num c-red">{nconf}</div><div class="metric-label">Não Conformes</div></div>
          <div class="metric-card"><div class="metric-num c-amber">{indet}</div><div class="metric-label">Indeterminados</div></div>
          <div class="metric-card"><div class="metric-num c-muted">{na}</div><div class="metric-label">N/A</div></div>
          <div class="metric-card"><div class="metric-num c-green">{pct}</div><div class="metric-label">Conformidade (bruta)</div></div>
          <div class="metric-card"><div class="metric-num c-blue">{pct_ver}</div><div class="metric-label">Conformidade (s/ N/A)</div></div>
        </div>
        """, unsafe_allow_html=True)

        # Observações
        obs = resultado.get("observacoes_gerais", "")
        if obs:
            st.markdown(f'<div class="info-box">💬 <strong>Análise Geral:</strong> {obs}</div>', unsafe_allow_html=True)

        st.markdown("---")

        # GlobalId explanation
        st.markdown("""
        <div class="info-box">
          <strong>🔑 Sobre o GlobalId</strong><br>
          O relatório inclui o <code>GlobalId</code> de cada elemento IFC verificado — é o identificador único do elemento no modelo, como um "CPF" do componente BIM.<br>
          <strong>Como usar no Revit:</strong> aba <em>Manage → Inquiry → IFC GUID</em> para localizar o elemento diretamente.
          No <strong>BIMcollab Zoom</strong>, <strong>Solibri</strong> ou <strong>usBIM viewer</strong> (gratuitos), cole o GlobalId no campo de busca para selecionar o elemento instantaneamente.
        </div>
        """, unsafe_allow_html=True)

        # Filters
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filter_status = st.multiselect(
                "Filtrar por Status",
                ["Conforme", "Parcial", "Não Conforme", "Indeterminado", "N/A"],
                default=["Conforme", "Parcial", "Não Conforme", "Indeterminado", "N/A"]
            )
        with col_f2:
            cats = sorted(set(it.get("categoria","") for it in itens if it.get("categoria")))
            filter_cat = st.multiselect("Filtrar por Categoria", cats, default=cats)
        with col_f3:
            search_gid = st.text_input("Buscar GlobalId", placeholder="0yScV...", help="Filtra pelo GlobalId do elemento IFC")

        # Table
        itens_filtrados = [
            it for it in itens
            if it.get("status","") in filter_status
            and it.get("categoria","") in filter_cat
            and (not search_gid or search_gid.lower() in it.get("globalid","").lower())
        ]

        st.markdown(f"""
        <div class="section-title">
          📋 Itens Verificados
          <span style="font-weight:400;color:#475569;font-size:0.75rem">— {len(itens_filtrados)} de {len(itens)} itens</span>
        </div>
        """, unsafe_allow_html=True)

        # Build table HTML
        rows_html = ""
        for it in itens_filtrados:
            gid = it.get("globalid", "—")
            gid_chip = f'<span class="globalid" title="GlobalId para filtro no Revit">{gid}</span>' if gid != "—" else "—"
            rows_html += f"""
            <tr>
              <td style="font-family:var(--mono);color:#94a3b8;white-space:nowrap">{it.get('item_nbr','—')}</td>
              <td style="color:#cbd5e1">{it.get('categoria','—')}</td>
              <td style="color:#e2e8f0">{it.get('elemento','—')}</td>
              <td>{status_badge(it.get('status','N/A'))}</td>
              <td style="font-family:var(--mono);font-size:0.78rem;color:#94a3b8">{it.get('valor_encontrado','—')}</td>
              <td style="font-family:var(--mono);font-size:0.78rem;color:#94a3b8">{it.get('valor_exigido','—')}</td>
              <td>{gid_chip}</td>
              <td style="font-family:var(--mono);font-size:0.72rem;color:#475569">{it.get('tipo_ifc','—')}</td>
              <td style="font-size:0.8rem;color:#f87171">{it.get('recomendacao','—') if classificar_status(it.get('status','')) in ('Não Conforme','Parcial','Indeterminado') else '<span style="color:#64748b">—</span>'}</td>
            </tr>"""

        st.markdown(f"""
        <div style="overflow-x:auto">
        <table class="result-table">
          <thead>
            <tr>
              <th>Item NBR</th><th>Categoria</th><th>Elemento</th><th>Status</th>
              <th>Valor Encontrado</th><th>Valor Exigido</th>
              <th>GlobalId 🔍</th><th>Tipo IFC</th><th>Recomendação</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="section-title">⬇️ Exportar Relatório</div>', unsafe_allow_html=True)

        col_dl1, col_dl2, col_dl3 = st.columns(3)
        modelo_nome = st.session_state.ifc_nome or "modelo"
        ts = datetime.now().strftime("%Y%m%d_%H%M")

        with col_dl1:
            html_bytes = gerar_relatorio_html(resultado, modelo_nome).encode("utf-8")
            st.download_button(
                "📄 Baixar Relatório HTML",
                data=html_bytes,
                file_name=f"relatorio_nbr9050_{ts}.html",
                mime="text/html",
                use_container_width=True,
            )

        with col_dl2:
            xlsx_bytes = gerar_excel(resultado, modelo_nome)
            if xlsx_bytes:
                st.download_button(
                    "📊 Baixar Checklist XLSX",
                    data=xlsx_bytes,
                    file_name=f"checklist_nbr9050_{ts}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        with col_dl3:
            json_bytes = json.dumps(resultado, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "🗂 Baixar JSON Completo",
                data=json_bytes,
                file_name=f"auditoria_nbr9050_{ts}.json",
                mime="application/json",
                use_container_width=True,
            )

        # JSON expandable
        with st.expander("🔍 Ver JSON bruto da auditoria"):
            st.json(resultado)


# ─────────────────────────────────────────────
with tab_elementos:
    render_aba_elementos(st.session_state.verificacoes, st.session_state.comparacao)


# ─────────────────────────────────────────────
with tab_ajuda:
    st.markdown("""
    <div class="section-title">📖 Como usar o Auditor NBR 9050</div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **1. Configure a IA (barra lateral)**
        - Escolha o provedor: **Anthropic** (Claude) ou **Google** (Gemini)
        - Cole sua chave API
        - Selecione o modelo desejado
        - Ajuste a temperature (0.0–0.2 recomendado para auditoria)

        **2. Carregue o arquivo**
        - **IFC** (obrigatório): arquivo exportado do Revit, ArchiCAD etc.
          - Formatos suportados: IFC2X3, IFC4
          - O sistema detecta o schema automaticamente
        - O **checklist NBR 9050** já vem embutido em `nbr9050_rules.json`,
          na raiz do repositório — não é preciso enviar planilha nenhuma.

        **3. Execute a auditoria**
        - Clique em **Executar Auditoria**
        - Acompanhe o log em tempo real
        - Aguarde 30–90 segundos (depende do modelo e tamanho do IFC)
        """)

    with col_b:
        st.markdown("""
        **4. Analise os resultados**
        - Filtre por status, categoria ou GlobalId
        - O **GlobalId** identifica cada elemento no IFC

        **5. Como usar o GlobalId no Revit**
        - No Revit: `Manage → Select by ID` → cole o GlobalId
        - No Navisworks: filtro por GUID
        - No Solibri / BIMcollab: filtro por GlobalId no modelo IFC
        - No IfcOpenShell: `ifc.by_guid("0yScV...")`

        **6. Exporte os relatórios**
        - **HTML**: relatório visual completo com todos os dados
        - **XLSX**: checklist com formatação por status (conforme/não conforme)
        - **JSON**: dados brutos para integração com outros sistemas
        """)

    st.markdown("---")
    st.markdown("""
    <div class="section-title">♿ Itens NBR 9050:2020 verificados (padrão)</div>
    """, unsafe_allow_html=True)

    # Lê os mesmos 12 itens que o motor de auditoria usa — nbr9050_rules.json
    # ANTES: lista hardcoded "itens_padrao" duplicando (e podendo divergir de) o JSON.
    # DEPOIS: mesma fonte única (obter_regras_lista()) usada em build_audit_prompt().
    itens_padrao = [
        (r["item_nbr"], r["classificacao"], r["subcategoria"], r["item_verificavel"], r["entidades"]["primaria"])
        for r in obter_regras_lista()
    ]

    cat_colors = {"Geométrica": "rgb(28,96,241)", "Condicional": "#e8920a", "Relacional": "#1ab87a", "Qualitativa": "rgb(77,83,99)"}
    rows_help = ""
    for item_nbr, classificacao, cat, desc, entidade in itens_padrao:
        color = cat_colors.get(classificacao, "#6b7280")
        rows_help += f"""
        <tr>
          <td style="font-family:'Courier New',monospace;color:rgb(28,96,241);font-weight:600">{item_nbr}</td>
          <td><span style="color:{color};font-size:0.78rem;font-weight:600">{classificacao}</span></td>
          <td style="color:#1a1d26">{cat}</td>
          <td style="color:#3d4252">{desc}</td>
          <td style="font-family:'Courier New',monospace;font-size:0.72rem;color:#6b7280">{entidade}</td>
        </tr>"""

    st.markdown(f"""
    <table class="result-table">
      <thead>
        <tr><th>Item NBR</th><th>Tipo</th><th>Categoria</th><th>Verificação</th><th>Entidade IFC</th></tr>
      </thead>
      <tbody>{rows_help}</tbody>
    </table>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="warn-box" style="margin-top:1.5rem">
    ⚠️ <strong>Limitações conhecidas:</strong>
    Itens qualitativos (maçaneta alavanca, lavatório suspenso) dependem de atributos textuais raramente preenchidos no IFC.
    Itens como espaço de giro (IfcSpace) ficam Indeterminados se o modelo não exportar espaços.
    Verificação manual complementar é sempre recomendada.
    </div>
    """, unsafe_allow_html=True)
