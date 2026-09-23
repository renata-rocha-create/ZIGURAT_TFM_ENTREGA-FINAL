"""
verificacoes.py — Classificação de status e cálculo determinístico do resumo.

Nesta etapa contém a lógica que já existia (classificar_status, calcular_resumo).
Nas próximas etapas recebe a tabela de verificação POR ELEMENTO e o nível de
confiança derivado da origem do dado.
"""


def classificar_status(status: str) -> str:
    """
    Classifica a string de status livre devolvida pelo LLM numa das 5 categorias
    canônicas. Tolerante a variações de capitalização/pontuação do modelo
    ("Não conforme", "NÃO CONFORME", "não-conforme" etc. caem todas aqui).

    "Parcial" precisa ser checado ANTES do fallback pra N/A — a palavra não
    contém "não"/"conforme"/"indet", então sem essa checagem explícita todo
    resultado "Parcial" seria contado como "N/A" por engano.

    Fonte única desta regra — usada tanto pelo badge visual (status_badge)
    quanto pelo cálculo do resumo (calcular_resumo), pra garantir que os
    números da tabela e os números do resumo NUNCA divirjam entre si.
    """
    s = (status or "").lower()
    if "parcial" in s:
        return "Parcial"
    if "não" in s or "nao" in s:
        return "Não Conforme"
    if "conforme" in s:
        return "Conforme"
    if "indet" in s:
        return "Indeterminado"
    return "N/A"


def calcular_resumo(resultados: list[dict]) -> dict:
    """
    Calcula o resumo estatístico em PYTHON, de forma determinística —
    em vez de confiar que o LLM soma e divide corretamente.

    ANTES: "percentual_conformidade" vinha inteiro da resposta do modelo
    (o prompt só mostrava um exemplo de formato, "0%", e torcia pra ele
    fazer a conta certa). Reproduzir a mesma auditoria duas vezes podia,
    em teoria, dar dois percentuais diferentes mesmo com os mesmos status.

    DEPOIS: o LLM só precisa classificar cada item (Conforme/Não Conforme/
    Parcial/Indeterminado/N/A) — a contagem e a divisão são sempre feitas
    aqui, logo o mesmo conjunto de status SEMPRE produz o mesmo percentual.

    "Parcial" entra no percentual com peso 0,5 — nem conta como conforme
    (esconderia que parte dos elementos falha), nem como não conforme
    (esconderia que parte já atende). Ex: 4 conformes + 2 parciais + 6
    não conformes, total 12 → (4 + 2×0,5) / 12 = 41,7%.

    Também calcula "percentual_sobre_verificaveis": conformidade excluindo
    itens N/A do denominador. Itens N/A significam "não se aplica a este
    modelo" (ex: item de janela quando o modelo não tem janelas) — incluí-los
    no denominador junto com os itens Indeterminados infla artificialmente
    a sensação de não conformidade. As duas métricas juntas dão um retrato
    mais honesto do que só o percentual bruto.
    """
    total = len(resultados)
    categorias = [classificar_status(r.get("status", "")) for r in resultados]

    conformes      = categorias.count("Conforme")
    parciais       = categorias.count("Parcial")
    nao_conformes  = categorias.count("Não Conforme")
    indeterminados = categorias.count("Indeterminado")
    na             = categorias.count("N/A")

    pontos = conformes + 0.5 * parciais
    verificaveis = total - na
    pct_bruto              = round(pontos / total * 100, 1) if total else 0.0
    pct_sobre_verificaveis = round(pontos / verificaveis * 100, 1) if verificaveis else 0.0

    return {
        "total": total,
        "conformes": conformes,
        "parciais": parciais,
        "nao_conformes": nao_conformes,
        "indeterminados": indeterminados,
        "na": na,
        "percentual_conformidade": f"{pct_bruto}%",
        "percentual_sobre_verificaveis": f"{pct_sobre_verificaveis}%",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 2 — VERIFICAÇÃO POR ELEMENTO (determinística, em Python)
# ══════════════════════════════════════════════════════════════════════════════
#
# Ideia central: "o LLM é o tradutor, o Python é o juiz".
# Para os itens NUMÉRICOS (dimensões, alturas, inclinações), a conta é feita
# aqui, elemento por elemento, sempre com o mesmo resultado para a mesma
# entrada. Cada linha da tabela = 1 elemento × 1 item da NBR.
#
# Essa tabela é a "planilha de campo" que alimenta dashboard, 3D e BCF.

# ── Parâmetros normativos (NBR 9050:2020) ────────────────────────────────────
PORTA_LARG_MIN = 0.80          # 6.11.2
PORTA_ALT_MIN = 2.10           # 6.11.2
JANELA_PEITORIL_MIN = 1.20     # 6.11.3
BACIA_ALT_MIN, BACIA_ALT_MAX = 0.43, 0.45   # 7.7.2.1
BARRA_ALT_REF, BARRA_TOL = 0.75, 0.05       # 7.6–7.8 (faixa 0,70–0,80 m)
DESNIVEL_CORRIMAO = 0.19       # 5.4.3

TERMOS_LAV_CONFORME = ["suspenso", "sem coluna", "embutir", "semiencaixe", "encaixe"]
TERMOS_LAV_NAO_CONF = ["com coluna", "pedestal", "coluna suspensa"]
TERMOS_MACANETA_OK = ["alavanca", "lever", "handle"]
TERMOS_MACANETA_NOK = ["esférica", "esferica", "knob", "giratória", "giratoria", "round"]

CATEGORIAS = {
    "6.6": "Rampas", "6.11.1": "Corredores", "6.11.2": "Portas",
    "6.11.3": "Janelas", "5.4.3": "Corrimão", "7.5": "Circulação sanitários",
    "7.7.2.1": "Bacia sanitária", "7.8": "Lavatório", "7.6-7.8": "Barras de apoio",
    "4.6.6": "Maçaneta",
}

# Itens que dependem de texto/nome (classificação por palavra-chave)
ITENS_QUALITATIVOS = {"7.8", "4.6.6"}


def confianca_por_fonte(fonte: str) -> str:
    """
    Nível de confiança derivado da ORIGEM do dado (proveniência), não de
    "achismo" do LLM. Critério auditável:
      ALTA  → propriedade explícita do modelo (atributo IFC ou Pset)
      MEDIA → valor derivado de geometria ou de proxy (ex: cota Z)
      BAIXA → inferência textual (nome do elemento) ou associação não verificada
    """
    f = (fonte or "").lower()
    if "texto" in f or "associacao" in f:
        return "BAIXA"
    if "estimativa" in f or "geometria" in f or "z_placement" in f or "proxy" in f:
        return "MEDIA"
    if "atributo" in f or "pset" in f:
        return "ALTA"
    return "BAIXA"


def _num(v):
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def _linha(el, item, medido, exigido, status, fonte, msg=""):
    return {
        "item_nbr": item,
        "categoria": CATEGORIAS.get(item, ""),
        "global_id": el.get("GlobalId"),
        "nome": el.get("Name") or el.get("ObjectType") or "—",
        "ifc_class": el.get("tipo_ifc"),
        "pavimento": el.get("pavimento") or "—",
        "valor_medido": medido,
        "valor_exigido": exigido,
        "status": status,
        "confianca": confianca_por_fonte(fonte),
        "fonte_dado": fonte,
        "mensagem": msg,
    }


# ── Uma função por item da NBR ───────────────────────────────────────────────

def _v_portas(portas):
    linhas = []
    for p in portas:
        w, h = _num(p.get("OverallWidth_m")), _num(p.get("OverallHeight_m"))
        exig = f"L ≥ {PORTA_LARG_MIN:.2f} m e A ≥ {PORTA_ALT_MIN:.2f} m"
        if w is None or h is None:
            linhas.append(_linha(p, "6.11.2", f"L={w} | A={h}", exig, "Indeterminado",
                                 "nao_encontrado", "Porta sem OverallWidth/OverallHeight no modelo."))
            continue
        ok = w >= PORTA_LARG_MIN and h >= PORTA_ALT_MIN
        falhas = []
        if w < PORTA_LARG_MIN: falhas.append(f"largura {w:.2f} m < {PORTA_LARG_MIN:.2f} m")
        if h < PORTA_ALT_MIN:  falhas.append(f"altura {h:.2f} m < {PORTA_ALT_MIN:.2f} m")
        linhas.append(_linha(p, "6.11.2", f"L={w:.2f} m | A={h:.2f} m", exig,
                             "Conforme" if ok else "Não Conforme", "atributo_ifc",
                             "; ".join(falhas)))
    return linhas


def _v_macaneta(portas):
    linhas = []
    for p in portas:
        if not p.get("pne_pcd_confirmado"):
            continue  # escopo do projeto: só portas de sanitário PNE/PCD
        texto = " ".join(str(p.get(k) or "") for k in ("Name", "ObjectType", "Description")).lower()
        if any(t in texto for t in TERMOS_MACANETA_NOK):
            st_, msg = "Não Conforme", "Nome indica maçaneta esférica/giratória."
        elif any(t in texto for t in TERMOS_MACANETA_OK):
            st_, msg = "Conforme", "Nome indica maçaneta tipo alavanca."
        else:
            st_, msg = "Indeterminado", "Tipo de maçaneta não informado no nome/descrição."
        linhas.append(_linha(p, "4.6.6", "(texto)", "Maçaneta tipo alavanca", st_, "texto_nome", msg))
    return linhas


def _limite_rampa(desnivel):
    if desnivel <= 0.80: return 8.33
    if desnivel <= 1.00: return 6.25
    if desnivel <= 1.50: return 5.00
    return None


def _v_rampas(rampas):
    linhas = []
    for r in rampas:
        rise, incl = _num(r.get("OverallRise_m")), _num(r.get("inclinacao_pct"))
        fonte = r.get("fonte_dados_rampa", "nao_encontrado")
        if rise is None or incl is None:
            linhas.append(_linha(r, "6.6", "—", "Inclinação por faixa de desnível", "Indeterminado",
                                 fonte, "Sem OverallRise/OverallRun nem geometria utilizável."))
            continue
        lim = _limite_rampa(rise)
        if lim is None:
            linhas.append(_linha(r, "6.6", f"desnível={rise:.2f} m | i={incl:.2f}%", "—",
                                 "Indeterminado", fonte, "Desnível > 1,50 m: fora da tabela verificada."))
            continue
        ok = incl <= lim
        linhas.append(_linha(r, "6.6", f"desnível={rise:.2f} m | i={incl:.2f}%", f"i ≤ {lim:.2f}%",
                             "Conforme" if ok else "Não Conforme", fonte,
                             "" if ok else f"Inclinação {incl:.2f}% acima do limite {lim:.2f}%."))
    return linhas


def _v_corrimao(escadas, rampas, corrimaos):
    linhas = []
    tem_railing = len(corrimaos) > 0
    tem_duplo = any(c.get("corrimao_duplo_070_092") for c in corrimaos)
    alvos = [e for e in escadas if e.get("tipo_ifc") == "IfcStairFlight"]
    alvos += [dict(r, desnivel_m=r.get("OverallRise_m")) for r in rampas]
    for a in alvos:
        d = _num(a.get("desnivel_m"))
        exig = f"Corrimão 0,70 e 0,92 m se desnível > {DESNIVEL_CORRIMAO:.2f} m"
        if d is None:
            linhas.append(_linha(a, "5.4.3", "—", exig, "Indeterminado", "nao_encontrado",
                                 "Desnível não calculável."))
        elif d <= DESNIVEL_CORRIMAO:
            linhas.append(_linha(a, "5.4.3", f"desnível={d:.2f} m", exig, "N/A", "atributo_ifc",
                                 "Desnível não exige corrimão."))
        elif not tem_railing:
            linhas.append(_linha(a, "5.4.3", f"desnível={d:.2f} m", exig, "Indeterminado",
                                 "associacao_nao_verificada", "Nenhum IfcRailing no modelo — verificar in loco."))
        else:
            linhas.append(_linha(a, "5.4.3", f"desnível={d:.2f} m", exig,
                                 "Conforme" if tem_duplo else "Não Conforme",
                                 "associacao_nao_verificada",
                                 "Associação corrimão↔escada não verificada geometricamente."))
    return linhas


def _v_corredores(espacos):
    linhas = []
    for e in espacos:
        if e.get("tipo_ambiente") != "corredor":
            continue
        larg, comp = _num(e.get("largura_estimada_m")), _num(e.get("comprimento_estimado_m"))
        if larg is None or comp is None:
            linhas.append(_linha(e, "6.11.1", "—", "0,90/1,20/1,50 m", "Indeterminado",
                                 "geometria_estimativa", "Geometria do espaço não disponível."))
            continue
        minimo = 0.90 if comp <= 4 else 1.20 if comp <= 10 else 1.50
        ok = larg >= minimo
        linhas.append(_linha(e, "6.11.1", f"L={larg:.2f} m | C={comp:.2f} m", f"L ≥ {minimo:.2f} m",
                             "Conforme" if ok else "Não Conforme", "geometria_bounding_box_estimativa",
                             "" if ok else f"Largura {larg:.2f} m abaixo de {minimo:.2f} m."))
    return linhas


def _v_janelas(janelas):
    linhas = []
    for j in janelas:
        s = _num(j.get("SillHeight_m"))
        exig = f"Peitoril ≥ {JANELA_PEITORIL_MIN:.2f} m"
        if s is None:
            linhas.append(_linha(j, "6.11.3", "—", exig, "Indeterminado", "nao_encontrado",
                                 "SillHeight ausente nos Psets."))
            continue
        ok = s >= JANELA_PEITORIL_MIN
        # MEDIA: o valor é explícito, mas a exceção de privacidade não é checada
        linhas.append(_linha(j, "6.11.3", f"peitoril={s:.2f} m", exig,
                             "Conforme" if ok else "Não Conforme", "pset_proxy_excecao_privacidade",
                             "" if ok else "Verificar se o ambiente é de privacidade (exceção)."))
    return linhas


def _v_giro(espacos):
    linhas = []
    for e in espacos:
        if e.get("tipo_ambiente") != "sanitario":
            continue
        st_ = e.get("giro_150_status", "Indeterminado")
        area = _num(e.get("area_geometrica_m2"))
        linhas.append(_linha(e, "7.5", f"área={area} m²", "Círculo ⌀1,50 m livre", st_,
                             "geometria_estimativa",
                             (e.get("giro_150_nota") or "")
                             + " (polígono convexo: pode superestimar ambientes em L; não considera louças)"))
    return linhas


def _altura_equip(el):
    mh = _num(el.get("MountingHeight_m"))
    if mh is not None:
        return mh, "pset_mountingheight"
    z = _num(el.get("altura_estimada_m") or el.get("Z_placement_m"))
    if z is not None:
        return z, "z_placement_proxy"
    return None, "nao_encontrado"


def _v_bacias(bacias):
    linhas = []
    for b in bacias:
        h, fonte = _altura_equip(b)
        exig = f"{BACIA_ALT_MIN:.2f} a {BACIA_ALT_MAX:.2f} m"
        if h is None:
            linhas.append(_linha(b, "7.7.2.1", "—", exig, "Indeterminado", fonte, "Sem altura disponível."))
            continue
        ok = BACIA_ALT_MIN <= h <= BACIA_ALT_MAX
        linhas.append(_linha(b, "7.7.2.1", f"altura={h:.3f} m", exig,
                             "Conforme" if ok else "Não Conforme", fonte))
    return linhas


def _v_barras(barras):
    linhas = []
    for b in barras:
        h, fonte = _altura_equip(b)
        exig = f"≈{BARRA_ALT_REF:.2f} m (±{BARRA_TOL:.2f})"
        if h is None:
            linhas.append(_linha(b, "7.6-7.8", "—", exig, "Indeterminado", fonte, "Sem altura disponível."))
            continue
        ok = abs(h - BARRA_ALT_REF) <= BARRA_TOL
        linhas.append(_linha(b, "7.6-7.8", f"altura={h:.3f} m", exig,
                             "Conforme" if ok else "Não Conforme", fonte,
                             "Posição (lateral/fundo) não verificada."))
    return linhas


def _v_lavatorios(lavs):
    linhas = []
    for l in lavs:
        texto = " ".join(str(l.get(k) or "") for k in ("Name", "ObjectType", "Description")).lower()
        if any(t in texto for t in TERMOS_LAV_NAO_CONF):
            st_, msg = "Não Conforme", "Nome indica lavatório com coluna."
        elif any(t in texto for t in TERMOS_LAV_CONFORME):
            st_, msg = "Conforme", "Nome indica lavatório sem coluna/suspenso."
        else:
            st_, msg = "Indeterminado", "Tipo de instalação não identificado pelo nome."
        linhas.append(_linha(l, "7.8", "(texto)", "Sem coluna ou suspenso", st_, "texto_nome", msg))
    return linhas


def gerar_verificacoes(elementos: dict) -> list[dict]:
    """
    Gera a tabela de verificação POR ELEMENTO a partir das listas completas
    extraídas do IFC (elementos["_completo"]).

    Itens fora daqui (continuam só com o LLM): 6.3.4 (desníveis de piso) e
    7.7.1 (área de transferência lateral) — exigem análise espacial que ainda
    não está implementada.
    """
    c = (elementos or {}).get("_completo", {})
    linhas = []
    linhas += _v_rampas(c.get("rampas", []))
    linhas += _v_corredores(c.get("espacos", []))
    linhas += _v_portas(c.get("portas", []))
    linhas += _v_janelas(c.get("janelas", []))
    linhas += _v_corrimao(c.get("escadas", []), c.get("rampas", []), c.get("corrimaos", []))
    linhas += _v_giro(c.get("espacos", []))
    linhas += _v_bacias(c.get("bacias", []))
    linhas += _v_lavatorios(c.get("lavatorios", []))
    linhas += _v_barras(c.get("barras", []))
    linhas += _v_macaneta(c.get("portas", []))
    return linhas


def status_item_python(linhas_item: list[dict]):
    """
    Status do ITEM a partir das linhas por elemento — mesma regra "X de Y"
    que hoje está escrita no prompt, só que calculada em Python.
    Devolve None se o item não tem nenhuma linha (fica só com o LLM).
    """
    if not linhas_item:
        return None
    st_ = [l["status"] for l in linhas_item]
    aval = [s for s in st_ if s in ("Conforme", "Não Conforme")]
    if not aval:
        return "N/A" if all(s == "N/A" for s in st_) else "Indeterminado"
    x, y = aval.count("Conforme"), len(aval)
    if x == y: return "Conforme"
    if x == 0: return "Não Conforme"
    return "Parcial"


def comparar_com_llm(linhas: list[dict], resultados_llm: list[dict]) -> dict:
    """
    Compara, item a item, o status dado pelo LLM com o status calculado em
    Python. A taxa de concordância é uma métrica direta de confiabilidade
    do LLM para a dissertação.
    """
    def _norm(i):  # "7.6–7.8" (travessão) e "7.6 - 7.8" viram "7.6-7.8"
        return str(i).replace("–", "-").replace("—", "-").replace(" ", "")
    llm_por_item = {_norm(r.get("item_nbr")): classificar_status(r.get("status", ""))
                    for r in (resultados_llm or [])}
    itens = sorted({l["item_nbr"] for l in linhas})
    tabela = []
    for item in itens:
        py = status_item_python([l for l in linhas if l["item_nbr"] == item])
        llm = llm_por_item.get(item, "—")
        tabela.append({
            "item_nbr": item,
            "categoria": CATEGORIAS.get(item, ""),
            "status_llm": llm,
            "status_python": py,
            "concorda": (llm == py) if llm != "—" else None,
            "tipo": "Qualitativo (texto)" if item in ITENS_QUALITATIVOS else "Numérico",
        })
    comparaveis = [t for t in tabela if t["status_llm"] != "—"]
    n_ok = sum(1 for t in comparaveis if t["concorda"])
    taxa = round(n_ok / len(comparaveis) * 100, 1) if comparaveis else None
    return {"tabela": tabela, "concordantes": n_ok, "comparaveis": len(comparaveis),
            "taxa_concordancia": taxa}
