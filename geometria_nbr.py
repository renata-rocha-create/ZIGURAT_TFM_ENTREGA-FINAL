"""
geometria_nbr.py — Análises geométricas puras (só numpy) usadas pela extração.

Por que um módulo separado?
  As funções aqui recebem apenas VÉRTICES (arrays N×3 em metros, coordenadas do
  mundo) — não dependem do ifcopenshell. Isso permite testá-las com dados reais
  do IFC sem abrir o modelo, e mantém o extracao.py focado em LER o IFC.

  Analogia: o extracao.py é o topógrafo que vai a campo e traz a caderneta de
  pontos; este módulo é o escritório que faz as contas com esses pontos.

Funções principais:
  analisar_laje()          → topo da laje, inclinação (%), desnível, comprimento  (6.6)
  poligono_planta()        → contorno em planta (casco convexo) de um sólido
  ambientes_da_porta()     → quais ambientes a porta conecta                    (4.6.6)
  desniveis_entre_lajes()  → diferença de cota entre pisos vizinhos            (6.3.4)
  corrimaos_da_rampa()     → corrimãos junto à rampa: lados e alturas          (5.4.3)
"""
import numpy as np

# ══════════════════════════════════════════════════════════════════════════════
# Geometria 2D básica
# ══════════════════════════════════════════════════════════════════════════════

def casco_convexo(xy):
    """
    Casco convexo 2D (algoritmo "monotone chain").
    Analogia: é o elástico esticado em volta de todos os pontos da planta.
    Devolve os vértices em sentido anti-horário, sem repetir o primeiro.
    """
    pts = sorted(set(map(tuple, np.round(np.asarray(xy, dtype=float)[:, :2], 6))))
    if len(pts) <= 2:
        return np.array(pts)

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    inf, sup = [], []
    for p in pts:
        while len(inf) >= 2 and cruz(inf[-2], inf[-1], p) <= 0:
            inf.pop()
        inf.append(p)
    for p in reversed(pts):
        while len(sup) >= 2 and cruz(sup[-2], sup[-1], p) <= 0:
            sup.pop()
        sup.append(p)
    return np.array(inf[:-1] + sup[:-1])


def ponto_no_poligono(p, poly):
    """Teste do raio (ray casting): conta quantas arestas um raio horizontal cruza."""
    x, y = p
    dentro = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xc:
                dentro = not dentro
    return dentro


def _dist_ponto_segmento(p, a, b):
    p, a, b = map(lambda v: np.asarray(v, dtype=float), (p, a, b))
    ab = b - a
    t = 0.0 if not ab.any() else float(np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0, 1))
    return float(np.linalg.norm(p - (a + t * ab)))


def dist_ponto_poligono(p, poly):
    """0 se o ponto está dentro; senão, a menor distância até a borda."""
    if len(poly) >= 3 and ponto_no_poligono(p, poly):
        return 0.0
    n = len(poly)
    return min(_dist_ponto_segmento(p, poly[i], poly[(i + 1) % n]) for i in range(n))


def dist_poligonos(pa, pb):
    """Menor distância entre dois polígonos convexos (0 se encostam/sobrepõem)."""
    d = min(min(dist_ponto_poligono(p, pb) for p in pa),
            min(dist_ponto_poligono(p, pa) for p in pb))
    return d


def poligono_planta(verts, so_base=False, tol=0.02):
    """
    Contorno em planta de um sólido.
    so_base=True → usa só os pontos do piso (cota mínima), útil para IfcSpace.
    """
    v = np.asarray(verts, dtype=float).reshape(-1, 3)
    if so_base:
        v = v[np.abs(v[:, 2] - v[:, 2].min()) < tol]
    return casco_convexo(v[:, :2])


# ══════════════════════════════════════════════════════════════════════════════
# 6.6 — Lajes inclinadas (rampa modelada como IfcSlab)
# ══════════════════════════════════════════════════════════════════════════════

def analisar_laje(verts, passo=0.01):
    """
    Analisa o TOPO de uma laje e ajusta um plano z = a·x + b·y + c.

    Como funciona (analogia de levantamento topográfico):
      1. Para cada ponto em planta (x, y), fica só com a cota MAIS ALTA —
         é a "superfície de pisada". As cotas de baixo (fundo da laje,
         camadas de contrapiso) são descartadas. Isso elimina o erro de somar
         a espessura da laje ao desnível.
      2. Ajusta um plano por mínimos quadrados nesses pontos de topo.
      3. Inclinação = |gradiente do plano| = √(a² + b²).

    Devolve dict com:
      inclinacao_pct, desnivel_m, comprimento_m, z_topo_min, z_topo_max,
      residuo_max_m (quão "plano" é o topo), planar (bool), direcao_subida (vetor xy)
    """
    v = np.asarray(verts, dtype=float).reshape(-1, 3)
    if len(v) < 3:
        return None

    chaves = np.round(v[:, :2] / passo).astype(np.int64)
    topo = {}
    for k, p in zip(map(tuple, chaves), v):
        if k not in topo or p[2] > topo[k][2]:
            topo[k] = p
    t = np.array(list(topo.values()))
    if len(t) < 3:
        return None

    A = np.c_[t[:, 0], t[:, 1], np.ones(len(t))]
    (a, b, c), *_ = np.linalg.lstsq(A, t[:, 2], rcond=None)
    residuo = float(np.abs(A @ np.array([a, b, c]) - t[:, 2]).max())
    grad = float(np.hypot(a, b))

    z_min, z_max = float(t[:, 2].min()), float(t[:, 2].max())
    desnivel = z_max - z_min
    comprimento = desnivel / grad if grad > 1e-6 else float(max(np.ptp(t[:, 0]), np.ptp(t[:, 1])))

    return {
        "inclinacao_pct": round(grad * 100, 2),
        "desnivel_m": round(desnivel, 3),
        "comprimento_m": round(comprimento, 3),
        "z_topo_min": round(z_min, 3) + 0.0,
        "z_topo_max": round(z_max, 3) + 0.0,
        "residuo_max_m": round(residuo, 4),
        "planar": residuo <= 0.01,
        "plano": (float(a), float(b), float(c)),
        "direcao_subida": (float(a / grad), float(b / grad)) if grad > 1e-6 else None,
        "poligono": casco_convexo(t[:, :2]),
    }


def cota_topo(info_laje, x, y):
    """Cota do topo da laje no ponto (x, y), pelo plano ajustado."""
    a, b, c = info_laje["plano"]
    return a * x + b * y + c


# ══════════════════════════════════════════════════════════════════════════════
# 4.6.6 — Quais ambientes uma porta conecta
# ══════════════════════════════════════════════════════════════════════════════

def sondas_porta(verts_porta, folga=0.15):   # mantida por compatibilidade
    """
    Dois pontos em planta, um de cada lado da porta.

    Analogia: é ficar no batente e dar um passo para cada lado.
    A caixa envolvente da porta tem um lado "fino" (espessura da parede) e um
    "largo" (largura do vão). Do centro, anda (meia espessura + folga) para
    cada lado ao longo do eixo fino.
    Devolve (sonda_1, sonda_2, centro).
    """
    v = np.asarray(verts_porta, dtype=float).reshape(-1, 3)
    xmin, ymin = v[:, 0].min(), v[:, 1].min()
    xmax, ymax = v[:, 0].max(), v[:, 1].max()
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    dx, dy = xmax - xmin, ymax - ymin
    if dx <= dy:   # parede corre em Y → lados da porta estão em ±X
        return (cx - dx / 2 - folga, cy), (cx + dx / 2 + folga, cy), (cx, cy)
    return (cx, cy - dy / 2 - folga), (cx, cy + dy / 2 + folga), (cx, cy)


def candidatos_sondas(verts_porta, folgas=(0.15, 0.30, 0.50)):
    """
    Pares de sondas em ordem de preferência: primeiro no eixo "fino" da
    caixa da porta (o certo quando a geometria é confiável), com passos
    crescentes; depois no outro eixo. Assim, se a caixa vier girada 90° (ex:
    porta com geometria mapeada interpretada diferente em outra versão do
    ifcopenshell), o par certo ainda é encontrado.
    """
    v = np.asarray(verts_porta, dtype=float).reshape(-1, 3)
    xmin, ymin = v[:, 0].min(), v[:, 1].min()
    xmax, ymax = v[:, 0].max(), v[:, 1].max()
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    dx, dy = xmax - xmin, ymax - ymin
    eixos = ["x", "y"] if dx <= dy else ["y", "x"]
    pares = []
    for eixo in eixos:
        for f in folgas:
            if eixo == "x":
                pares.append(((cx - dx / 2 - f, cy), (cx + dx / 2 + f, cy)))
            else:
                pares.append(((cx, cy - dy / 2 - f), (cx, cy + dy / 2 + f)))
    return pares, (cx, cy)


def ambientes_da_porta(verts_porta, poligonos, dist_max=0.30):
    """
    Descobre os ambientes dos DOIS lados de uma porta: testa pares de sondas
    (ver candidatos_sondas) e fica com o primeiro que cai em DOIS ambientes
    diferentes. Se nenhum par conseguir (porta para área externa), usa o melhor
    par encontrado + ambientes a até `dist_max` do centro da porta.

    poligonos: dict {chave: polígono xy}. Devolve lista de chaves.
    """
    pares, centro = candidatos_sondas(verts_porta)

    def _amb(p):
        for k, poly in poligonos.items():
            if len(poly) >= 3 and ponto_no_poligono(p, poly):
                return k
        return None

    melhor = []
    for s1, s2 in pares:
        a1, a2 = _amb(s1), _amb(s2)
        achados = [a for a in (a1, a2) if a is not None]
        achados = list(dict.fromkeys(achados))
        if len(achados) == 2:
            return achados
        if len(achados) > len(melhor):
            melhor = achados
    for k, poly in poligonos.items():
        if k not in melhor and len(poly) >= 3 and dist_ponto_poligono(centro, poly) <= dist_max:
            melhor.append(k)
    return melhor


# ══════════════════════════════════════════════════════════════════════════════
# 6.3.4 — Desníveis entre pisos vizinhos
# ══════════════════════════════════════════════════════════════════════════════

def triangulos_topo(verts, faces, nz_min=0.5):
    """
    Triângulos da malha com a face voltada PARA CIMA (normal com z > nz_min).
    São exatamente a superfície onde se pisa — funciona para lajes com
    várias "ilhas" (ex: um IfcSlab cobrindo ACESSO e PORTARIA) e para lajes
    inclinadas, onde um contorno único (casco convexo) erraria.
    faces: lista plana de índices (como shape.geometry.faces do ifcopenshell).
    Devolve array (M, 3, 3).
    """
    v = np.asarray(verts, dtype=float).reshape(-1, 3)
    f = np.asarray(faces, dtype=int).reshape(-1, 3)
    if not len(f):
        return np.zeros((0, 3, 3))
    t = v[f]
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    norma = np.linalg.norm(n, axis=1)
    ok = norma > 1e-12
    nz = np.zeros(len(t))
    nz[ok] = n[ok, 2] / norma[ok]
    return t[nz > nz_min]


def cota_no_ponto(tris, x, y, tol=1e-6):
    """
    Cota do piso no ponto (x, y): procura o triângulo de topo que contém o
    ponto e interpola a cota (coordenadas baricêntricas). Se houver mais de
    uma laje sobreposta (estrutural + acabamento), fica com a MAIS ALTA,
    que é o piso acabado. None se o ponto não está sobre nenhum triângulo.
    """
    melhor = None
    for t in tris:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = t
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(det) < 1e-12:
            continue
        l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det
        l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det
        l3 = 1 - l1 - l2
        if l1 >= -tol and l2 >= -tol and l3 >= -tol:
            z = l1 * z1 + l2 * z2 + l3 * z3
            melhor = z if melhor is None else max(melhor, z)
    return melhor


def desnivel_na_porta(verts_porta, lajes_tris):
    """
    Desnível de piso ATRAVÉS de uma porta (6.3.4): lê a cota do piso acabado
    um passo antes e um passo depois do vão. Testa os pares de sondas de
    candidatos_sondas() e usa o primeiro com piso dos DOIS lados.
    lajes_tris: lista de arrays de triângulos de topo (uma por laje).
    Devolve dict {"z_1", "z_2", "desnivel_mm", "sondas"}; desnivel_mm=None
    se nenhum par encontrou piso dos dois lados.
    """
    def _z(p):
        zs = [cota_no_ponto(t, *p) for t in lajes_tris]
        zs = [z for z in zs if z is not None]
        return max(zs) if zs else None

    pares, _ = candidatos_sondas(verts_porta)
    parcial = None
    for s1, s2 in pares:
        z1, z2 = _z(s1), _z(s2)
        sondas = [[round(float(c), 3) for c in s] for s in (s1, s2)]
        if z1 is not None and z2 is not None:
            return {"z_1": round(float(z1), 4) + 0.0, "z_2": round(float(z2), 4) + 0.0,
                    "desnivel_mm": round(abs(float(z1) - float(z2)) * 1000, 1), "sondas": sondas}
        if parcial is None:
            parcial = {"z_1": None if z1 is None else round(float(z1), 4),
                       "z_2": None if z2 is None else round(float(z2), 4),
                       "desnivel_mm": None, "sondas": sondas}
    return parcial


def _partes_planta(verts, passo=0.01):
    """
    Uma laje do Revit pode ter várias "ilhas" (ex: um mesmo tipo de piso no
    ACESSO e na PORTARIA). Separa os pontos de topo em grupos conectados para
    não tratar duas salas como um polígono único.
    """
    v = np.asarray(verts, dtype=float).reshape(-1, 3)
    chaves = np.round(v[:, :2] / passo).astype(np.int64)
    topo = {}
    for k, p in zip(map(tuple, chaves), v):
        if k not in topo or p[2] > topo[k][2]:
            topo[k] = p
    return np.array(list(topo.values()))


def desniveis_entre_lajes(lajes, dist_max=0.05):
    """
    Compara a cota do topo de lajes que ENCOSTAM uma na outra (a até
    `dist_max` em planta) — juntas de piso contínuo sem porta, como o topo de
    uma rampa chegando no piso do ACESSO. Lajes separadas por parede (≈0,15–
    0,25 m) ficam de fora: essas passagens são medidas nas portas.

    lajes: lista de dicts {"id", "nome", "verts"}
    Para cada par vizinho, mede a diferença de cota NOS PONTOS MAIS PRÓXIMOS
    entre os dois (importante quando uma delas é inclinada, como a rampa: o que
    vale é a cota na junta, não a média da laje).

    Devolve lista de dicts:
      {"a", "b", "nome_a", "nome_b", "z_a", "z_b", "desnivel_mm", "distancia_m"}
    """
    infos = []
    for l in lajes:
        inf = analisar_laje(l["verts"])
        if inf is None:
            continue
        infos.append((l, inf, _partes_planta(l["verts"])))

    pares = []
    for i in range(len(infos)):
        for j in range(i + 1, len(infos)):
            (la, ia, ta), (lb, ib, tb) = infos[i], infos[j]
            if dist_poligonos(ia["poligono"], ib["poligono"]) > dist_max:
                continue
            # pares de pontos de topo mais próximos entre as duas lajes
            d2 = ((ta[:, None, :2] - tb[None, :, :2]) ** 2).sum(-1)
            k = np.unravel_index(np.argmin(d2), d2.shape)
            pa, pb = ta[k[0]], tb[k[1]]
            dist = float(np.sqrt(d2[k]))
            if dist > dist_max:
                continue
            # cota de cada laje no ponto médio da junta
            mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
            za = cota_topo(ia, mx, my) if not ia["planar"] or ia["inclinacao_pct"] > 0.5 else ia["z_topo_max"]
            zb = cota_topo(ib, mx, my) if not ib["planar"] or ib["inclinacao_pct"] > 0.5 else ib["z_topo_max"]
            pares.append({
                "a": la["id"], "b": lb["id"],
                "nome_a": la.get("nome"), "nome_b": lb.get("nome"),
                "z_a": round(float(za), 4) + 0.0, "z_b": round(float(zb), 4) + 0.0,
                "desnivel_mm": round(abs(float(za) - float(zb)) * 1000, 1),
                "distancia_m": round(dist, 3),
                "junta_xy": (round(float(mx), 3), round(float(my), 3)),
            })
    return pares


# ══════════════════════════════════════════════════════════════════════════════
# 5.4.3 — Corrimãos junto a uma rampa
# ══════════════════════════════════════════════════════════════════════════════

def corrimaos_da_rampa(info_rampa, corrimaos, dist_max=0.40, tol_alt=0.05):
    """
    Associa corrimãos (IfcRailing) a uma rampa e mede alturas em relação
    à SUPERFÍCIE da rampa (não ao pavimento).

    Analogia: a régua de altura do corrimão é encostada no piso da rampa
    logo abaixo dele — como a rampa sobe, a régua sobe junto.

    info_rampa: saída de analisar_laje() da rampa
    corrimaos:  lista de dicts {"id", "nome", "verts"}

    Para cada corrimão a até `dist_max` da rampa em planta:
      lado          → "esquerdo"/"direito" em relação ao sentido de subida
      altura_topo_m → altura máxima acima da superfície (mediana ao longo da rampa)
      alturas_m     → níveis horizontais detectados (tubos do corrimão)
      tem_070 / tem_092
    """
    if info_rampa is None or info_rampa.get("direcao_subida") is None:
        return []
    poly = info_rampa["poligono"]
    ux, uy = info_rampa["direcao_subida"]
    nx, ny = -uy, ux                       # perpendicular (lado esquerdo de quem sobe)
    cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
    proj_long = (poly[:, 0] - cx) * ux + (poly[:, 1] - cy) * uy
    lmin, lmax = proj_long.min(), proj_long.max()

    saida = []
    for c in corrimaos:
        v = np.asarray(c["verts"], dtype=float).reshape(-1, 3)
        if not len(v):
            continue
        pc = casco_convexo(v[:, :2])
        if len(pc) < 3 or dist_poligonos(pc, poly) > dist_max:
            continue
        # só pontos ao longo do comprimento da rampa
        long_v = (v[:, 0] - cx) * ux + (v[:, 1] - cy) * uy
        sel = v[(long_v >= lmin) & (long_v <= lmax)]
        if not len(sel):
            continue
        rel = sel[:, 2] - np.array([cota_topo(info_rampa, x, y) for x, y in sel[:, :2]])
        lateral = float(np.median((sel[:, 0] - cx) * nx + (sel[:, 1] - cy) * ny))

        # Divide o comprimento da rampa em 8 trechos e DESCARTA o primeiro e o
        # último: nas pontas ficam postes, terminais e prolongamentos do
        # corrimão, que distorcem a altura. Mede só o "miolo" da rampa.
        ls = (sel[:, 0] - cx) * ux + (sel[:, 1] - cy) * uy
        cortes = np.linspace(lmin, lmax, 9)
        miolo = (ls >= cortes[1]) & (ls <= cortes[7])
        if miolo.sum() < 5:
            miolo = np.ones(len(rel), dtype=bool)
        rel_m, ls_m = rel[miolo], ls[miolo]

        # Paralelismo: topo do corrimão em cada trecho interno. Se ele acompanha
        # a rampa, o topo fica constante; se foi modelado "reto" (horizontal),
        # o topo varia junto com o desnível da rampa.
        topos = [float(rel_m[(ls_m >= cortes[i]) & (ls_m <= cortes[i + 1])].max())
                 for i in range(1, 7) if ((ls_m >= cortes[i]) & (ls_m <= cortes[i + 1])).any()]
        variacao = round(float(np.ptp(topos)), 3) if len(topos) >= 2 else 0.0
        topo = round(float(np.median(topos)), 3) if topos else round(float(rel_m.max()), 3)

        # Níveis horizontais (tubos): histograma de alturas relativas (passo 2 cm);
        # cada tubo gera um "pico" com muitos vértices na mesma altura.
        hist, bordas = np.histogram(rel_m, bins=np.arange(0, max(rel_m.max(), 0.1) + 0.02, 0.02))
        picos = [round(float((bordas[i] + bordas[i + 1]) / 2), 2)
                 for i in range(len(hist)) if hist[i] >= max(0.08 * len(rel_m), 5)]
        alturas = sorted(set(picos))

        saida.append({
            "id": c["id"], "nome": c.get("nome"),
            "lado": "esquerdo" if lateral > 0 else "direito",
            "altura_topo_m": topo,
            "variacao_altura_m": variacao,
            "paralelo_a_rampa": variacao <= 0.03,
            "alturas_m": alturas,
            "tem_070": any(abs(h - 0.70) <= tol_alt for h in alturas + [topo]),
            "tem_092": any(abs(h - 0.92) <= tol_alt for h in alturas + [topo]),
        })
    return saida
