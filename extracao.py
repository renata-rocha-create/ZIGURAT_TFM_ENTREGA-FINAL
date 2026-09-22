"""
extracao.py — Leitura e pré-processamento do modelo IFC (IfcOpenShell + Shapely).

Recebe o caminho do .ifc e devolve um dicionário com os elementos relevantes
para os 12 itens da NBR 9050. Não conversa com o LLM nem com a interface.
"""
from pathlib import Path


def _estatisticas_portas(portas_todas: list[dict]) -> dict:
    """
    Calcula min/max e contagem de não conformidades sobre TODAS as portas
    do modelo — não só a amostra de 60 que é enviada ao prompt.

    POR QUÊ ISSO EXISTE: a amostra (`portas[:60]`) existe pra não estourar
    o orçamento de tokens do prompt quando o modelo tem centenas de portas.
    Mas se o LLM só vê 60 de, digamos, 265 portas, ele só consegue avaliar
    conformidade das 60 — as outras 205 nunca são checadas, e uma porta fora
    do padrão nelas passaria batido. Esta função varre a lista COMPLETA em
    Python (rápido, determinístico) e devolve um resumo estatístico que é
    anexado ao prompt ao lado da amostra — assim o veredito do LLM cobre
    o modelo inteiro, não só a fatia que caiu na amostra ilustrativa.
    """
    larguras = [(d["GlobalId"], d["OverallWidth_m"]) for d in portas_todas if d.get("OverallWidth_m") is not None]
    alturas  = [(d["GlobalId"], d["OverallHeight_m"]) for d in portas_todas if d.get("OverallHeight_m") is not None]

    if not larguras and not alturas:
        return {"total": len(portas_todas), "com_dimensoes": 0}

    gid_min_larg, min_larg = min(larguras, key=lambda x: x[1]) if larguras else (None, None)
    gid_min_alt, min_alt   = min(alturas, key=lambda x: x[1]) if alturas else (None, None)

    # NBR 9050 item 6.11.2: largura ≥ 0,80m e altura ≥ 2,10m
    nao_conf_largura = [gid for gid, l in larguras if l < 0.80]
    nao_conf_altura  = [gid for gid, a in alturas if a < 2.10]

    return {
        "total": len(portas_todas),
        "com_dimensoes": len(set(gid for gid, _ in larguras) | set(gid for gid, _ in alturas)),
        "largura_min_m": round(min_larg, 3) if min_larg is not None else None,
        "largura_min_globalid": gid_min_larg,
        "altura_min_m": round(min_alt, 3) if min_alt is not None else None,
        "altura_min_globalid": gid_min_alt,
        "n_nao_conformes_largura": len(nao_conf_largura),
        "n_nao_conformes_altura": len(nao_conf_altura),
        "globalids_nao_conformes_largura": nao_conf_largura[:15],
        "globalids_nao_conformes_altura": nao_conf_altura[:15],
    }


def extract_ifc_elements(ifc_path: str) -> dict:
    """
    Extrai e pré-processa elementos do IFC para auditoria NBR 9050.
    
    DESCOBERTAS DO MODELO AGO-ARQ (IFC2X3/Revit):
    - IfcStairFlight: em IFC2X3, NumberOfRisers/RiserHeight/TreadLength são atributos
      diretos da entidade e vêm em PÉS (→ x0.3048). Em IFC4 esses dados saem do
      Pset_StairFlightCommon/Pset_StairCommon ("NumberOfRiser" no singular) já em
      METROS — extract_ifc_elements detecta qual caso se aplica por elemento.
    - IfcDoor: OverallHeight (pos 9), OverallWidth (pos 10) estão em METROS → correto
    - IfcFlowTerminal: contém bacias, lavatórios, barras de apoio, torneiras — filtrar por nome
    - IfcRailing: contém guarda-corpos (não corrimão) — modelo não tem corrimão separado
    - IfcSpace: ausente neste modelo — fallback via IfcWall necessário
    - IfcRamp/IfcRampFlight: ausentes neste modelo
    """
    try:
        import ifcopenshell
    except ImportError:
        return {"error": "ifcopenshell não instalado. Execute: pip install ifcopenshell"}

    ifc    = ifcopenshell.open(ifc_path)
    schema = ifc.schema

    FT_TO_M = 0.3048  # Revit exporta dimensões de escadas em pés para IFC2X3

    def todos_psets(el):
        psets = {}
        try:
            for rel in getattr(el, "IsDefinedBy", []):
                if rel.is_a("IfcRelDefinesByProperties"):
                    pdef = rel.RelatingPropertyDefinition
                    if pdef.is_a("IfcPropertySet"):
                        props = {}
                        for p in getattr(pdef, "HasProperties", []):
                            try:
                                val = None
                                if hasattr(p, "NominalValue") and p.NominalValue:
                                    val = p.NominalValue.wrappedValue
                                props[p.Name] = val
                            except Exception:
                                pass
                        if props:
                            psets[pdef.Name] = props
        except Exception:
            pass
        return psets

    def info_basica(el, tipo_ifc=None):
        return {
            "GlobalId":    el.GlobalId,
            "Name":        getattr(el, "Name", None),
            "ObjectType":  getattr(el, "ObjectType", None),
            "Tag":         getattr(el, "Tag", None),
            "Description": getattr(el, "Description", None),
            "tipo_ifc":    tipo_ifc or el.is_a(),
        }

    def buscar_prop(psets, *termos):
        for ps in psets.values():
            for k, v in ps.items():
                if any(t in k.lower() for t in termos) and v is not None:
                    return v
        return None

    def buscar_todas_props(psets, *termos):
        """
        Como buscar_prop, mas coleta TODAS as ocorrências em vez de parar na
        primeira. Necessário para elementos compostos — ex: um único IfcRailing
        do Revit pode carregar 3 Psets diferentes ("Corrimão 1", "Corrimão 2",
        "Corrimão superior"), cada um com sua própria propriedade "Altura".
        Pegar só a primeira jogava fora 2 das 3 alturas reais do elemento.
        """
        achados = []
        for pset_nome, ps in psets.items():
            for k, v in ps.items():
                if any(t in k.lower() for t in termos) and v is not None:
                    achados.append({"pset": pset_nome, "propriedade": k, "valor": v})
        return achados

    def limpar_nulos(obj):
        if isinstance(obj, dict):
            return {k: limpar_nulos(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [limpar_nulos(i) for i in obj if i is not None]
        return obj

    def contar(tipo):
        try: return len(ifc.by_type(tipo))
        except: return 0

    resultado = {"schema": schema, "arquivo": Path(ifc_path).name, "elementos": {}}

    # ── Inventário ────────────────────────────────────────────────────────────
    resultado["inventario_modelo"] = {
        t: contar(t) for t in [
            "IfcDoor","IfcWindow","IfcStair","IfcStairFlight","IfcRamp","IfcRampFlight",
            "IfcRailing","IfcSpace","IfcSlab","IfcWall","IfcWallStandardCase",
            "IfcFlowTerminal","IfcFurnishingElement","IfcBuildingElementProxy",
        ]
    }

    # ── Filtro PNE/PCD — usado em portas (4.6.6) e sanitários (7.x) ──────────
    # A NBR 9050 item 4.6.6 (maçaneta tipo alavanca) é uma exigência geral de
    # rota acessível, mas por decisão do projeto/thesis, aqui só é cobrada nas
    # portas de sanitários PNE/PCD — as demais portas do modelo ficam fora do
    # escopo dessa checagem específica. Verifica: (1) nome/tipo do próprio
    # elemento; (2) se ausente, nome do IfcSpace que o contém.
    TERMOS_ACESSIVEL = ["pne", "pcd"]
    try:
        from ifcopenshell.util.element import get_container as _get_container
    except Exception:
        _get_container = None

    def eh_acessivel_pne(el, texto_proprio):
        if any(t in texto_proprio for t in TERMOS_ACESSIVEL):
            return True, "nome_elemento"
        if _get_container:
            try:
                cont = _get_container(el)
                if cont is not None and cont.is_a("IfcSpace"):
                    nome_cont = ((getattr(cont, "Name", "") or "") + " " + (getattr(cont, "LongName", "") or "")).lower()
                    if any(t in nome_cont for t in TERMOS_ACESSIVEL):
                        return True, "nome_espaco_continente"
            except Exception:
                pass
        return False, None

    # ── 1. PORTAS (6.11.2, 4.6.6) ────────────────────────────────────────────
    # IfcDoor IFC2X3: campo 9=OverallHeight, campo 10=OverallWidth (em metros)
    portas = []
    for el in ifc.by_type("IfcDoor"):
        d = info_basica(el, "IfcDoor")
        oh = getattr(el, "OverallHeight", None)
        ow = getattr(el, "OverallWidth", None)
        # Em IFC2X3 Revit: OverallHeight é o 1º parâmetro dimensional, OverallWidth o 2º
        d["OverallHeight_m"] = round(float(oh), 3) if oh else None
        d["OverallWidth_m"]  = round(float(ow), 3) if ow else None
        d["Psets"] = todos_psets(el)

        nome_porta = (getattr(el, "Name", "") or "").lower() + " " + (getattr(el, "ObjectType", "") or "").lower()
        pne_ok, pne_fonte = eh_acessivel_pne(el, nome_porta)
        d["pne_pcd_confirmado"] = pne_ok  # relevante só pro item 4.6.6 (maçaneta) — 6.11.2 (vão livre) vale pra todas
        if pne_fonte:
            d["pne_pcd_fonte"] = pne_fonte

        portas.append(d)
    resultado["elementos"]["IfcDoor"] = portas[:60]
    resultado["estatisticas_portas"] = _estatisticas_portas(portas)
    n_portas_pne = sum(1 for p in portas if p.get("pne_pcd_confirmado"))
    resultado["nota_portas_pne"] = (
        f"{n_portas_pne} de {len(portas)} portas foram identificadas em ambiente/nome PNE/PCD. "
        f"O item 4.6.6 (maçaneta tipo alavanca) deve ser avaliado SOMENTE nessas portas — "
        f"as demais ficam fora do escopo desse item específico (mas continuam valendo para 6.11.2, vão livre)."
    )

    # ── 2. RAMPAS (6.6) ─────────────────────────────────────────────────────
    def _geom_bbox_rise_run(el):
        """
        Fallback geométrico: quando não há OverallRise/OverallRun nem no atributo
        direto nem no Pset, estima a partir da geometria bruta.

        run = maior dimensão em planta (X ou Y) — essa parte é confiável.

        rise = precisa de cuidado: a rampa é modelada como uma LAJE inclinada
        com espessura própria (não uma superfície fina). Pegar direto
        (Z_max global − Z_min global) do sólido inteiro conta a espessura da
        laje NAS DUAS PONTAS junto com o desnível real, inflando o resultado
        (confirmado num caso real: bbox bruto deu 0,51m onde o desnível real,
        medido ponta a ponta pela cota média de cada extremidade, era 0,36m —
        diferença suficiente pra trocar "Não Conforme" por "Conforme").
        Para evitar isso: agrupa os vértices pelas pontas ao longo do eixo de
        percurso (percentis 15/85) e compara a cota Z MÉDIA de cada ponta —
        isso cancela a espessura da laje, que aparece igualmente nas duas pontas.
        """
        try:
            import ifcopenshell.geom
            import numpy as np
            gset = ifcopenshell.geom.settings()
            gset.set(gset.USE_WORLD_COORDS, True)
            shape = ifcopenshell.geom.create_shape(gset, el)
            verts = np.array(shape.geometry.verts).reshape(-1, 3)

            x_range = verts[:, 0].max() - verts[:, 0].min()
            y_range = verts[:, 1].max() - verts[:, 1].min()
            axis_idx = 0 if x_range >= y_range else 1
            run = round(float(max(x_range, y_range)), 3)

            axis_vals = verts[:, axis_idx]
            lo, hi = np.percentile(axis_vals, [15, 85])
            grupo_inicio = verts[axis_vals <= lo]
            grupo_fim    = verts[axis_vals >= hi]
            if len(grupo_inicio) and len(grupo_fim):
                rise = round(float(abs(grupo_fim[:, 2].mean() - grupo_inicio[:, 2].mean())), 3)
            else:
                rise = round(float(verts[:, 2].max() - verts[:, 2].min()), 3)  # fallback bruto

            return rise, run
        except Exception:
            return None, None

    rampas = []
    for tipo in ["IfcRamp", "IfcRampFlight"]:
        for el in ifc.by_type(tipo):
            d = info_basica(el, tipo)
            ps = todos_psets(el)
            d["Psets"] = ps

            rise_attr = getattr(el, "OverallRise", None)
            run_attr  = getattr(el, "OverallRun", None)
            rise_pset = buscar_prop(ps, "overallrise", "altura da rampa", "desnivel")
            run_pset  = buscar_prop(ps, "overallrun", "comprimento da rampa")
            slope_pset = buscar_prop(ps, "slope", "inclinacao", "inclinação")

            rise_m, run_m, fonte = None, None, "nao_encontrado"
            if rise_attr and run_attr:
                # IFC2X3: atributo direto, em pés
                rise_m = round(float(rise_attr) * FT_TO_M, 3)
                run_m  = round(float(run_attr) * FT_TO_M, 3)
                fonte = "atributo_direto_ifc2x3_pes"
            elif rise_pset and run_pset:
                # IFC4: Pset_RampFlightCommon/RampCommon, já em metros
                rise_m = round(float(rise_pset), 3)
                run_m  = round(float(run_pset), 3)
                fonte = "pset_ifc4_metros"
            else:
                # Nenhum dos dois → estima pela geometria (bounding box)
                rise_geo, run_geo = _geom_bbox_rise_run(el)
                if rise_geo and run_geo:
                    rise_m, run_m = rise_geo, run_geo
                    fonte = "geometria_bounding_box_ESTIMATIVA"

            d["OverallRise_m"] = rise_m
            d["OverallRun_m"]  = run_m
            d["fonte_dados_rampa"] = fonte
            if slope_pset is not None:
                d["Slope_pset_bruto"] = slope_pset  # valor cru do Pset — unidade não confirmada, conferir
            if rise_m and run_m and run_m > 0:
                d["inclinacao_pct"] = round(rise_m / run_m * 100, 2)
            rampas.append(d)

    # Fallback: IfcSlab modelado como rampa (nome contém "rampa"/"ramp"/"slope")
    for el in ifc.by_type("IfcSlab"):
        nome = (getattr(el, "Name", "") or "").lower()
        otype = (getattr(el, "ObjectType", "") or "").lower()
        if any(t in nome + otype for t in ["rampa", "ramp", "slope"]):
            d = info_basica(el, "IfcSlab(rampa-fallback)")
            d["Psets"] = todos_psets(el)
            rise_geo, run_geo = _geom_bbox_rise_run(el)
            if rise_geo and run_geo:
                d["OverallRise_m"] = rise_geo
                d["OverallRun_m"] = run_geo
                d["fonte_dados_rampa"] = "geometria_bounding_box_slab_ESTIMATIVA"
                if run_geo > 0:
                    d["inclinacao_pct"] = round(rise_geo / run_geo * 100, 2)
            rampas.append(d)
    resultado["elementos"]["Rampas"] = rampas
    resultado["nota_rampas"] = f"Modelo tem {contar('IfcRamp')} IfcRamp e {contar('IfcRampFlight')} IfcRampFlight. Sem rampas modeladas neste projeto."

    # ── 3. ESCADAS + DESNÍVEL CALCULADO (5.4.3) ───────────────────────────────
    # ATENÇÃO: RiserHeight e TreadLength do Revit/IFC2X3 estão em PÉS → x0.3048
    escadas = []
    for el in ifc.by_type("IfcStairFlight"):
        d = info_basica(el, "IfcStairFlight")
        ps = todos_psets(el)
        d["Psets"] = ps

        # ── Estratégia por CAMPO (não por elemento inteiro): cada campo tenta o
        # atributo direto (IFC2X3, em pés) e, se vier vazio, cai pro Pset (IFC4,
        # "NumberOfRiser" no singular, já em metros) — independentemente dos
        # outros campos. Isso cobre o caso real de um Revit preencher RiserHeight
        # automaticamente mas deixar NumberOfRisers em branco (ou vice-versa),
        # que a versão anterior (cascata por elemento) não pegava.
        nr_attr = getattr(el, "NumberOfRisers", None)
        nt_attr = getattr(el, "NumberOfTreads", None)
        rh_attr = getattr(el, "RiserHeight", None)
        tl_attr = getattr(el, "TreadLength", None)

        fontes = []

        if nr_attr is not None:
            nr = nr_attr
            fontes.append("NumberOfRisers:atributo")
        else:
            nr = buscar_prop(ps, "numberofriser", "numberofrisers", "número de espelhos", "numero de espelhos")
            if nr is not None:
                fontes.append("NumberOfRisers:pset")

        if nt_attr is not None:
            nt = nt_attr
            fontes.append("NumberOfTreads:atributo")
        else:
            nt = buscar_prop(ps, "numberoftread", "número de pisos", "numero de pisos")
            if nt is not None:
                fontes.append("NumberOfTreads:pset")

        if rh_attr is not None:
            rh_m = round(float(rh_attr) * FT_TO_M, 4)
            fontes.append("RiserHeight:atributo_pes")
        else:
            rh_pset = buscar_prop(ps, "riserheight", "altura do espelho")
            rh_m = round(float(rh_pset), 4) if rh_pset is not None else None
            if rh_m is not None:
                fontes.append("RiserHeight:pset_metros")

        if tl_attr is not None:
            tl_m = round(float(tl_attr) * FT_TO_M, 4)
            fontes.append("TreadLength:atributo_pes")
        else:
            tl_pset = buscar_prop(ps, "treadlength", "largura do piso")
            tl_m = round(float(tl_pset), 4) if tl_pset is not None else None
            if tl_m is not None:
                fontes.append("TreadLength:pset_metros")

        d["fonte_dados_escada"] = ", ".join(fontes) if fontes else "nao_encontrado"

        d["NumberOfRisers"] = int(float(nr)) if nr is not None else None
        d["NumberOfTreads"] = int(float(nt)) if nt is not None else None
        d["RiserHeight_m"]  = rh_m
        d["TreadLength_m"]  = tl_m

        # Desnível calculado = NumberOfRisers × RiserHeight (já em metros)
        if d["NumberOfRisers"] and d["RiserHeight_m"]:
            d["desnivel_m"] = round(d["NumberOfRisers"] * d["RiserHeight_m"], 3)

        escadas.append(d)

    # Também inclui IfcStair (container) para contexto
    for el in ifc.by_type("IfcStair"):
        d = info_basica(el, "IfcStair")
        d["Psets"] = todos_psets(el)
        escadas.append(d)

    resultado["elementos"]["Escadas"] = escadas
    resultado["nota_escadas"] = (
        f"RiserHeight_m e TreadLength_m já normalizados para metros — via atributo direto "
        f"convertido de pés (schema IFC2X3) ou via Pset_StairCommon/Pset_StairFlightCommon já "
        f"em metros (schema IFC4). Veja 'fonte_dados_escada' em cada item para a origem. "
        f"Use desnivel_m = NumberOfRisers × RiserHeight_m para calcular o desnível total."
    )

    # ── 4. CORRIMÕES / GUARDA-CORPOS (5.4.3) ─────────────────────────────────
    TOLERANCIA_ALTURA = 0.03  # 3cm de tolerância pra bater com 0,70m/0,92m
    corrimaos = []
    algum_com_corrimao_duplo = False
    for el in ifc.by_type("IfcRailing"):
        d = info_basica(el, "IfcRailing")
        ps = todos_psets(el)
        d["Psets"] = ps

        # Um único IfcRailing pode conter VÁRIOS sub-Psets com "Altura" própria
        # (ex: corrimão inferior, corrimão superior, guarda-corpo) — coleta todas,
        # não só a maior/primeira encontrada.
        alturas_encontradas = buscar_todas_props(ps, "altura", "height")
        d["alturas_detalhadas"] = alturas_encontradas
        valores = sorted({round(float(a["valor"]), 3) for a in alturas_encontradas})
        d["alturas_m"] = valores

        tem_070 = any(abs(v - 0.70) <= TOLERANCIA_ALTURA for v in valores)
        tem_092 = any(abs(v - 0.92) <= TOLERANCIA_ALTURA for v in valores)
        d["corrimao_duplo_070_092"] = tem_070 and tem_092
        if d["corrimao_duplo_070_092"]:
            algum_com_corrimao_duplo = True

        nome = (getattr(el, "Name", "") or "").lower()
        d["tipo_elemento"] = "guarda-corpo" if "guarda" in nome else ("corrimao" if "corrim" in nome else "railing")
        corrimaos.append(d)

    resultado["elementos"]["Corrimaos"] = corrimaos
    if not corrimaos:
        resultado["nota_corrimaos"] = "Modelo não tem nenhum IfcRailing."
    elif algum_com_corrimao_duplo:
        resultado["nota_corrimaos"] = (
            f"Modelo tem {len(corrimaos)} IfcRailing. Pelo menos um contém, em Psets separados dentro do "
            f"MESMO elemento, alturas compatíveis com corrimão duplo (0,70m e 0,92m) — verifique o campo "
            f"'alturas_m' de cada item para ver todas as alturas detectadas por elemento."
        )
    else:
        alturas_todas = sorted({v for c in corrimaos for v in c.get("alturas_m", [])})
        resultado["nota_corrimaos"] = (
            f"Modelo tem {len(corrimaos)} IfcRailing. Alturas encontradas nos Psets: {alturas_todas or 'nenhuma'}. "
            f"Nenhum elemento apresentou as duas alturas normativas (0,70m e 0,92m) simultaneamente."
        )

    # ── 5. ESPAÇOS (6.11.1, 7.5) — análise geométrica real ───────────────────
    espacos = []
    n_spaces = contar("IfcSpace")

    if n_spaces > 0:
        try:
            import ifcopenshell.geom
            import numpy as np
            from shapely.geometry import MultiPoint, Point

            geom_settings = ifcopenshell.geom.settings()
            geom_settings.set(geom_settings.USE_WORLD_COORDS, True)

            R_GIRO = 0.75  # raio da área de manobra NBR 9050 item 7.5

            TERMOS_CORREDOR = ["corredor", "circulação", "circulacao", "hall",
                               "acesso", "passagem", "lobby", "foyer", "vestíbulo"]
            TERMOS_SANITARIO = ["banheiro", "sanitário", "sanitario", "wc",
                                "lavabo", "toalete", "vestiário", "vestiario",
                                "banho", "bath", "toilet"]
            TERMOS_ACESSIVEL_SPACE = ["pne", "pcd"]

            for el in ifc.by_type("IfcSpace"):
                d = info_basica(el, "IfcSpace")
                d["LongName"] = getattr(el, "LongName", None)
                ps = todos_psets(el)
                d["Psets"] = ps
                d["Area_m2"] = buscar_prop(ps, "area", "grossarea", "netarea")

                nome_completo = ((d.get("Name") or "") + " " + (d.get("LongName") or "")).lower()
                eh_sanitario_generico = any(t in nome_completo for t in TERMOS_SANITARIO)
                eh_acessivel = any(t in nome_completo for t in TERMOS_ACESSIVEL_SPACE)
                d["tipo_ambiente"] = (
                    "corredor" if any(t in nome_completo for t in TERMOS_CORREDOR)
                    # Só marca como "sanitario" (analisado no item 7.5 — giro 1,50m) se tiver
                    # PNE/PCD no nome. Banheiro comum sem essa tag vira "sanitario_nao_pne"
                    # e fica de fora da verificação de giro/transferência lateral.
                    else "sanitario" if (eh_sanitario_generico and eh_acessivel)
                    else "sanitario_nao_pne" if eh_sanitario_generico
                    else "outro"
                )

                # ── Análise geométrica com ifcopenshell.geom + Shapely ──
                try:
                    shape = ifcopenshell.geom.create_shape(geom_settings, el)
                    verts = np.array(shape.geometry.verts).reshape(-1, 3)
                    z_min = verts[:, 2].min()

                    # Pontos do piso (tolerância 2cm)
                    floor_pts = verts[np.abs(verts[:, 2] - z_min) < 0.02]

                    if len(floor_pts) >= 3:
                        hull = MultiPoint(floor_pts[:, :2]).convex_hull
                        area_geom = round(hull.area, 3)
                        d["area_geometrica_m2"] = area_geom

                        # Bounding box para estimativa de largura (corredores)
                        minx, miny, maxx, maxy = hull.bounds
                        largura_bb  = round(min(maxx - minx, maxy - miny), 3)
                        comprimento_bb = round(max(maxx - minx, maxy - miny), 3)
                        d["largura_estimada_m"]    = largura_bb
                        d["comprimento_estimado_m"] = comprimento_bb

                        # Teste de giro ⌀ 1,50m (NBR 9050 item 7.5)
                        cx, cy = hull.centroid.x, hull.centroid.y
                        circle_centro = Point(cx, cy).buffer(R_GIRO, resolution=64)

                        if hull.contains(circle_centro):
                            d["giro_150_conforme"] = True
                            d["giro_150_status"]   = "Conforme"
                            d["giro_150_nota"]     = f"Círculo ⌀1,50m contido no polígono do ambiente (centróide)"
                        else:
                            # Tenta outras posições (canto, deslocado)
                            encontrou = False
                            for dx, dy in [(0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3),
                                           (0.5, 0.5), (-0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)]:
                                circle_alt = Point(cx + dx, cy + dy).buffer(R_GIRO, resolution=64)
                                if hull.contains(circle_alt):
                                    encontrou = True
                                    d["giro_150_conforme"] = True
                                    d["giro_150_status"]   = "Conforme"
                                    d["giro_150_nota"]     = f"Círculo ⌀1,50m contido (posição deslocada {dx},{dy}m do centróide)"
                                    break
                            if not encontrou:
                                d["giro_150_conforme"] = False
                                d["giro_150_status"]   = "Não Conforme"
                                d["giro_150_nota"]     = (
                                    f"Círculo ⌀1,50m NÃO cabe no polígono do ambiente. "
                                    f"Área={area_geom:.2f}m² | Largura≈{largura_bb:.2f}m. "
                                    f"Mín. necessário: ⌀1,50m livre de obstruções."
                                )
                    else:
                        d["giro_150_status"] = "Indeterminado"
                        d["giro_150_nota"]   = "Geometria insuficiente para análise"

                except Exception as e_geom:
                    d["giro_150_status"] = "Indeterminado"
                    d["giro_150_nota"]   = f"Erro na extração geométrica: {str(e_geom)[:80]}"

                espacos.append(d)

        except ImportError:
            # Shapely ou ifcopenshell.geom não disponível — fallback básico
            for el in ifc.by_type("IfcSpace"):
                d = info_basica(el, "IfcSpace")
                d["LongName"] = getattr(el, "LongName", None)
                ps = todos_psets(el)
                d["Psets"] = ps
                d["Area_m2"] = buscar_prop(ps, "area", "grossarea", "netarea")
                d["giro_150_status"] = "Indeterminado"
                d["giro_150_nota"]   = "Shapely não disponível — instale: pip install shapely"
                espacos.append(d)

    resultado["elementos"]["IfcSpace"] = espacos[:40]
    resultado["nota_espacos"] = (
        f"Modelo tem {n_spaces} IfcSpace. "
        + (f"Analisados geometricamente: {len(espacos)} espaços com teste de giro ⌀1,50m via Shapely."
           if n_spaces > 0
           else "AUSENTE: não é possível verificar largura de corredores (6.11.1) nem giro de cadeira (7.5) sem IfcSpace. "
                "Recomenda-se exportar Rooms do Revit como IfcSpace com opção 'Export Rooms as IfcSpace'.")
    )

    # ── 6. SANITÁRIOS — classificados por tipo (7.7.2.1, 7.7.1, 7.8, 7.6-7.8) ─
    # IfcFlowTerminal no Revit IFC2X3 contém TUDO: bacias, lavatórios, barras, torneiras
    # Classificação pelo Name (em português, com marca Deca/Celite/Bobrick)

    def get_z_placement(el):
        """
        Extrai coordenada Z RELATIVA ao pavimento — proxy da altura de instalação.
        
        Problema: projetos em coordenadas compartilhadas têm Z global ~700m+.
        Solução: pega só o Z do nível IMEDIATO (RelativePlacement direto),
        ignorando os níveis superiores (pavimento, edifício, terreno).
        Valores plausíveis para equipamentos sanitários: 0.01m a 2.50m.
        """
        try:
            placement = el.ObjectPlacement
            # Pega apenas o placement imediato (relativo ao pavimento)
            if hasattr(placement, "RelativePlacement"):
                rp = placement.RelativePlacement
                if hasattr(rp, "Location") and rp.Location:
                    coords = rp.Location.Coordinates
                    if coords and len(coords) >= 3:
                        z = float(coords[2])
                        # Filtra: só valores plausíveis para altura de equipamento
                        # (entre 1cm e 2,50m — exclui coordenadas globais absurdas)
                        if 0.01 <= z <= 2.50:
                            return round(z, 3)
        except Exception:
            pass
        return None

    TERMOS_BACIA    = ["bacia", "vaso", "toilet", "wc", "p.505", "vogue plus p", "caixa acoplada"]
    TERMOS_LAVAT    = [
        "lavatório", "lavatorio", "lavat",
        "cuba",          # cuba embutir, cuba semiencaixe → sem coluna → Conforme
        "embutir",       # cuba retang. embutir → sem coluna
        "semiencaixe",   # cuba-de-semiencaixe → sem coluna
        "pia", "sink", "basin",
        "l.510", "l.830", "l.733",
    ]
    TERMOS_BARRA    = ["barra apoio", "grab bar", "barra de apoio", "2310.", "2335.", "apoio", "barra "]
    TERMOS_CHUVEIRO = ["chuveiro", "ducha", "shower", "1955", "registro"]

    bacias    = []
    lavatórios = []
    barras    = []
    outros_san = []
    excluidos_sem_pne = []  # fixtures que casaram categoria mas não têm tag PNE/PCD — não entram na auditoria

    for el in ifc.by_type("IfcFlowTerminal"):
        nome  = (getattr(el, "Name", "") or "").lower()
        otype = (getattr(el, "ObjectType", "") or "").lower()
        texto = nome + " " + otype

        d = info_basica(el, "IfcFlowTerminal")
        ps = todos_psets(el)
        d["Psets"] = ps

        # MountingHeight via Psets
        mh = buscar_prop(ps, "mountingheight", "mounting", "instalacao", "installation")
        d["MountingHeight_m"] = mh

        # Z do placement como fallback de altura
        z = get_z_placement(el)
        if z:
            d["Z_placement_m"] = z
            if not mh:
                d["altura_estimada_m"] = z  # proxy para o LLM usar

        pne_ok, pne_fonte = eh_acessivel_pne(el, texto)
        d["pne_pcd_confirmado"] = pne_ok
        if pne_fonte:
            d["pne_pcd_fonte"] = pne_fonte

        if any(t in texto for t in TERMOS_BACIA):
            d["categoria_sanitario"] = "bacia_sanitaria"
            (bacias if pne_ok else excluidos_sem_pne).append(d)
        elif any(t in texto for t in TERMOS_LAVAT):
            d["categoria_sanitario"] = "lavatorio"
            (lavatórios if pne_ok else excluidos_sem_pne).append(d)
        elif any(t in texto for t in TERMOS_BARRA):
            d["categoria_sanitario"] = "barra_apoio"
            (barras if pne_ok else excluidos_sem_pne).append(d)
        elif any(t in texto for t in TERMOS_CHUVEIRO):
            d["categoria_sanitario"] = "chuveiro"
            outros_san.append(d)  # chuveiros/outros não entram no filtro PNE (fora do escopo dos itens 7.x aqui)
        else:
            d["categoria_sanitario"] = "outros"
            outros_san.append(d)

    resultado["elementos"]["Bacias"]    = bacias[:20]
    resultado["elementos"]["Lavatorios"] = lavatórios[:20]
    resultado["elementos"]["BarrasApoio"] = barras[:20]
    resultado["elementos"]["OutrosSanitarios"] = outros_san[:10]
    resultado["nota_sanitarios"] = (
        f"IfcFlowTerminal classificados E marcados como PNE/PCD (analisados nos itens 7.x): "
        f"{len(bacias)} bacias, {len(lavatórios)} lavatórios, {len(barras)} barras de apoio. "
        f"Outros elementos (chuveiros, torneiras, dispensers): {len(outros_san)}. "
        f"Total IfcFlowTerminal no modelo: {contar('IfcFlowTerminal')}. "
        + (
            f"⚠️ {len(excluidos_sem_pne)} bacia(s)/lavatório(s)/barra(s) foram encontrados mas EXCLUÍDOS "
            f"da auditoria por não terem 'PNE' ou 'PCD' no nome (nem no espaço IfcSpace continente) — "
            f"portanto não foram tratados como sanitário acessível. Se isso for inesperado, confira a "
            f"nomenclatura das famílias no Revit (ex: renomear para 'Bacia PNE', 'WC Acessível PCD')."
            if excluidos_sem_pne else
            "Nenhum elemento foi excluído por falta de tag PNE/PCD."
        )
    )

    # ── 7. JANELAS (6.11.3) ──────────────────────────────────────────────────
    janelas = []
    for el in ifc.by_type("IfcWindow"):
        d = info_basica(el, "IfcWindow")
        oh = getattr(el, "OverallHeight", None)
        ow = getattr(el, "OverallWidth", None)
        d["OverallHeight_m"] = round(float(oh), 3) if oh else None
        d["OverallWidth_m"]  = round(float(ow), 3) if ow else None
        ps = todos_psets(el)
        d["Psets"] = ps
        d["SillHeight_m"] = buscar_prop(ps, "sill", "peitoril", "sillheight")
        janelas.append(d)
    resultado["elementos"]["IfcWindow"] = janelas[:40]

    # ── 8. PISOS (6.3.4) ─────────────────────────────────────────────────────
    pisos = []
    for el in ifc.by_type("IfcSlab"):
        nome = (getattr(el, "Name", "") or "").lower()
        otype = (getattr(el, "ObjectType", "") or "").lower()
        if any(t in nome + otype for t in ["rampa", "ramp"]):
            continue
        d = info_basica(el, "IfcSlab")
        ps = todos_psets(el)
        d["Psets"] = ps
        d["Elevation_m"] = buscar_prop(ps, "elevation", "cota", "level")
        pisos.append(d)
    resultado["elementos"]["IfcSlab"] = pisos[:25]

    # ── 9. PAREDES — amostra (fallback para corredores) ───────────────────────
    paredes = []
    for el in list(ifc.by_type("IfcWall"))[:8] + list(ifc.by_type("IfcWallStandardCase"))[:8]:
        d = info_basica(el, el.is_a())
        ps = todos_psets(el)
        d["Width_m"]  = buscar_prop(ps, "width", "thickness", "espessura")
        d["Length_m"] = buscar_prop(ps, "length", "comprimento")
        d["Height_m"] = buscar_prop(ps, "height", "altura")
        paredes.append(d)
    resultado["elementos"]["IfcWall_amostra"] = paredes

    return limpar_nulos(resultado)
