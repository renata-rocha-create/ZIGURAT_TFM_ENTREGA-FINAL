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
BACIA_ALT_MIN, BACIA_ALT_MAX = 0.43, 0.45   # 7.7.2.1 (RIM, não assembly)
BARRA_ALT_REF, BARRA_TOL = 0.75, 0.05       # 7.6–7.8 frontal (faixa 0,70–0,80 m)
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


def _nome(el):
    # IfcSpace do Revit: Name = número do ambiente ("14"), LongName = nome ("Corredor")
    n, ln = el.get("Name"), el.get("LongName")
    if n and ln and n != ln:
        return f"{n} — {ln}"
    return ln or n or el.get("ObjectType") or "—"


def _linha(el, item, medido, exigido, status, fonte, msg=""):
    return {
        "item_nbr": item,
        "categoria": CATEGORIAS.get(item, ""),
        "global_id": el.get("GlobalId"),
        "nome": _nome(el),
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


# ┌─ PONTO 1: Fallback Rampas ──────────────────────────────────────────────────
def _detectar_rampa_fallback(elemento):
    """
    Detecta se um elemento (tipicamente IfcSlab) é uma rampa implícita.
    Critério: 2% < inclinação < 30% = rampa válida.

    Analogia: Como reconhecer uma rampa de acesso em um prédio antigo onde o
    arquiteto não criou um IfcRamp explícito, mas fez um slab inclinado.
    Você mede a inclinação: se está entre 2% e 30%, é uma rampa.
    """
    rise = _num(elemento.get("OverallRise_m"))
    incl = _num(elemento.get("inclinacao_pct"))

    if rise is None or incl is None:
        return None, None, False

    eh_rampa_fallback = 2.0 < incl < 30.0
    return rise, incl, eh_rampa_fallback


def _v_rampas(rampas):
    linhas = []
    for r in rampas:
        # Tenta fallback primeiro se não for IfcRamp explícito
        tipo_ifc = r.get("tipo_ifc", "")
        is_explicit_ramp = "IfcRamp" in tipo_ifc or "IfcRampFlight" in tipo_ifc

        rise, incl = _num(r.get("OverallRise_m")), _num(r.get("inclinacao_pct"))
        fonte = r.get("fonte_dados_rampa", "nao_encontrado")

        # Se não é IfcRamp explícito, testa fallback
        if not is_explicit_ramp:
            rise_fb, incl_fb, eh_rampa_fb = _detectar_rampa_fallback(r)
            if not eh_rampa_fb:
                # Não passa no critério fallback, pula
                continue
            # Passa: usa os valores do fallback
            rise, incl = rise_fb, incl_fb
            fonte = "geometria_fallback_inclinacao"

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
        marker = " [fallback: slab inclinado]" if "fallback" in fonte else ""
        linhas.append(_linha(r, "6.6", f"desnível={rise:.2f} m | i={incl:.2f}%", f"i ≤ {lim:.2f}%",
                             "Conforme" if ok else "Não Conforme", fonte,
                             ("" if ok else f"Inclinação {incl:.2f}% acima do limite {lim:.2f}%.") + marker))
    return linhas
# └─ fim PONTO 1 ──────────────────────────────────────────────────────────────


def _v_corrimao(escadas, rampas, corrimaos):
    linhas = []
    tem_railing = len(corrimaos) > 0
    tem_duplo = any(c.get("corrimao_duplo_070_092") for c in corrimaos)
    alvos = [e for e in escadas if e.get("tipo_ifc") == "IfcStairFlight"]
    alvos += [dict(r, desnivel_m=r.get("OverallRise_m")) for r in rampas]
    for a in alvos:
        d = _num(a.get("desnivel_m"))
        exig = f"Corrimão 0,70 e 0,92 m se desnível > {DESNIVEL_CORRIMAO:.2f} m"
        fonte = a.get("fonte_dados_rampa", "associacao_nao_verificada")
        fallback_marker = ""
        if "fallback" in str(fonte):
            fallback_marker = " [Rampa detectada por fallback — validação manual recomendada]"

        if d is None:
            linhas.append(_linha(a, "5.4.3", "—", exig, "Indeterminado", fonte,
                                 "Desnível não calculável." + fallback_marker))
        elif d <= DESNIVEL_CORRIMAO:
            linhas.append(_linha(a, "5.4.3", f"desnível={d:.2f} m", exig, "N/A", fonte,
                                 "Desnível não exige corrimão."))
        elif not tem_railing:
            linhas.append(_linha(a, "5.4.3", f"desnível={d:.2f} m", exig, "Indeterminado",
                                 fonte, "Nenhum IfcRailing no modelo — verificar in loco." + fallback_marker))
        else:
            linhas.append(_linha(a, "5.4.3", f"desnível={d:.2f} m", exig,
                                 "Conforme" if tem_duplo else "Não Conforme",
                                 fonte,
                                 "Associação corrimão↔escada não verificada geometricamente." + fallback_marker))
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
    if el.get("fonte_altura"):          # altura tirada do bounding box da geometria
        h = _num(el.get("altura_estimada_m"))
        if h is not None:
            return h, el["fonte_altura"]
    z = _num(el.get("altura_estimada_m") or el.get("Z_placement_m"))
    if z is not None:
        return z, "z_placement_proxy"
    return None, "nao_encontrado"


# ┌─ PONTO 3: Altura da Bacia ──────────────────────────────────────────────────
def _altura_bacia_rim(altura_total: float, nome_elemento: str) -> float:
    """
    Extrai altura da BORDA (rim) da bacia a partir da altura total.

    Analogia técnica: É como medir a altura de um livro dentro de uma caixa
    protetora. A caixa toda mede 0.81 m, mas o "rim" (a página da capa) é
    mais próximo de 0.43 m — você precisa descontar a embalagem (tanque).
    """
    n = (nome_elemento or "").lower()
    if "caixa acoplada" in n or "acoplada" in n:
        return altura_total - 0.375  # Remove tanque integrado (~0.375m)
    return altura_total - 0.05  # Pequena margem de segurança


def _v_bacias(bacias):
    linhas = []
    for b in bacias:
        h_total, fonte = _altura_equip(b)
        nome = _nome(b)

        if h_total is None:
            linhas.append(_linha(b, "7.7.2.1", "—", f"{BACIA_ALT_MIN:.2f} a {BACIA_ALT_MAX:.2f} m",
                                 "Indeterminado", fonte, "Sem altura disponível."))
            continue

        # Calcula altura da borda (rim)
        h_rim = _altura_bacia_rim(h_total, nome)

        # Validação em 3 faixas
        if BACIA_ALT_MIN <= h_rim <= BACIA_ALT_MAX:
            status = "Conforme"
            msg = f"Altura da borda (rim) = {h_rim:.3f} m (dentro de 0.43–0.45 m)"
        elif 0.41 <= h_rim <= 0.47:
            status = "Parcial"
            msg = f"Altura {h_rim:.3f} m próxima ao intervalo (0.43–0.45 m). Validação manual recomendada."
        else:
            status = "Indeterminado"
            msg = f"Altura {h_rim:.3f} m fora da faixa aceitável (< 0.41 m ou > 0.47 m). Requer verificação in loco."

        linhas.append(_linha(b, "7.7.2.1", f"rim={h_rim:.3f} m", f"{BACIA_ALT_MIN:.2f}–{BACIA_ALT_MAX:.2f} m",
                             status, fonte, msg))
    return linhas
# └─ fim PONTO 3 ──────────────────────────────────────────────────────────────


# ┌─ PONTO 4: Barras com Posição ───────────────────────────────────────────────
def _classificar_barra_posicao(nome_elemento: str, altura: float) -> tuple:
    """
    Classifica barra por posição e retorna faixa de altura esperada.

    Analogia técnica: É como validar barras de proteção em um parque. Uma barra
    a 0.75 m é perfeita para que um adulto se segure em pé (Frontal A), mas
    0.40 m é o certo para se sentar (Lateral B). Medir tudo contra 0.75 m seria
    como pedir que todas as pessoas usem o mesmo tamanho de sapato.

    Retorna: (posicao, h_min, h_max)
    """
    n = (nome_elemento or "").lower()

    # Ordem importa: checar termos mais específicos antes de genéricos
    if "escada" in n or "corrimão" in n or "corrimao" in n:
        return "Escada (E)", 0.80, 0.90    # 0.85m
    elif "infantil" in n or "criança" in n or "crianca" in n:
        return "Infantil (D)", 0.25, 0.35  # 0.30m
    elif "lateral" in n or "lado" in n:
        return "Lateral (B)", 0.35, 0.45   # 0.40m
    elif "frontal" in n or "frente" in n or "vaso" in n:
        return "Frontal (A)", 0.70, 0.80   # 0.75m
    else:
        # Infere pela altura se nome não diz
        if 0.80 <= altura <= 0.90:
            return "Escada (E)", 0.80, 0.90
        elif 0.70 <= altura <= 0.80:
            return "Frontal? (A)", 0.70, 0.80
        elif 0.35 <= altura <= 0.45:
            return "Lateral? (B)", 0.35, 0.45
        elif 0.25 <= altura <= 0.35:
            return "Infantil? (D)", 0.25, 0.35
        else:
            # Fallback: assume frontal como padrão
            return "Frontal? (A)", 0.70, 0.80


def _v_barras(barras):
    linhas = []
    for b in barras:
        h, fonte = _altura_equip(b)
        nome = _nome(b)

        if h is None:
            linhas.append(_linha(b, "7.6-7.8", "—", "Varia por posição", "Indeterminado",
                                 fonte, "Sem altura disponível."))
            continue

        # Classifica por posição
        posicao, h_min, h_max = _classificar_barra_posicao(nome, h)
        exig = f"{posicao}: {h_min:.2f}–{h_max:.2f} m"

        # Validação em 3 faixas
        if h_min <= h <= h_max:
            status = "Conforme"
            msg = f"Altura {h:.3f} m dentro da faixa para {posicao}"
        elif (h_min - 0.05) <= h <= (h_max + 0.05):
            status = "Parcial"
            msg = f"Altura {h:.3f} m próxima à faixa para {posicao}. Validação manual recomendada."
        else:
            status = "Não Conforme"
            msg = f"Altura {h:.3f} m fora da faixa esperada para {posicao}"

        linhas.append(_linha(b, "7.6-7.8", f"{h:.3f} m", exig, status, fonte, msg))
    return linhas
# └─ fim PONTO 4 ──────────────────────────────────────────────────────────────


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
    aval = [s for s in st_ if s in ("Conforme", "Não Conforme", "Parcial")]
    if not aval:
        return "N/A" if all(s == "N/A" for s in st_) else "Indeterminado"
    if all(s == "Conforme" for s in aval): return "Conforme"
    if all(s == "Não Conforme" for s in aval): return "Não Conforme"
    return "Parcial"


def aplicar_veredito_python(resultados_llm: list[dict], linhas: list[dict]) -> list[dict]:
    """
    O PYTHON DÁ A PALAVRA FINAL nos itens numéricos.

    Analogia: o LLM é o "estagiário" que escreve o rascunho do laudo; o Python
    é o "engenheiro responsável" que mede com trena e assina. Se os dois
    discordam num item numérico (ex: altura da bacia), vale a medição do Python.

    Sem isto, o relatório HTML mostrava o status do LLM — que lia a altura
    TOTAL da bacia com caixa acoplada (0,81 m) e marcava Não Conforme, mesmo
    com o Python já descontando o tanque (rim = 0,435 m → Conforme).

    Itens qualitativos (texto) continuam com o LLM. O status original do LLM
    fica guardado em "status_llm_original" para a comparação da dissertação.
    """
    def _norm(i):
        return str(i).replace("–", "-").replace("—", "-").replace(" ", "")

    resultados = [dict(r) for r in (resultados_llm or [])]
    por_item = {}
    for l in linhas or []:
        por_item.setdefault(l["item_nbr"], []).append(l)

    for item, ls in por_item.items():
        if item in ITENS_QUALITATIVOS:
            continue
        st_py = status_item_python(ls)
        if st_py is None:
            continue
        medidos  = "; ".join(f"{(l['nome'] or '—')[:40]}: {l['valor_medido']}" for l in ls)
        mensagens = " | ".join(f"[{l['global_id']}] {l['mensagem']}" for l in ls if l.get("mensagem"))
        novo = {
            "status": st_py,
            "valor_encontrado": medidos,
            "valor_exigido": ls[0]["valor_exigido"],
            "elemento": ", ".join(sorted({(l['nome'] or '—')[:40] for l in ls})),
            "globalid": ", ".join(l["global_id"] or "" for l in ls),
            "tipo_ifc": ", ".join(sorted({l["ifc_class"] or "" for l in ls})),
            "recomendacao": f"[Verificação Python] {mensagens}",
            "fonte_veredito": "python",
        }
        alvo = next((r for r in resultados if _norm(r.get("item_nbr")) == _norm(item)), None)
        if alvo is None:
            resultados.append({"item_nbr": item, "categoria": CATEGORIAS.get(item, ""),
                               "status_llm_original": "—", **novo})
        else:
            alvo["status_llm_original"] = alvo.get("status", "—")
            alvo.update(novo)
    return resultados


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


def classificar_prototipo(resultados_llm: list[dict]) -> dict:
    """
    Classificação de validação do protótipo, conforme definida em
    nbr9050_rules.json ("status_validacao_prototipo"):
      Completo   → nenhum item aplicável ficou Indeterminado
      Parcial    → há Indeterminados, mas a maioria dos itens foi avaliada
      Incompleto → a maior parte dos itens aplicáveis ficou Indeterminada
    Itens N/A (não se aplicam ao modelo) saem da conta.
    """
    cats = [classificar_status(r.get("status", "")) for r in (resultados_llm or [])]
    aplicaveis = [c for c in cats if c != "N/A"]
    indet = aplicaveis.count("Indeterminado")
    if not aplicaveis:
        classe = "Incompleto"
    elif indet == 0:
        classe = "Completo"
    elif indet <= len(aplicaveis) / 2:
        classe = "Parcial"
    else:
        classe = "Incompleto"
    return {"classe": classe, "avaliados": len(aplicaveis) - indet,
            "aplicaveis": len(aplicaveis), "indeterminados": indet}
