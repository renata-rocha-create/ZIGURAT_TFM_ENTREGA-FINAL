"""
relatorios.py — Geração dos entregáveis: relatório HTML e checklist XLSX.
"""
import io
from datetime import datetime


AUTORES = "Kevin Dias Quintian &nbsp;·&nbsp; Renata Gomes Rocha &nbsp;·&nbsp; Sergio Rosenboim &nbsp;·&nbsp; Viviane Nishizaki Suzuke &nbsp;·&nbsp; William Felipe dos Santos Moura"
RODAPE_TXT = "Kevin Dias Quintian · Renata Gomes Rocha · Sergio Rosenboim · Viviane Nishizaki Suzuke · William Felipe dos Santos Moura"

def gerar_relatorio_html(resultado: dict, modelo_nome: str) -> str:
    """Generate a self-contained HTML report — Zigurat brand."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    resumo = resultado.get("resumo", {})
    itens  = resultado.get("resultados", [])

    # status color map
    def st_color(s):
        sl = s.lower()
        if "parcial" in sl: return "#7c3ac4"
        if "conforme" in sl and "não" not in sl and "nao" not in sl: return "#1ab87a"
        if "não" in sl or "nao" in sl: return "#e03c3c"
        if "indet" in sl: return "#e8920a"
        return "#6b7280"

    rows = ""
    for it in itens:
        gid = it.get("globalid","") or ""
        gid_cell = f'<code style="font-family:\'Courier New\',monospace;font-size:0.73em;background:#eef1f8;border:1px solid #c5cad8;border-radius:4px;padding:2px 7px;color:rgb(28,96,241);letter-spacing:0.02em">{gid}</code>' if gid and gid != "—" else '<span style="color:#aab0be;font-size:0.8em">—</span>'
        st = it.get("status","N/A")
        rec = it.get("recomendacao","") or ""
        confianca_tag = ' <span title="Avaliação qualitativa — recomenda-se confirmação humana" style="cursor:help">🔍</span>' if it.get("requer_confirmacao_humana") else ""
        rows += f"""
        <tr>
          <td><code style="background:#f0f3fb;border-radius:4px;padding:2px 6px;font-size:0.8em;color:rgb(28,96,241)">{it.get('item_nbr','—')}</code>{confianca_tag}</td>
          <td style="color:#3d4252">{it.get('categoria','—')}</td>
          <td style="color:#1a1d26;max-width:200px">{it.get('elemento','—')}</td>
          <td style="color:{st_color(st)};font-weight:700;white-space:nowrap">{st}</td>
          <td style="color:#3d4252;font-family:'Courier New',monospace;font-size:0.8em">{it.get('valor_encontrado','—')}</td>
          <td style="color:#3d4252;font-family:'Courier New',monospace;font-size:0.8em">{it.get('valor_exigido','—')}</td>
          <td style="white-space:nowrap">{gid_cell}</td>
          <td style="color:#6b7280;font-size:0.82em">{it.get('tipo_ifc','—')}</td>
          <td style="color:#b52929;font-size:0.82em">{rec}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório NBR 9050 — {modelo_nome}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Trebuchet MS', Trebuchet, Arial, sans-serif;
    background: #ffffff;
    color: #1a1d26;
    padding: 0;
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(120deg, rgb(77,83,99) 0%, rgb(50,56,72) 100%);
    padding: 1.5rem 2.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .header-left h1 {{
    color: rgb(68,205,148);
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.2rem;
  }}
  .header-left .sub {{
    color: rgba(255,255,255,0.55);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }}
  .header-logo {{
    background: #ffffff;
    border-radius: 7px;
    padding: 5px 12px;
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
  }}
  .header-logo img {{ height: 32px; display: block; }}

  /* ── Body content ── */
  .content {{ padding: 2rem 2.5rem; }}

  /* ── Meta line ── */
  .meta {{
    font-family: 'Courier New', monospace;
    font-size: 0.78rem;
    color: #6b7280;
    margin-bottom: 1.75rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
  }}
  .meta strong {{ color: #1a1d26; }}

  /* ── Section titles ── */
  h2 {{
    font-size: 0.78rem;
    font-weight: 700;
    color: rgb(28,96,241);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 1.75rem 0 0.85rem 0;
  }}

  /* ── Metric cards ── */
  .resumo {{ display: flex; gap: 0.85rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .card {{
    flex: 1; min-width: 100px;
    background: #f4f6f9;
    border: 1px solid #e5e7eb;
    border-top: 3px solid rgb(68,205,148);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    text-align: center;
  }}
  .card .num {{ font-size: 1.9rem; font-weight: 800; line-height: 1; margin-bottom: 0.2rem; }}
  .card .lbl {{ font-size: 0.6rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.1em; }}

  /* ── Obs box ── */
  .obs {{
    background: #f4f6f9;
    border-left: 3px solid rgb(68,205,148);
    border-radius: 0 6px 6px 0;
    padding: 1rem 1.25rem;
    font-size: 0.85rem;
    color: #3d4252;
    margin: 0 0 1.5rem 0;
    line-height: 1.65;
  }}

  /* ── GlobalId tip ── */
  .globalid-tip {{
    font-size: 0.75rem;
    color: #6b7280;
    margin-bottom: 0.75rem;
    padding: 0.5rem 0.85rem;
    background: #eef1f8;
    border-radius: 6px;
    border-left: 3px solid rgb(28,96,241);
  }}
  .globalid-tip strong {{ color: rgb(28,96,241); }}

  /* ── Table ── */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  thead {{ position: sticky; top: 0; }}
  th {{
    background: rgb(77,83,99);
    color: #ffffff;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 2px solid rgb(28,96,241);
    white-space: nowrap;
  }}
  th.col-gid {{ color: rgb(68,205,148); }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #f0f1f4; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #fafbfc; }}
  tr:hover td {{ background: rgba(68,205,148,0.06); }}

  /* ── Footer ── */
  .footer {{
    background: rgb(77,83,99);
    padding: 1rem 2.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 2.5rem;
  }}
  .footer-left {{
    font-size: 0.7rem;
    color: rgba(255,255,255,0.5);
    line-height: 1.6;
  }}
  .footer-left strong {{ color: rgb(68,205,148); display: block; margin-bottom: 0.2rem; font-size: 0.72rem; }}
  .footer-left .autores {{ color: rgba(255,255,255,0.7); }}
  .footer-logo {{
    background: #ffffff;
    border-radius: 7px;
    padding: 4px 10px;
    display: inline-flex;
    align-items: center;
  }}
  .footer-logo img {{ height: 20px; display: block; }}
  .footer-right {{
    font-family: 'Courier New', monospace;
    font-size: 0.65rem;
    color: rgba(255,255,255,0.35);
    text-align: right;
  }}
</style>
</head>
<body>

<!-- ── Header ── -->
<div class="header">
  <div class="header-left">
    <h1>&#9855; Relatório de Verificação de Acessibilidade BIM</h1>
    <div class="sub">Verificação Automatizada de Conformidade &nbsp;·&nbsp; ABNT NBR 9050:2020</div>
  </div>
  <div class="header-logo">
    <img src="https://www.e-zigurat.com/images/logo.svg" alt="Zigurat Institute of Technology" />
  </div>
</div>
</div>

<!-- ── Content ── -->
<div class="content">

  <p class="meta">
    Norma: <strong>ABNT NBR 9050:2020</strong> &nbsp;|&nbsp;
    Modelo: <strong>{modelo_nome}</strong> &nbsp;|&nbsp;
    Schema IFC: <strong>{resultado.get('schema_ifc','—')}</strong> &nbsp;|&nbsp;
    Emitido em: <strong>{now}</strong>
  </p>

  <h2>Resumo Executivo</h2>
  <div class="resumo">
    <div class="card"><div class="num" style="color:#1a1d26">{resumo.get('total',0)}</div><div class="lbl">Total</div></div>
    <div class="card"><div class="num" style="color:#1ab87a">{resumo.get('conformes',0)}</div><div class="lbl">Conformes</div></div>
    <div class="card"><div class="num" style="color:#7c3ac4">{resumo.get('parciais',0)}</div><div class="lbl">Parciais</div></div>
    <div class="card"><div class="num" style="color:#e03c3c">{resumo.get('nao_conformes',0)}</div><div class="lbl">Não Conformes</div></div>
    <div class="card"><div class="num" style="color:#e8920a">{resumo.get('indeterminados',0)}</div><div class="lbl">Indeterminados</div></div>
    <div class="card"><div class="num" style="color:#6b7280">{resumo.get('na',0)}</div><div class="lbl">N/A</div></div>
    <div class="card"><div class="num" style="color:rgb(28,96,241)">{resumo.get('percentual_conformidade','—')}</div><div class="lbl">Conformidade (bruta)</div></div>
    <div class="card"><div class="num" style="color:#0c447c">{resumo.get('percentual_sobre_verificaveis','—')}</div><div class="lbl">Conformidade (s/ N/A)</div></div>
  </div>

  <div class="obs">{resultado.get('observacoes_gerais','—')}</div>

  <h2>Resultados Detalhados por Elemento</h2>
  <div class="globalid-tip">
    💡 A coluna <strong>GlobalId</strong> é o identificador único do elemento no IFC — o "CPF" do elemento.
    Use-o no Revit (<em>Manage → Select by ID</em>), no Navisworks ou no BIMcollab para localizar o elemento diretamente no modelo.
    <br>🔍 ao lado do item = avaliação qualitativa (baseada em nome/tipo, não em medição direta) — recomenda-se confirmação humana.
    <br><span style="color:#7c3ac4;font-weight:700">▲ Parcial</span> = alguns dos elementos avaliados atendem ao critério e outros não (ver "Valor Encontrado" para a proporção).
  </div>

  <table>
    <thead>
      <tr>
        <th>Item NBR</th>
        <th>Categoria</th>
        <th>Elemento</th>
        <th>Status</th>
        <th>Valor Encontrado</th>
        <th>Valor Exigido</th>
        <th class="col-gid">&#128273; GlobalId (IFC/Revit)</th>
        <th>Tipo IFC</th>
        <th>Recomendação</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

</div><!-- /content -->

<!-- ── Footer ── -->
<div class="footer">
  <div class="footer-left">
    <strong>TFM | Grupo 1</strong>
    <span class="autores">{AUTORES}</span>
    <span style="color:rgba(255,255,255,0.3);font-size:0.65rem;margin-top:0.3rem;display:block">
      Gerado automaticamente por IA — verificação manual complementar necessária para itens qualitativos e indeterminados.
    </span>
  </div>
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:0.5rem">
    <div class="footer-logo">
      <img src="https://www.e-zigurat.com/images/logo.svg" alt="Zigurat" />
    </div>
    <div class="footer-right">Master IA para AEC &nbsp;·&nbsp; {now}</div>
  </div>
</div>

</body>
</html>"""


def gerar_excel(resultado: dict, modelo_nome: str) -> bytes:
    """Generate XLSX report with openpyxl."""
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    except ImportError:
        return b""

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Checklist NBR 9050"

    # Colors
    H_FILL  = PatternFill("solid", fgColor="0A1628")
    SUB_FILL = PatternFill("solid", fgColor="111827")
    CONF_F  = PatternFill("solid", fgColor="064E3B")
    PARC_F  = PatternFill("solid", fgColor="3B1064")
    NAO_F   = PatternFill("solid", fgColor="4C0519")
    INDET_F = PatternFill("solid", fgColor="4B2B06")
    NA_F    = PatternFill("solid", fgColor="1E293B")

    thin = Side(style="thin", color="1F2D45")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Header
    ws.merge_cells("A1:I1")
    ws["A1"] = f"♿ RELATÓRIO DE ACESSIBILIDADE NBR 9050:2020 — {modelo_nome}"
    ws["A1"].font = Font(bold=True, color="00D4AA", size=12, name="Calibri")
    ws["A1"].fill = H_FILL
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:I2")
    ws["A2"] = f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Schema IFC: {resultado.get('schema_ifc','—')}"
    ws["A2"].font = Font(color="64748B", size=9, italic=True, name="Calibri")
    ws["A2"].fill = SUB_FILL
    ws["A2"].alignment = Alignment(horizontal="center")

    # Column headers
    headers = ["Item NBR", "Categoria", "Elemento", "Status", "Valor Encontrado",
               "Valor Exigido", "GlobalId (Revit/IFC)", "Tipo IFC", "Recomendação"]
    widths   = [12, 16, 32, 16, 20, 20, 32, 18, 45]

    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=3, column=i, value=h)
        cell.font = Font(bold=True, color="94A3B8", size=9, name="Calibri")
        cell.fill = SUB_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        ws.column_dimensions[chr(64+i)].width = w
    ws.row_dimensions[3].height = 20

    # Data rows
    status_fills = {
        "conforme": CONF_F, "parcial": PARC_F, "não conforme": NAO_F, "nao conforme": NAO_F,
        "indeterminado": INDET_F, "n/a": NA_F
    }
    status_colors = {
        "conforme": "10B981", "parcial": "C084FC", "não conforme": "F87171", "nao conforme": "F87171",
        "indeterminado": "FCD34D", "n/a": "64748B"
    }

    for r, it in enumerate(resultado.get("resultados", []), start=4):
        st_key = it.get("status","").lower()
        fill = status_fills.get(st_key, NA_F)

        values = [
            it.get("item_nbr",""),
            it.get("categoria",""),
            it.get("elemento",""),
            it.get("status",""),
            it.get("valor_encontrado",""),
            it.get("valor_exigido",""),
            it.get("globalid","—"),
            it.get("tipo_ifc",""),
            it.get("recomendacao",""),
        ]
        for c, val in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.fill = fill
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.font = Font(color="E2E8F0", size=9, name="Calibri")
            if c == 4:
                color = status_colors.get(st_key, "E2E8F0")
                cell.font = Font(color=color, bold=True, size=9, name="Calibri")
            if c == 7:
                cell.font = Font(color="60A5FA", size=9, name="Calibri Mono")
        ws.row_dimensions[r].height = 36

    # Summary sheet
    ws2 = wb.create_sheet("Resumo")
    resumo = resultado.get("resumo", {})
    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 20
    ws2.append(["Métrica", "Valor"])
    ws2.append(["Modelo", resultado.get("modelo","—")])
    ws2.append(["Schema IFC", resultado.get("schema_ifc","—")])
    ws2.append(["Data Auditoria", resultado.get("data_auditoria", datetime.now().strftime("%d/%m/%Y"))])
    ws2.append(["Total de Itens", resumo.get("total", 0)])
    ws2.append(["✅ Conformes", resumo.get("conformes", 0)])
    ws2.append(["▲ Parciais", resumo.get("parciais", 0)])
    ws2.append(["❌ Não Conformes", resumo.get("nao_conformes", 0)])
    ws2.append(["⚠️ Indeterminados", resumo.get("indeterminados", 0)])
    ws2.append(["— N/A", resumo.get("na", 0)])
    ws2.append(["% Conformidade", resumo.get("percentual_conformidade","—")])
    for row in ws2.iter_rows(min_row=1, max_row=ws2.max_row):
        for cell in row:
            cell.font = Font(name="Calibri", size=10)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
