"""
verificacoes.py — Classificação de status e cálculo determinístico do resumo.

Nesta etapa contém a lógica que já existia (classificar_status, calcular_resumo).
Nas próximas etapas recebe a tabela de verificação POR ELEMENTO e o nível de
confiança derivado da origem do dado.
"""


from geometria_nbr import dist_bbox


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
RAMPA_I_MIN = 5.0              # 6.6 — abaixo de 5% a NBR não considera a superfície uma rampa
DESNIVEL_SEM_TRAT_MM = 5.0     # 6.3.4 — até 5 mm dispensa tratamento especial
DESNIVEL_CHANFRO_MM = 20.0     # 6.3.4 — de 5 a 20 mm exige chanfro 1:2 (50%)
TOL_MODELAGEM_MM = 0.5         # 6.3.4 — arredondamento de cotas no modelo (0,005 vira 4,9999…)

TERMOS_LAV_CONFORME = ["suspenso", "sem coluna", "embutir", "semiencaixe", "encaixe"]
TERMOS_LAV_NAO_CONF = ["com coluna", "pedestal", "coluna suspensa"]
TERMOS_MACANETA_OK = ["alavanca", "lever", "handle"]
TERMOS_MACANETA_NOK = ["esférica", "esferica", "knob", "giratória", "giratoria", "round"]

CATEGORIAS = {
    "6.6": "Rampas", "6.11.1": "Corredores", "6.11.2": "Portas",
    "6.11.3": "Janelas", "5.4.3": "Corrimão", "7.5": "Circulação sanitários",
    "7.7.2.1": "Bacia sanitária", "7.8": "Lavatório", "7.6-7.8": "Barras de apoio",
    "4.6.6": "Maçaneta", "6.3.4": "Desníveis de piso",
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


TERMOS_PROP_FERRAGEM = ["ferrage", "maçaneta", "macaneta", "puxador", "fechadura", "handle", "hardware", "lever"]


def _textos_ferragem(p):
    """
    Onde procurar o tipo de maçaneta, em ordem:
      1) Name / ObjectType / Description da porta;
      2) propriedades de FERRAGEM nos Psets da instância e do TIPO da porta
         (só as que têm "ferragem", "maçaneta", "puxador", "fechadura",
         "handle"... no NOME da propriedade — evita falsos positivos como
         "round" dentro de "background").
    Devolve lista de (origem, texto).
    """
    achados = [("nome", " ".join(str(p.get(k) or "") for k in ("Name", "ObjectType", "Description")))]
    for chave, rotulo in (("Psets", "Pset da porta"), ("Psets_tipo", "Pset do tipo")):
        for pset, props in (p.get(chave) or {}).items():
            for nome_prop, valor in (props or {}).items():
                if isinstance(valor, str) and any(t in str(nome_prop).lower() for t in TERMOS_PROP_FERRAGEM):
                    achados.append((f"{rotulo} '{pset}' → {nome_prop}", valor))
    return achados


def _v_macaneta(portas):
    linhas = []
    for p in portas:
        if not p.get("pne_pcd_confirmado"):
            continue  # escopo: só portas que dão acesso a ambiente PNE/PCD
        amb = p.get("ambientes_adjacentes")
        onde = f" Porta entre: {' ↔ '.join(amb)}." if amb else ""
        st_, msg, fonte, medido = "Indeterminado", "Tipo de maçaneta não informado no nome nem nos Psets de ferragem (instância e tipo).", "texto_nome", "(sem informação)"
        for origem, texto in _textos_ferragem(p):
            t = texto.lower()
            if any(x in t for x in TERMOS_MACANETA_NOK):
                st_, msg = "Não Conforme", f"{origem}: \"{texto}\" indica maçaneta esférica/giratória."
            elif any(x in t for x in TERMOS_MACANETA_OK):
                st_, msg = "Conforme", f"{origem}: \"{texto}\" indica maçaneta tipo alavanca."
            else:
                continue
            fonte = "texto_nome" if origem == "nome" else "pset_ferragem"
            medido = f"\"{texto[:60]}\""
            break
        linhas.append(_linha(p, "4.6.6", medido, "Maçaneta tipo alavanca", st_, fonte, msg + onde))
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
    """
    6.6 — inclinação por faixa de desnível.

    Abaixo de 5% a NBR 9050 não considera a superfície uma rampa (é piso
    inclinado de rota acessível): registra como Conforme, sem exigir os
    limites da tabela, mas avisa quando está "colado" no limite (≥ 4,5%) —
    um arredondamento no projeto pode virar 5% na obra.
    """
    linhas = []
    for r in rampas:
        tipo_ifc = r.get("tipo_ifc", "")
        is_explicit_ramp = "IfcRamp" in tipo_ifc
        rise, incl = _num(r.get("OverallRise_m")), _num(r.get("inclinacao_pct"))
        fonte = r.get("fonte_dados_rampa", "nao_encontrado")

        if not is_explicit_ramp:
            rise_fb, incl_fb, eh_rampa_fb = _detectar_rampa_fallback(r)
            if not eh_rampa_fb:
                continue
            rise, incl = rise_fb, incl_fb
        como = r.get("deteccao_rampa")
        marker = f" [fallback IfcSlab — {como}]" if como else (" [fallback: slab inclinado]" if "fallback" in fonte else "")

        if rise is None or incl is None:
            linhas.append(_linha(r, "6.6", "—", "Inclinação por faixa de desnível", "Indeterminado",
                                 fonte, "Sem OverallRise/OverallRun nem geometria utilizável." + marker))
            continue

        medido = f"desnível={rise:.3f} m | i={incl:.2f}%"
        if r.get("cota_inicio_m") is not None and r.get("cota_fim_m") is not None:
            medido += f" | cotas {r['cota_inicio_m']:.3f}→{r['cota_fim_m']:.3f} m"

        if incl < RAMPA_I_MIN:
            aviso = (f" Inclinação {incl:.2f}% muito próxima de 5% — confirmar no projeto/obra." if incl >= 4.5 else "")
            linhas.append(_linha(r, "6.6", medido, f"i < {RAMPA_I_MIN:.0f}% (não é rampa) ou tabela 6.6",
                                 "Conforme", fonte,
                                 f"Inclinação {incl:.2f}% < 5%: pela NBR 9050 a superfície não é considerada rampa "
                                 f"(piso inclinado de rota acessível)." + aviso + marker))
            continue

        lim = _limite_rampa(rise)
        if lim is None:
            linhas.append(_linha(r, "6.6", medido, "—", "Indeterminado", fonte,
                                 "Desnível > 1,50 m: fora da tabela verificada." + marker))
            continue
        ok = incl <= lim
        linhas.append(_linha(r, "6.6", medido, f"i ≤ {lim:.2f}%",
                             "Conforme" if ok else "Não Conforme", fonte,
                             ("" if ok else f"Inclinação {incl:.2f}% acima do limite {lim:.2f}%.") + marker))
    return linhas
# └─ fim PONTO 1 ──────────────────────────────────────────────────────────────


def _descrever_corrimaos(assoc):
    """Texto curto com o que a geometria encontrou ao lado da rampa."""
    partes = []
    for c in assoc:
        alturas = []
        if c.get("tem_070"): alturas.append("0,70")
        if c.get("tem_092"): alturas.append("0,92")
        par = "acompanha a rampa" if c.get("paralelo_a_rampa") else \
              f"NÃO acompanha a inclinação (altura varia {c.get('variacao_altura_m', 0):.2f} m)"
        partes.append(f"lado {c.get('lado')}: [{c.get('id')}] topo {c.get('altura_topo_m', 0):.2f} m, "
                      f"níveis {'/'.join(alturas) or 'fora de 0,70/0,92'} m, {par}")
    return "; ".join(partes)


def _v_corrimao(escadas, rampas, corrimaos):
    """
    5.4.3 — corrimão nos dois lados, a 0,70 e 0,92 m, quando desnível > 0,19 m.

    Quando é obrigatório:
      RAMPA (i ≥ 5%)  → SEMPRE, em ambos os lados, qualquer que seja o desnível
                        (NBR 9050: toda rampa tem corrimão de duas alturas);
      i < 5%          → não é rampa pela NBR → N/A (corrimãos encontrados
                        aparecem como informação);
      ESCADA          → desnível > 0,19 m (critério do nbr9050_rules.json).

    Rampas: usa a associação GEOMÉTRICA feita na extração (corrimaos_associados):
    corrimão ao lado da rampa, lado (esquerdo/direito), alturas medidas a partir
    da SUPERFÍCIE da rampa e se ele acompanha a inclinação.
    Escadas: mantém o critério anterior (Psets), sem associação geométrica.
    """
    linhas = []
    tem_railing = len(corrimaos) > 0
    tem_duplo = any(c.get("corrimao_duplo_070_092") for c in corrimaos)
    exig = f"Escada: corrimão 2 lados, 0,70 e 0,92 m, se desnível > {DESNIVEL_CORRIMAO:.2f} m"

    for e in [e for e in escadas if e.get("tipo_ifc") == "IfcStairFlight"]:
        d = _num(e.get("desnivel_m"))
        fonte = "associacao_nao_verificada"
        if d is None:
            linhas.append(_linha(e, "5.4.3", "—", exig, "Indeterminado", fonte, "Desnível não calculável."))
        elif d <= DESNIVEL_CORRIMAO:
            linhas.append(_linha(e, "5.4.3", f"desnível={d:.2f} m", exig, "N/A", fonte, "Desnível não exige corrimão."))
        elif not tem_railing:
            linhas.append(_linha(e, "5.4.3", f"desnível={d:.2f} m", exig, "Indeterminado", fonte,
                                 "Nenhum IfcRailing no modelo — verificar in loco."))
        else:
            linhas.append(_linha(e, "5.4.3", f"desnível={d:.2f} m", exig,
                                 "Conforme" if tem_duplo else "Não Conforme", fonte,
                                 "Associação corrimão↔escada não verificada geometricamente."))

    for r in rampas:
        incl = _num(r.get("inclinacao_pct"))
        if "IfcRamp" not in r.get("tipo_ifc", "") and not (incl is not None and 2.0 < incl < 30.0):
            continue  # mesmo filtro do 6.6: só o que foi tratado como rampa
        d = _num(r.get("OverallRise_m"))
        assoc = r.get("corrimaos_associados")
        fonte = "geometria_associacao_corrimao" if assoc is not None else "associacao_nao_verificada"
        info = _descrever_corrimaos(assoc or [])
        medido = (f"desnível={d:.2f} m" if d is not None else "desnível=—") + \
                 (f" | {len(set(c['lado'] for c in assoc))} lado(s) com corrimão" if assoc else "")

        exig_r = "Rampa (i ≥ 5%): corrimão nos 2 lados, 0,70 e 0,92 m, paralelo à rampa"
        if incl is not None and incl < RAMPA_I_MIN:
            msg = (f"Inclinação {incl:.2f}% < 5%: pela NBR 9050 não é rampa — corrimão não obrigatório.")
            if info:
                msg += f" Corrimãos encontrados (informativo): {info}."
            linhas.append(_linha(r, "5.4.3", medido, exig_r, "N/A", fonte, msg))
            continue
        if incl is None:
            linhas.append(_linha(r, "5.4.3", medido, exig_r, "Indeterminado", fonte,
                                 "Inclinação não calculável — não dá para saber se é rampa."))
            continue
        exig = exig_r
        if assoc is None:
            linhas.append(_linha(r, "5.4.3", medido, exig,
                                 "Indeterminado" if not tem_railing else ("Conforme" if tem_duplo else "Não Conforme"),
                                 fonte, "Sem geometria para associar corrimão↔rampa — verificar in loco."))
            continue
        lados = {c["lado"] for c in assoc}
        lados_ok = {c["lado"] for c in assoc if c.get("tem_070") and c.get("tem_092") and c.get("paralelo_a_rampa")}
        if len(lados_ok) == 2:
            st_ = "Conforme"
        elif not assoc:
            st_ = "Não Conforme"
        else:
            st_ = "Parcial"
        falta = []
        if len(lados) < 2: falta.append("corrimão em só um lado" if lados else "nenhum corrimão ao lado da rampa")
        if lados - lados_ok: falta.append("lado(s) " + ", ".join(sorted(lados - lados_ok)) + " sem 0,70/0,92 m paralelos à rampa")
        linhas.append(_linha(r, "5.4.3", medido, exig, st_, fonte,
                             ("; ".join(falta) + ". " if falta else "") + (f"Detalhe: {info}." if info else "")))
    return linhas


def _resumo_diag_lajes(diag):
    """Uma linha por laje: o que a extração conseguiu ler (para depurar 'sem piso')."""
    partes = []
    for d in diag or []:
        nome = (d.get("nome") or d.get("GlobalId") or "?").split(":")
        nome = nome[1] if len(nome) >= 2 else nome[0]
        if d.get("problema"):
            partes.append(f"{nome[:30]}: {d['problema']}")
        else:
            partes.append(f"{nome[:30]}: {d.get('n_triangulos_horizontais')} faces horiz., "
                          f"x {d.get('x')}, y {d.get('y')}, z {d.get('z')}")
    return " | ".join(partes)


def _v_desniveis(desniveis, chanfros, diag_lajes=None):
    """
    6.3.4 — desníveis medidos nos pontos de passagem (portas e juntas de piso).
      ≤ 5 mm       → Conforme (NBR: dispensa tratamento especial)
      5 a 20 mm    → Conforme se houver chanfro modelado; senão Indeterminado
                     (exige chanfro 1:2 — conferir detalhe/obra)
      > 20 mm      → Não Conforme (é degrau: rota acessível pede rampa)
    Tolerância de 0,5 mm para ruído de modelagem/arredondamento.
    """
    linhas = []
    tem_chanfro = bool(chanfros)
    exig = "≤ 5 mm livre | 5–20 mm com chanfro 1:2"
    for x in desniveis:
        mm = x.get("desnivel_mm")
        el = {"GlobalId": x.get("GlobalId"), "Name": x.get("trecho") or x.get("Name"),
              "tipo_ifc": x.get("tipo_ifc"), "pavimento": x.get("pavimento")}
        onde = "porta" if x.get("tipo") == "porta" else "junta de lajes"
        if mm is None:
            linhas.append(_linha(el, "6.3.4", "—", exig, "Indeterminado", "geometria_lajes",
                                 f"Sem piso modelado de um dos lados da {onde} "
                                 f"(cotas lidas: {x.get('cota_lado_1_m')} / {x.get('cota_lado_2_m')} m; "
                                 f"pontos testados: {x.get('sondas_xy')}). Verificar se há laje dos dois lados. "
                                 f"Lajes lidas: {_resumo_diag_lajes(diag_lajes)}"))
            continue
        medido = f"{mm:.1f} mm ({x.get('cota_lado_1_m')} / {x.get('cota_lado_2_m')} m)"
        if mm <= DESNIVEL_SEM_TRAT_MM + TOL_MODELAGEM_MM:
            st_ = "Conforme"
            msg = f"Desnível de {mm:.1f} mm na {onde}: até 5 mm dispensa tratamento especial."
        elif mm <= DESNIVEL_CHANFRO_MM + TOL_MODELAGEM_MM:
            st_ = "Conforme" if tem_chanfro else "Indeterminado"
            msg = (f"Desnível de {mm:.1f} mm na {onde}: exige chanfro com inclinação ≤ 1:2 (50%). "
                   + ("Chanfro modelado no projeto — conferir posição." if tem_chanfro
                      else "Nenhum chanfro modelado — verificar detalhe de soleira/obra."))
        else:
            st_ = "Não Conforme"
            msg = f"Desnível de {mm:.1f} mm na {onde}: acima de 20 mm é degrau — rota acessível exige rampa."
        linhas.append(_linha(el, "6.3.4", medido, exig, st_, "geometria_lajes", msg))
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


# ┌─ PONTO 4: Barras de apoio (NBR 9050:2020 — 7.7.2.2 bacia | 7.8.1 lavatório) ─
#
# Cada barra é comparada com a regra DA PEÇA A QUE SERVE — não com uma régua
# única. Analogia: é como conferir pilares e vigas — cada elemento tem a sua
# tabela; medir tudo pela tabela do pilar reprova a viga que está certa.
#
# 1) Associação: a barra pertence à peça (bacia ou lavatório) mais próxima em
#    planta (até 1,0 m).
# 2) Tipo, pela geometria:
#    bacia + vertical                         → VERTICAL LATERAL (7.7.2.2.1)
#    bacia + horizontal paralela à bacia      → HORIZONTAL LATERAL (7.7.2.2.1)
#    bacia + horizontal transversal à bacia   → FUNDO (7.7.2.2.2 / .3)
#    lavatório + horizontal / vertical        → 7.8.1 d / 7.8.1 e
# 3) Régua de cada tipo (adulto | infantil, Figuras 106 a 111):
#    lateral e fundo: eixo a 0,75 m (0,60 infantil), comprimento ≥ 0,80 m
#    fundo com CAIXA ACOPLADA: eixo até 0,89 m (A1; 0,72 infantil) e
#        ≥ 0,04 m acima da tampa da caixa
#    vertical: comprimento ≥ 0,70 m, fixação inferior 0,10 m acima do eixo
#        da barra horizontal lateral
#    lavatório horizontal: FACE SUPERIOR a 0,78–0,80 m
#    lavatório vertical: início a 0,90 m, comprimento ≥ 0,40 m
# 4) Três faixas (decisão do projeto): dentro da norma → Conforme;
#    até ±2 cm além → Parcial (verificar na obra/projeto); além disso →
#    Não Conforme. Barra sem geometria/associação → Indeterminado.

TOL_BARRA_CONF = 0.01      # ruído de modelagem (arredondamento da família)
TOL_BARRA_PARC = 0.02      # faixa "Parcial": validar manualmente
BARRA_REF = {   # (adulto, infantil)
    "A": (0.75, 0.60),       # eixo das barras lateral e de fundo
    "A1": (0.89, 0.72),      # máximo da barra de fundo com caixa acoplada
}
BARRA_COMP_HORIZ = 0.80
BARRA_COMP_VERT_BACIA = 0.70
BARRA_ACIMA_HORIZ = 0.10
BARRA_FOLGA_TAMPA = 0.04
LAV_BARRA_TOPO = (0.78, 0.80)
LAV_BARRA_VERT_BASE = 0.90
LAV_BARRA_VERT_COMP = 0.40
BARRA_DIST_ASSOC = 1.0


def _faixa(valor, vmin, vmax):
    """Classifica um valor contra [vmin, vmax] nas 3 faixas do projeto."""
    if vmin - TOL_BARRA_CONF <= valor <= vmax + TOL_BARRA_CONF:
        return "Conforme"
    if vmin - TOL_BARRA_PARC <= valor <= vmax + TOL_BARRA_PARC:
        return "Parcial"
    return "Não Conforme"


def _pior(*sts):
    ordem = ["Não Conforme", "Indeterminado", "Parcial", "Conforme"]
    return min(sts, key=ordem.index)


def _m(v):
    return f"{v:.3f} m".replace(".", ",")


def _v_barras_sem_geometria(barras):
    """Fallback (sem ficha geométrica): régua única 0,70–0,80 m, como antes."""
    linhas = []
    h_min, h_max = BARRA_ALT_REF - BARRA_TOL, BARRA_ALT_REF + BARRA_TOL
    exig = f"Horizontal: {h_min:.2f}–{h_max:.2f} m (eixo)"
    for b in barras:
        h, fonte = _altura_equip(b)
        if h is None:
            linhas.append(_linha(b, "7.6-7.8", "—", exig, "Indeterminado", fonte,
                                 "Sem altura disponível — verificar in loco."))
            continue
        st_ = _faixa(h, h_min, h_max)
        if st_ == "Não Conforme":
            st_ = "Indeterminado"   # sem saber o tipo da barra, não dá para reprovar
        msg = "" if st_ == "Conforme" else (f"Altura {h:.3f} m — sem geometria para identificar o tipo "
                                            "da barra (lateral/fundo/vertical/lavatório); verificar in loco.")
        linhas.append(_linha(b, "7.6-7.8", f"eixo={h:.3f} m", exig, st_, fonte, msg))
    return linhas


def _v_barras(barras, bacias=None, lavatorios=None):
    pecas = [("bacia", p) for p in (bacias or []) if p.get("geo")] + \
            [("lavatório", p) for p in (lavatorios or []) if p.get("geo")]
    if not pecas or not any(b.get("geo") for b in barras):
        return _v_barras_sem_geometria(barras)

    # 1) associação barra → peça mais próxima
    assoc = []
    for b in barras:
        g = b.get("geo")
        if not g:
            assoc.append((b, None, None)); continue
        dists = [(dist_bbox(g["bbox"], p["geo"]["bbox"]), tipo, p) for tipo, p in pecas]
        d, tipo, p = min(dists, key=lambda t: t[0])
        assoc.append((b, (tipo, p) if d <= BARRA_DIST_ASSOC else None, d))

    # eixo das barras horizontais LATERAIS de cada bacia (referência da vertical)
    def _tipo_barra_bacia(g, bacia):
        if g["vertical"]:
            return "vertical"
        return "lateral" if g["eixo_maior"] == bacia["geo"]["eixo_planta"] else "fundo"

    ref_lateral = {}
    for b, pa, _ in assoc:
        if pa and pa[0] == "bacia" and _tipo_barra_bacia(b["geo"], pa[1]) == "lateral":
            ref_lateral.setdefault(pa[1]["GlobalId"], []).append(b["geo"]["z_eixo"])

    linhas = []
    for b, pa, dist in assoc:
        g = b.get("geo")
        fonte = "geometria_bbox_barra"
        if g is None:
            linhas.append(_linha(b, "7.6-7.8", "—", "—", "Indeterminado", "nao_encontrado",
                                 "Barra sem geometria — verificar in loco."))
            continue
        if pa is None:
            linhas.append(_linha(b, "7.6-7.8", f"eixo={g['z_eixo']:.3f} m", "—", "Indeterminado", fonte,
                                 f"Nenhuma bacia/lavatório a menos de {BARRA_DIST_ASSOC:.1f} m — tipo da barra "
                                 "não identificado; verificar in loco."))
            continue
        tipo_peca, peca = pa
        infantil = "infantil" in (str(peca.get("Name")) + " " + str(b.get("Name"))).lower()
        k = 1 if infantil else 0
        publico = " (infantil)" if infantil else ""
        comp = g["comprimento"]

        if tipo_peca == "bacia":
            tipo = _tipo_barra_bacia(g, peca)
            caixa = "acoplada" in str(peca.get("Name", "")).lower()
            if tipo == "lateral":
                A = BARRA_REF["A"][k]
                st_h = _faixa(g["z_eixo"], A, A)
                st_c = "Conforme" if comp >= BARRA_COMP_HORIZ - TOL_BARRA_CONF else "Não Conforme"
                st_ = _pior(st_h, st_c)
                exig = f"7.7.2.2.1 horizontal lateral{publico}: eixo {A:.2f} m; comp. ≥ {BARRA_COMP_HORIZ:.2f} m"
                medido = f"lateral | eixo={_m(g['z_eixo'])} | comp={_m(comp)}"
                msg = []
                if st_h != "Conforme": msg.append(f"eixo {_m(g['z_eixo'])} (exigido {A:.2f} m)")
                if st_c != "Conforme": msg.append(f"comprimento {_m(comp)} < {BARRA_COMP_HORIZ:.2f} m")
            elif tipo == "fundo":
                A = BARRA_REF["A"][k]
                if caixa:
                    A1 = BARRA_REF["A1"][k]
                    st_h = _faixa(g["z_eixo"], A, A1)
                    tampa = peca["geo"]["z_max"]
                    folga = g["z_miolo_min"] - tampa
                    st_t = "Conforme" if folga >= BARRA_FOLGA_TAMPA - TOL_BARRA_CONF else \
                           ("Parcial" if folga >= BARRA_FOLGA_TAMPA - TOL_BARRA_PARC else "Não Conforme")
                    exig = (f"7.7.2.2.3 fundo c/ caixa acoplada{publico}: eixo {A:.2f}–{A1:.2f} m; "
                            f"≥ {BARRA_FOLGA_TAMPA:.2f} m acima da tampa; comp. ≥ {BARRA_COMP_HORIZ:.2f} m")
                    medido = f"fundo | eixo={_m(g['z_eixo'])} | {_m(folga)} acima da tampa | comp={_m(comp)}"
                else:
                    st_h = _faixa(g["z_eixo"], A, A)
                    st_t, folga = "Conforme", None
                    exig = f"7.7.2.2.2 fundo{publico}: eixo {A:.2f} m; comp. ≥ {BARRA_COMP_HORIZ:.2f} m"
                    medido = f"fundo | eixo={_m(g['z_eixo'])} | comp={_m(comp)}"
                st_c = "Conforme" if comp >= BARRA_COMP_HORIZ - TOL_BARRA_CONF else "Não Conforme"
                st_ = _pior(st_h, st_t, st_c)
                msg = []
                if st_h != "Conforme": msg.append(f"eixo {_m(g['z_eixo'])} fora da faixa")
                if st_t != "Conforme": msg.append(f"só {_m(folga)} acima da tampa (mín. {BARRA_FOLGA_TAMPA:.2f} m)")
                if st_c != "Conforme": msg.append(f"comprimento {_m(comp)} < {BARRA_COMP_HORIZ:.2f} m")
            else:  # vertical
                refs = ref_lateral.get(peca["GlobalId"])
                st_c = "Conforme" if comp >= BARRA_COMP_VERT_BACIA - TOL_BARRA_CONF else "Não Conforme"
                if refs:
                    alvo = min(refs) + BARRA_ACIMA_HORIZ
                    st_b = _faixa(g["z_base_eixo"], alvo, alvo)
                    exig = (f"7.7.2.2.1 vertical{publico}: comp. ≥ {BARRA_COMP_VERT_BACIA:.2f} m; "
                            f"fixação inferior {BARRA_ACIMA_HORIZ:.2f} m acima da horizontal ({alvo:.2f} m)")
                else:
                    alvo = None
                    st_b = "Indeterminado"
                    exig = (f"7.7.2.2.1 vertical{publico}: comp. ≥ {BARRA_COMP_VERT_BACIA:.2f} m; "
                            f"{BARRA_ACIMA_HORIZ:.2f} m acima da barra horizontal")
                st_ = _pior(st_b, st_c)
                medido = f"vertical | fixação inferior={_m(g['z_base_eixo'])} | comp={_m(comp)}"
                msg = []
                if st_b == "Indeterminado": msg.append("sem barra horizontal lateral identificada para referência")
                elif st_b != "Conforme": msg.append(f"fixação inferior {_m(g['z_base_eixo'])} (exigido {alvo:.2f} m)")
                if st_c != "Conforme": msg.append(f"comprimento {_m(comp)} < {BARRA_COMP_VERT_BACIA:.2f} m")
        else:  # lavatório (7.8.1)
            if g["vertical"]:
                base = g["z_min"]
                st_b = _faixa(base, LAV_BARRA_VERT_BASE, LAV_BARRA_VERT_BASE)
                st_c = "Conforme" if comp >= LAV_BARRA_VERT_COMP - TOL_BARRA_CONF else "Não Conforme"
                st_ = _pior(st_b, st_c)
                exig = f"7.8.1 e) lavatório vertical: início a {LAV_BARRA_VERT_BASE:.2f} m; comp. ≥ {LAV_BARRA_VERT_COMP:.2f} m"
                medido = f"lavatório vertical | início={_m(base)} | comp={_m(comp)}"
                msg = []
                if st_b != "Conforme": msg.append(f"início {_m(base)} (exigido {LAV_BARRA_VERT_BASE:.2f} m)")
                if st_c != "Conforme": msg.append(f"comprimento {_m(comp)} < {LAV_BARRA_VERT_COMP:.2f} m")
            else:
                t0, t1 = LAV_BARRA_TOPO
                st_ = _faixa(g["z_topo"], t0, t1)
                exig = f"7.8.1 d) lavatório horizontal: face superior a {t0:.2f}–{t1:.2f} m"
                medido = f"lavatório horizontal | face superior={_m(g['z_topo'])}"
                desvio_cm = f"{abs(g['z_topo'] - (t1 if g['z_topo'] > t1 else t0)) * 100:.1f}".replace(".", ",")
                lado = "acima" if g["z_topo"] > t1 else "abaixo"
                msg = [] if st_ == "Conforme" else [
                    f"face superior {_m(g['z_topo'])} — {desvio_cm} cm {lado} do limite"]

        texto = ""
        if msg:
            texto = "; ".join(msg) + "."
            if st_ == "Parcial":
                texto += " Dentro de ±2 cm do limite — confirmar no projeto/obra."
        linhas.append(_linha(b, "7.6-7.8", medido, exig, st_, fonte, texto))
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

    Item fora daqui (continua só com o LLM): 7.7.1 (área de transferência
    lateral) — exige análise espacial ainda não implementada.
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
    linhas += _v_barras(c.get("barras", []), c.get("bacias", []), c.get("lavatorios", []))
    linhas += _v_macaneta(c.get("portas", []))
    linhas += _v_desniveis(c.get("desniveis", []), c.get("chanfros", []), c.get("diag_lajes", []))
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
    if all(s == "Conforme" for s in aval):
        # Conformes + elementos sem confirmação → não dá pra afirmar "Conforme"
        # para o item inteiro (critério conservador): fica Parcial.
        return "Parcial" if "Indeterminado" in st_ else "Conforme"
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

    Itens qualitativos (4.6.6 maçaneta, 7.8 lavatório) também seguem o Python —
    que aplica o ESCOPO certo (ex: maçaneta só em portas de ambiente PCD) —
    mas ficam sempre marcados com 🔍 (confirmação humana). O status original do
    LLM fica guardado em "status_llm_original" para a comparação da dissertação.
    """
    def _norm(i):
        return str(i).replace("–", "-").replace("—", "-").replace(" ", "")

    resultados = [dict(r) for r in (resultados_llm or [])]
    por_item = {}
    for l in linhas or []:
        por_item.setdefault(l["item_nbr"], []).append(l)

    for item, ls in por_item.items():
        st_py = status_item_python(ls)
        if st_py is None:
            continue
        cont = {k: sum(1 for l in ls if l["status"] == k)
                for k in ("Conforme", "Parcial", "Não Conforme", "Indeterminado")}
        pend = [l for l in ls if l["status"] != "Conforme" and l.get("mensagem")]
        resumo_cont = f"{cont['Conforme']} de {len(ls)} elementos conformes"
        extras = [f"{v} {k.lower()}" for k, v in cont.items() if k != "Conforme" and v]
        if extras:
            resumo_cont += " (" + ", ".join(extras) + ")"
        medidos = "; ".join(f"{(l['nome'] or '—')[:40]}: {l['valor_medido']}" for l in ls)
        if pend:
            rec = "[Verificação Python] " + " | ".join(f"[{l['global_id']}] {l['mensagem']}" for l in pend)
        else:
            rec = "[Verificação Python] Todos os elementos atendem — sem pendências."
        novo = {
            "status": st_py,
            "valor_encontrado": (resumo_cont + ". " + medidos) if len(ls) > 1 else medidos,
            "valor_exigido": " / ".join(sorted({l["valor_exigido"] for l in ls})),
            "elemento": ", ".join(sorted({(l['nome'] or '—')[:40] for l in ls})),
            "globalid": ", ".join(l["global_id"] or "" for l in ls),
            "tipo_ifc": ", ".join(sorted({l["ifc_class"] or "" for l in ls})),
            "recomendacao": rec,
            "requer_confirmacao_humana": bool(cont["Parcial"] or cont["Indeterminado"]
                                              or item in ITENS_QUALITATIVOS),
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


def gerar_observacoes(resultados: list[dict], resumo: dict) -> str:
    """
    Resumo executivo escrito em PYTHON a partir dos status FINAIS.

    Analogia: o LLM escrevia a "capa do laudo" ANTES do engenheiro revisar as
    medições — então a capa podia dizer "bacia não conforme" enquanto a tabela
    (já corrigida) dizia "Conforme". Agora a capa é escrita DEPOIS, com os
    mesmos números da tabela e dos cards. Impossível divergir.
    """
    def _lista(cat):
        return [r for r in resultados if classificar_status(r.get("status", "")) == cat]

    def _fmt(rs):
        return "; ".join(f"{r.get('item_nbr')} {CATEGORIAS.get(str(r.get('item_nbr')), r.get('categoria', ''))}".strip()
                         for r in rs)

    partes = [
        f"Avaliados {resumo.get('total', 0)} itens da NBR 9050:2020: "
        f"{resumo.get('conformes', 0)} conformes, {resumo.get('parciais', 0)} parciais, "
        f"{resumo.get('nao_conformes', 0)} não conformes, {resumo.get('indeterminados', 0)} indeterminados "
        f"e {resumo.get('na', 0)} N/A. Conformidade: {resumo.get('percentual_conformidade')} (bruta) | "
        f"{resumo.get('percentual_sobre_verificaveis')} (sobre itens aplicáveis)."
    ]
    if _lista("Conforme"):
        partes.append("CONFORMES: " + _fmt(_lista("Conforme")) + ".")
    atencao = _lista("Não Conforme") + _lista("Parcial")
    if atencao:
        partes.append("PONTOS DE ATENÇÃO: " + _fmt(atencao) + " — ver recomendações na tabela.")
    if _lista("Indeterminado"):
        partes.append("VERIFICAÇÃO MANUAL NECESSÁRIA: " + _fmt(_lista("Indeterminado")) + ".")
    if _lista("N/A"):
        partes.append("NÃO SE APLICAM A ESTE MODELO: " + _fmt(_lista("N/A")) + ".")
    corrigidos = [r for r in resultados if r.get("fonte_veredito") == "python"
                  and r.get("status_llm_original") not in (None, "—")
                  and classificar_status(r["status_llm_original"]) != classificar_status(r.get("status", ""))]
    if corrigidos:
        partes.append("STATUS DEFINIDO PELA VERIFICAÇÃO PYTHON (divergiu do LLM): " + "; ".join(
            f"{r['item_nbr']} (LLM: {r['status_llm_original']} → Python: {r['status']})" for r in corrigidos) + ".")
    return " ".join(partes)


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
