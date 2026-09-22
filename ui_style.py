"""
ui_style.py — Identidade visual Zigurat (CSS) e componentes visuais simples.

Só APARÊNCIA: nenhuma lógica de auditoria vive aqui.
"""
import streamlit as st

from verificacoes import classificar_status

CSS_ZIGURAT = """
<style>

:root {
    --zk-slate:  rgb(77,83,99);
    --zk-green:  rgb(68,205,148);
    --zk-blue:   rgb(28,96,241);
    --bg:        #ffffff;
    --surface:   #f4f6f9;
    --border:    #d1d5de;
    --border-dk: rgb(77,83,99);
    --text:      #1a1d26;
    --muted:     #6b7280;
    --success:   #1ab87a;
    --danger:    #e03c3c;
    --warn:      #e8920a;
    --font: 'Trebuchet MS', Trebuchet, Arial, sans-serif;
    --mono: 'Courier New', Courier, monospace;
}

/* ── Global ── */
html, body, .stApp, [class*="css"] {
    font-family: var(--font) !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}
.stApp { background-color: var(--bg) !important; }
.stApp p, .stApp span, .stApp label, .stApp div,
.stApp h1, .stApp h2, .stApp h3, .stApp li { color: var(--text) !important; }

/* ════════════════════════════════════
   SIDEBAR — fundo BRANCO
   ════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 5px solid var(--zk-green) !important;
}
/* Textos escuros na sidebar branca */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] .stMarkdown { color: var(--text) !important; }

/* Inputs na sidebar: fundo cinza claro, texto escuro */
[data-testid="stSidebar"] input {
    background: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    font-family: var(--font) !important;
}
[data-testid="stSidebar"] input::placeholder { color: var(--muted) !important; }

/* Selectbox na sidebar */
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div {
    color: var(--text) !important;
    font-family: var(--font) !important;
}

/* Dropdown list */
[data-baseweb="popover"] [role="option"] {
    background: #ffffff !important;
    color: var(--text) !important;
    font-family: var(--font) !important;
}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [aria-selected="true"] {
    background: rgba(68,205,148,0.15) !important;
    color: var(--text) !important;
}

/* Linha separadora verde na sidebar */
[data-testid="stSidebar"] hr { border-color: var(--zk-green) !important; border-width: 2px !important; }

/* Labels da sidebar */
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stSlider label { color: var(--zk-slate) !important; font-weight: 600 !important; }

/* ── Slider na sidebar ── */
[data-testid="stSidebar"] [data-baseweb="slider"] { background: var(--border) !important; }
[data-testid="stSidebar"] [role="slider"] {
    background: var(--zk-green) !important;
    width: 20px !important; height: 20px !important;
    border: 3px solid #ffffff !important;
    box-shadow: 0 0 0 2px var(--zk-green) !important;
}
[data-testid="stSidebar"] [data-testid="stSlider"] [data-baseweb="slider"] div[role="progressbar"] {
    background: var(--zk-green) !important;
}
/* Ocultar o valor flutuante nativo (tooltip do thumb) */
[data-testid="stSidebar"] [data-testid="stSlider"] [data-baseweb="tooltip"],
[data-testid="stSidebar"] [data-testid="stSlider"] div[data-testid="stTickBarMin"],
[data-testid="stSidebar"] [data-testid="stSlider"] div[data-testid="stTickBarMax"] {
    display: none !important;
}

/* ════════════════════════════════════
   HERO — fundo BRANCO, borda escura
   ════════════════════════════════════ */
.hero-block {
    background: #ffffff;
    border: 2px solid var(--zk-slate);
    border-radius: 10px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
}
.hero-title {
    font-family: var(--font);
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--zk-slate) !important;
    margin: 0 0 0.2rem 0;
}
.hero-sub {
    font-family: var(--font);
    font-size: 0.72rem;
    color: var(--muted) !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

/* ── Section titles ── */
.section-title {
    font-family: var(--font);
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--zk-blue) !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.85rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

/* ── Status badges ── */
.badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-family: var(--font); font-size: 0.72rem; font-weight: 600; }
.badge-conforme { background: rgba(26,184,122,0.12); color: #0a7a4e !important; border: 1px solid rgba(26,184,122,0.35); }
.badge-parcial  { background: rgba(124,58,196,0.12);  color: #5b21a6 !important; border: 1px solid rgba(124,58,196,0.35); }
.badge-nao      { background: rgba(224,60,60,0.10);  color: #9b1c1c !important; border: 1px solid rgba(224,60,60,0.35); }
.badge-indet    { background: rgba(232,146,10,0.12); color: #7a4500 !important; border: 1px solid rgba(232,146,10,0.35); }
.badge-na       { background: rgba(77,83,99,0.08);   color: #4d5363 !important; border: 1px solid rgba(77,83,99,0.2); }

/* ── Result table ── */
.result-table { width: 100%; border-collapse: collapse; font-size: 0.81rem; }
.result-table th {
    font-family: var(--font); font-size: 0.67rem; color: #ffffff !important;
    text-transform: uppercase; letter-spacing: 0.08em;
    border-bottom: 2px solid var(--zk-blue); padding: 9px 12px;
    text-align: left; background: var(--zk-slate);
}
.result-table td { padding: 9px 12px; border-bottom: 1px solid var(--border); vertical-align: top; color: var(--text) !important; }
.result-table tr:hover td { background: rgba(68,205,148,0.05); }

/* ── GlobalId chip ── */
.globalid { font-family: var(--mono); font-size: 0.67rem; background: #eef1f8; border: 1px solid #c5cad8; border-radius: 4px; padding: 2px 6px; color: var(--zk-blue) !important; display: inline-block; }

/* ── Metric cards ── */
.metric-row { display: flex; gap: 0.85rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.metric-card { flex: 1; min-width: 110px; background: var(--surface); border: 1px solid var(--border); border-top: 3px solid var(--zk-green); border-radius: 8px; padding: 1rem; text-align: center; }
.metric-num { font-family: var(--font); font-size: 2rem; font-weight: 700; line-height: 1; margin-bottom: 0.2rem; }
.metric-label { font-family: var(--font); font-size: 0.62rem; color: var(--muted) !important; text-transform: uppercase; letter-spacing: 0.08em; }
.c-green { color: var(--success) !important; }
.c-purple{ color: #7c3ac4 !important; }
.c-red   { color: var(--danger)  !important; }
.c-amber { color: var(--warn)    !important; }
.c-blue  { color: var(--zk-blue) !important; }
.c-muted { color: var(--muted)   !important; }

/* ── Terminal ── */
.terminal {
    background: var(--zk-slate); border: 1px solid #3a3f4f; border-radius: 8px;
    padding: 1rem 1.25rem; font-family: var(--mono); font-size: 0.74rem;
    color: var(--zk-green) !important; max-height: 280px; overflow-y: auto; line-height: 1.7;
}

/* ── Inputs main content ── */
.stTextInput input, .stTextArea textarea {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    color: var(--text) !important; border-radius: 6px !important;
    font-family: var(--font) !important; font-size: 0.82rem !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--zk-green) !important;
    box-shadow: 0 0 0 2px rgba(68,205,148,0.2) !important;
}

/* Selectbox main content */
[data-testid="stMain"] [data-baseweb="select"] > div { background: var(--surface) !important; border: 1px solid var(--border) !important; color: var(--text) !important; }
[data-testid="stMain"] [data-baseweb="select"] span { color: var(--text) !important; }

/* ── File uploader — borda verde chamativa ── */
[data-testid="stFileUploader"] { background: #f0fdf8 !important; border: 2px dashed var(--zk-green) !important; border-radius: 8px !important; }
[data-testid="stFileUploader"]:hover { background: #e6faf3 !important; border-color: var(--zk-blue) !important; }
[data-testid="stFileUploader"] span, [data-testid="stFileUploader"] p { color: var(--text) !important; }

/* ── Botão principal — verde chamativo ── */
.stButton button {
    background: var(--zk-green) !important; color: rgb(20,60,40) !important;
    font-family: var(--font) !important; font-weight: 700 !important; font-size: 0.9rem !important;
    border: none !important; border-radius: 6px !important; padding: 0.65rem 1.75rem !important;
    transition: all 0.2s !important; letter-spacing: 0.02em !important;
}
.stButton button:hover { background: var(--zk-blue) !important; color: #ffffff !important; transform: translateY(-1px); box-shadow: 0 4px 18px rgba(28,96,241,0.3) !important; }
.stButton button:disabled { background: var(--border) !important; color: var(--muted) !important; transform: none !important; }

/* ── Download buttons ── */
[data-testid="stDownloadButton"] button { background: var(--surface) !important; color: var(--zk-blue) !important; border: 1.5px solid var(--zk-blue) !important; font-family: var(--font) !important; font-weight: 600 !important; }
[data-testid="stDownloadButton"] button:hover { background: var(--zk-blue) !important; color: #ffffff !important; }

/* ── Expander ── */
.streamlit-expanderHeader { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 6px !important; font-family: var(--font) !important; font-size: 0.82rem !important; color: var(--text) !important; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] { font-family: var(--font) !important; font-size: 0.82rem !important; color: var(--muted) !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: var(--zk-blue) !important; border-bottom-color: var(--zk-blue) !important; }

/* ── Info / warning boxes ── */
.info-box { background: rgba(28,96,241,0.06); border-left: 3px solid var(--zk-blue); border-radius: 0 6px 6px 0; padding: 0.75rem 1rem; font-size: 0.82rem; color: #1a3fa8 !important; margin: 0.75rem 0; }
.warn-box { background: rgba(232,146,10,0.08); border-left: 3px solid var(--warn); border-radius: 0 6px 6px 0; padding: 0.75rem 1rem; font-size: 0.82rem; color: #7a4500 !important; margin: 0.75rem 0; }

/* ── Divider ── */
hr { border-color: var(--border) !important; }

/* ── Pulse ── */
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(68,205,148,0.4); } 50% { box-shadow: 0 0 0 8px rgba(68,205,148,0); } }

/* ── Botão CTA — verde vibrante com sombra quando habilitado ── */
.stButton button {
    background: var(--zk-green) !important; color: rgb(20,60,40) !important;
    font-family: var(--font) !important; font-weight: 700 !important; font-size: 0.9rem !important;
    border: none !important; border-radius: 6px !important; padding: 0.65rem 1.75rem !important;
    transition: all 0.2s !important; letter-spacing: 0.02em !important;
    box-shadow: 0 2px 8px rgba(68,205,148,0.35) !important;
}
.stButton button:hover {
    background: var(--zk-blue) !important; color: #ffffff !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(28,96,241,0.35) !important;
}
.stButton button:disabled {
    background: #e5e7eb !important; color: #9ca3af !important;
    transform: none !important; box-shadow: none !important;
}

/* ════════════════════════════════════
   RODAPÉ — fundo BRANCO, borda escura
   ════════════════════════════════════ */
.footer-app {
    background: #ffffff;
    border: 2px solid var(--zk-slate);
    border-radius: 8px;
    padding: 1rem 1.5rem;
    margin-top: 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
}
.footer-app-tfm { color: var(--zk-green) !important; font-weight: 700; font-size: 0.72rem; margin-bottom: 0.15rem; }
.footer-app-autores { color: var(--zk-slate) !important; font-size: 0.65rem; }

/* ── Ocultar chrome do Streamlit ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── Manter sidebar sempre visível ── */
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] { min-width: 240px !important; transform: none !important; }
</style>
"""


def aplicar_estilo() -> None:
    """Injeta o CSS da identidade visual Zigurat na página."""
    st.markdown(CSS_ZIGURAT, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    badges = {
        "Conforme":      '<span class="badge badge-conforme">✅ Conforme</span>',
        "Parcial":       '<span class="badge badge-parcial">▲ Parcial</span>',
        "Não Conforme":  '<span class="badge badge-nao">❌ Não Conforme</span>',
        "Indeterminado": '<span class="badge badge-indet">⚠️ Indeterminado</span>',
        "N/A":           '<span class="badge badge-na">— N/A</span>',
    }
    return badges[classificar_status(status)]

