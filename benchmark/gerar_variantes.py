"""
gerar_variantes.py — Gera o benchmark de IFCs com ERROS INJETADOS e o GABARITO.

Ideia (injeção controlada de erros / "fault injection"):
  parte-se de um modelo 100% conforme (BENCHMARK_00_3.ifc) e cria-se uma
  variante por erro, alterando por script UM aspecto conhecido do modelo.
  O gabarito (status esperado de cada um dos 12 itens em cada variante) é
  gravado ANTES de o auditor rodar — como corrigir uma prova com o
  gabarito já impresso, e não escrito depois de ver as respostas.

Uso:
    python gerar_variantes.py --base BENCHMARK_00_3.ifc [--real-corrimao BENCHMARK_00_2.ifc]
Saída (na pasta deste script):
    variantes/*.ifc   — um arquivo por variante
    gabarito.csv      — variante × item NBR → status esperado (+ alteração aplicada)

Só usa a API básica do ifcopenshell (sem ifcopenshell.api) para rodar em
qualquer instalação.
"""
import argparse
import csv
import sys
import math
import shutil
from datetime import datetime
from pathlib import Path

import ifcopenshell

# Terminal do Windows: aceitar acentos e setas nas mensagens sem travar
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


AQUI = Path(__file__).resolve().parent

# ── Identificadores no BENCHMARK_00_3 ───────────────────────────────────────
GID = {
    "porta_pcd": "2iZFzhqZj33PazahJbF3OE",
    "porta_lisa": "2iZFzhqZj33PazahJbF5PL",
    "janela_fixa": "2iZFzhqZj33PazahJbF5vk",
    "rampa": "2iZFzhqZj33PazahJbF16Y",
    "laje_wc": "2iZFzhqZj33PazahJbFLSU",
    "corrimao_vidro": "2iZFzhqZj33PazahJbF49C",
    "corrimao_parede": "2iZFzhqZj33PazahJbF4h7",
    "bacia": "2iZFzhqZj33PazahJbFLSv",
    "barra_fundo": "2iZFzhqZj33PazahJbFLVd",
    "barra_lateral": "2iZFzhqZj33PazahJbFLVc",
    "barra_vertical": "2iZFzhqZj33PazahJbFLVb",
    "barra_lav_1": "2iZFzhqZj33PazahJbFLS0",
    "barra_lav_2": "2iZFzhqZj33PazahJbF0gn",
    "lavatorio_1": "2iZFzhqZj33PazahJbFLSG",
    "lavatorio_2": "2iZFzhqZj33PazahJbFLSu",
    "esp_wc": "2iZFzhqZj33PazahJbF0hQ",
    "esp_acesso": "2Cd7r7klL5F8t2OHHoqOv$",
}

ITENS = ["6.6", "6.11.1", "6.11.2", "6.11.3", "5.4.3", "6.3.4",
         "7.5", "7.7.2.1", "7.7.1", "4.6.6", "7.6-7.8", "7.8"]


# ══════════════════════════════════════════════════════════════════════════════
# Utilitários de edição (sem numpy)
# ══════════════════════════════════════════════════════════════════════════════

def _usos(f, ent):
    return len(f.get_inverse(ent))


def _novo_ponto(f, coords):
    return f.createIfcCartesianPoint(tuple(float(c) for c in coords))


def mover_elemento_z(f, el, dz):
    """Sobe/desce um elemento pela sua IfcLocalPlacement (sem tocar em pontos compartilhados)."""
    rp = el.ObjectPlacement.RelativePlacement
    x, y, z = (list(rp.Location.Coordinates) + [0.0, 0.0, 0.0])[:3]
    rp.Location = _novo_ponto(f, (x, y, z + dz))


def mover_extrusoes_z(f, el, dz):
    """Desloca em Z todas as extrusões da representação Body (lajes com origem compartilhada)."""
    for rep in el.Representation.Representations:
        if rep.RepresentationIdentifier != "Body":
            continue
        for it in rep.Items:
            pos = it.Position
            x, y, z = (list(pos.Location.Coordinates) + [0.0, 0.0, 0.0])[:3]
            if _usos(f, pos) > 1:
                pos = f.createIfcAxis2Placement3D(pos.Location, pos.Axis, pos.RefDirection)
                it.Position = pos
            pos.Location = _novo_ponto(f, (x, y, z + dz))


def definir_prop(f, el_ou_tipo, nome_prop, tipo_valor, valor, nos_tipos=False):
    """Altera o valor de uma propriedade de Pset (da instância ou do tipo)."""
    alvos = []
    if nos_tipos:
        for rel in getattr(el_ou_tipo, "IsTypedBy", None) or []:
            for ps in rel.RelatingType.HasPropertySets or []:
                alvos.append(ps)
    else:
        for rel in el_ou_tipo.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                alvos.append(rel.RelatingPropertyDefinition)
    n = 0
    for ps in alvos:
        for p in getattr(ps, "HasProperties", None) or []:
            if p.Name == nome_prop:
                p.NominalValue = f.create_entity(tipo_valor, valor)
                n += 1
    if n == 0:
        raise RuntimeError(f"propriedade '{nome_prop}' não encontrada")


def _matriz(pos):
    """Axis2Placement3D → (origem, X, Y, Z) em listas Python."""
    o = list(pos.Location.Coordinates)
    z = list(pos.Axis.DirectionRatios) if pos.Axis else [0.0, 0.0, 1.0]
    x = list(pos.RefDirection.DirectionRatios) if pos.RefDirection else [1.0, 0.0, 0.0]
    nz = math.sqrt(sum(c * c for c in z)); z = [c / nz for c in z]
    d = sum(x[i] * z[i] for i in range(3)); x = [x[i] - d * z[i] for i in range(3)]
    nx = math.sqrt(sum(c * c for c in x)); x = [c / nx for c in x]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return o, x, y, z


def inclinar_rampa(f, rampa, inclinacao):
    """
    Mantém a cota do TOPO da rampa (junta com o piso do ACESSO) e o
    comprimento; rebaixa a extremidade inferior até atingir o novo desnível.
    Trabalha nas extrusões cujo perfil está num plano vertical (laje
    inclinada do Revit): converte os pontos do perfil para coordenadas do
    mundo, desloca Z proporcionalmente à posição ao longo da rampa e volta.
    inclinacao: fração (ex.: 0.10 = 10%), aplicada ao comprimento medido em planta.
    Devolve (y_baixo, y_topo, delta_desnivel) para inclinar os corrimãos junto.
    """
    pts_mundo = []
    itens = []
    for rep in rampa.Representation.Representations:
        if rep.RepresentationIdentifier != "Body":
            continue
        for it in rep.Items:
            o, X, Y, Z = _matriz(it.Position)
            lista = it.SweptArea.OuterCurve.Points
            coords = [list(c) for c in lista.CoordList]
            mundo = [[o[k] + u * X[k] + v * Y[k] for k in range(3)] for u, v in coords]
            itens.append((it, lista, o, X, Y, mundo))
            pts_mundo += mundo
    y_baixo = min(p[1] for p in pts_mundo)
    y_topo = max(p[1] for p in pts_mundo)
    comp = y_topo - y_baixo
    # topo da superfície: maior Z em cada extremidade
    z_topo_alto = max(p[2] for p in pts_mundo if abs(p[1] - y_topo) < 1e-3)
    z_topo_baixo = max(p[2] for p in pts_mundo if abs(p[1] - y_baixo) < 1e-3)
    desnivel_antigo = z_topo_alto - z_topo_baixo
    novo_desnivel = inclinacao * comp
    delta = novo_desnivel - desnivel_antigo
    for it, lista, o, X, Y, mundo in itens:
        novos = []
        for p in mundo:
            frac = (y_topo - p[1]) / comp          # 0 no topo, 1 na base
            p2 = [p[0], p[1], p[2] - delta * frac]
            d = [p2[k] - o[k] for k in range(3)]
            novos.append((sum(d[k] * X[k] for k in range(3)), sum(d[k] * Y[k] for k in range(3))))
        if _usos(f, lista) > 1:
            nova = f.createIfcCartesianPointList2D(tuple(novos))
            it.SweptArea.OuterCurve.Points = nova
        else:
            lista.CoordList = tuple(novos)
    return y_baixo, y_topo, delta


def inclinar_corrimao(f, el, y_baixo, y_topo, delta_desnivel):
    """
    Cisalha a geometria tesselada do corrimão para acompanhar a nova
    inclinação: Z desce (delta · fração do comprimento) ao longo da rampa;
    trechos além das extremidades acompanham a extremidade mais próxima.
    O placement do corrimão não tem rotação (só translação) — conferido.
    """
    oz = el.ObjectPlacement.RelativePlacement.Location.Coordinates
    oy = oz[1]
    comp = y_topo - y_baixo
    vistos = set()
    for rep in el.Representation.Representations:
        if rep.RepresentationIdentifier != "Body":
            continue
        for it in rep.Items:
            lista = it.Coordinates
            if lista.id() in vistos:
                continue
            vistos.add(lista.id())
            novos = []
            for x, y, z in lista.CoordList:
                yw = oy + y
                frac = min(1.0, max(0.0, (y_topo - yw) / comp))
                novos.append((x, y, z - delta_desnivel * frac))
            lista.CoordList = tuple(novos)


def editar_perfil_espaco(f, espaco, fn):
    """Aplica fn(x, y) → (x, y) aos pontos do perfil em planta do IfcSpace."""
    for rep in espaco.Representation.Representations:
        for it in rep.Items:
            if not it.is_a("IfcExtrudedAreaSolid"):
                continue
            lista = it.SweptArea.OuterCurve.Points
            novos = tuple(fn(x, y) for x, y in lista.CoordList)
            if _usos(f, lista) > 1:
                it.SweptArea.OuterCurve.Points = f.createIfcCartesianPointList2D(novos)
            else:
                lista.CoordList = novos


# ══════════════════════════════════════════════════════════════════════════════
# Mutações (cada uma recebe o arquivo aberto e altera UMA coisa)
# ══════════════════════════════════════════════════════════════════════════════

def m_largura_porta(v):
    def _m(f):
        f.by_guid(GID["porta_pcd"]).OverallWidth = v
    return _m


def m_altura_porta_lisa(v):
    def _m(f):
        f.by_guid(GID["porta_lisa"]).OverallHeight = v
    return _m


def m_peitoril(v):
    def _m(f):
        definir_prop(f, f.by_guid(GID["janela_fixa"]), "Sill Height", "IfcLengthMeasure", v)
    return _m


def m_rampa(inclinacao_pct):
    def _m(f):
        rampa = f.by_guid(GID["rampa"])
        y_b, y_t, delta = inclinar_rampa(f, rampa, inclinacao_pct / 100.0)
        for g in ("corrimao_vidro", "corrimao_parede"):
            try:
                inclinar_corrimao(f, f.by_guid(GID[g]), y_b, y_t, delta)
            except RuntimeError:
                pass  # corrimão removido por outra mutação (variante multi-erro)
    return _m


def m_remover_corrimao_parede(f):
    f.remove(f.by_guid(GID["corrimao_parede"]))


def m_baixar_corrimao_vidro(dz):
    def _m(f):
        mover_elemento_z(f, f.by_guid(GID["corrimao_vidro"]), -dz)
    return _m


def m_desnivel_wc(dz):
    """dz < 0 rebaixa o piso do WC (o ACESSO está +5 mm acima na base)."""
    def _m(f):
        mover_extrusoes_z(f, f.by_guid(GID["laje_wc"]), dz)
    return _m


def m_subir(chaves, dz):
    def _m(f):
        for k in chaves:
            mover_elemento_z(f, f.by_guid(GID[k]), dz)
    return _m


def m_ferragens(texto):
    def _m(f):
        definir_prop(f, f.by_guid(GID["porta_pcd"]), "Ferragens", "IfcText", texto, nos_tipos=True)
    return _m


def m_estreitar_wc(largura):
    """WC PNE: mantém a face sul (y=11,193) e puxa a face norte."""
    def _m(f):
        y_sul = 11.193156207621353
        y_novo = y_sul + largura
        editar_perfil_espaco(f, f.by_guid(GID["esp_wc"]),
                             lambda x, y: (x, y_novo if y > y_sul + 0.5 else y))
    return _m


def m_estreitar_acesso(largura):
    """ACESSO: mantém a face norte (y=10,993) e puxa a face sul."""
    def _m(f):
        y_norte = 10.99315620762136
        y_novo = y_norte - largura
        editar_perfil_espaco(f, f.by_guid(GID["esp_acesso"]),
                             lambda x, y: (x, y_novo if y < y_norte - 0.5 else y))
    return _m


def m_lavatorio_com_coluna(f):
    for k in ("lavatorio_1", "lavatorio_2"):
        el = f.by_guid(GID[k])
        el.Name = el.Name.replace("Suspenso", "com coluna")


def combinar(*ms):
    def _m(f):
        for m in ms:
            m(f)
    return _m


# ══════════════════════════════════════════════════════════════════════════════
# Catálogo de variantes + gabarito
# ══════════════════════════════════════════════════════════════════════════════
# Cada variante: id, nível, descrição, mutação, {item: status esperado}.
# Itens não listados → status da BASE (todos Conforme no BENCHMARK_00_3).
# "efeito" documenta interdependências normativas reais (não são falhas do teste).

BASE_ESPERADO = {i: "Conforme" for i in ITENS}

VARIANTES = [
    ("B00", "base", "Modelo-base sem alteração", None, {}, ""),
    # 6.11.2 portas
    ("P01", "grosseiro", "Porta PCD: largura 1,04 → 0,75 m", m_largura_porta(0.75), {"6.11.2": "Não Conforme"}, ""),
    ("P02", "limítrofe", "Porta PCD: largura 1,04 → 0,79 m", m_largura_porta(0.79), {"6.11.2": "Não Conforme"}, ""),
    ("P03", "quase-erro", "Porta PCD: largura 1,04 → 0,81 m", m_largura_porta(0.81), {}, ""),
    ("P04", "grosseiro", "Porta lisa: altura 2,15 → 2,05 m", m_altura_porta_lisa(2.05), {"6.11.2": "Não Conforme"}, ""),
    # 6.11.3 janelas
    ("J01", "grosseiro", "Janela fixa: peitoril 1,20 → 1,10 m", m_peitoril(1.10), {"6.11.3": "Não Conforme"}, ""),
    ("J02", "quase-erro", "Janela fixa: peitoril 1,20 → 1,21 m", m_peitoril(1.21), {}, ""),
    # 6.6 rampa (corrimãos inclinados junto para não contaminar o 5.4.3)
    ("R01", "grosseiro", "Rampa: 6,67% → 10,0% (desnível 0,18 m)", m_rampa(10.0), {"6.6": "Não Conforme"}, ""),
    ("R02", "quase-erro", "Rampa: 6,67% → 8,0% (desnível 0,144 m)", m_rampa(8.0), {}, ""),
    ("R03", "limítrofe", "Rampa: 6,67% → 8,6% (desnível 0,155 m)", m_rampa(8.6), {"6.6": "Não Conforme"}, ""),
    # 5.4.3 corrimão
    ("C01", "grosseiro", "Corrimão de parede removido (só um lado)", m_remover_corrimao_parede, {"5.4.3": "Parcial"}, ""),
    ("C02", "real-revit", "Corrimão de parede reto, não acompanha a rampa (IFC real: BENCHMARK_00_2)", "REAL", {"5.4.3": "Parcial"}, ""),
    ("C03", "grosseiro", "Corrimão do guarda-corpo 8 cm mais baixo (topo 0,84 m)", m_baixar_corrimao_vidro(0.08), {"5.4.3": "Parcial"}, ""),
    # 6.3.4 desníveis (base: ACESSO +5 mm em relação ao WC)
    ("D01", "grosseiro", "Piso WC −10 mm → desnível de 15 mm na porta (sem chanfro)", m_desnivel_wc(-0.010), {"6.3.4": "Indeterminado"}, ""),
    ("D02", "grosseiro", "Piso WC −25 mm → desnível de 30 mm na porta (degrau)", m_desnivel_wc(-0.025), {"6.3.4": "Não Conforme"}, ""),
    ("D03", "quase-erro", "Piso WC +2 mm → desnível de 3 mm na porta", m_desnivel_wc(+0.002), {}, ""),
    # 7.7.2.1 bacia (subir a bacia aproxima a tampa da barra de fundo → 7.6-7.8 também)
    ("S01", "grosseiro", "Bacia +6 cm (borda 0,495 m)", m_subir(["bacia"], 0.06),
     {"7.7.2.1": "Não Conforme", "7.6-7.8": "Não Conforme"}, "barra de fundo fica abaixo de 0,04 m da tampa"),
    ("S02", "limítrofe", "Bacia +2 cm (borda 0,455 m)", m_subir(["bacia"], 0.02),
     {"7.7.2.1": "Parcial", "7.6-7.8": "Parcial"}, "folga barra de fundo × tampa cai para ~0,03 m"),
    # 7.6-7.8 barras
    ("G01", "grosseiro", "Barra lateral: eixo 0,75 → 0,85 m", m_subir(["barra_lateral"], 0.10), {"7.6-7.8": "Não Conforme"},
     "a vertical também perde a referência (0,10 m acima da horizontal)"),
    ("G02", "grosseiro", "Barra de fundo: eixo 0,89 → 0,95 m", m_subir(["barra_fundo"], 0.06), {"7.6-7.8": "Não Conforme"}, ""),
    ("G03", "grosseiro", "Barra vertical 10 cm mais alta (fixação inferior 0,95 m)", m_subir(["barra_vertical"], 0.10), {"7.6-7.8": "Não Conforme"}, ""),
    ("G04", "grosseiro", "Barras do lavatório: face superior 0,797 → 0,85 m", m_subir(["barra_lav_1", "barra_lav_2"], 0.053), {"7.6-7.8": "Não Conforme"}, ""),
    ("G05", "limítrofe", "Barras do lavatório: face superior 0,797 → 0,815 m", m_subir(["barra_lav_1", "barra_lav_2"], 0.018), {"7.6-7.8": "Parcial"}, ""),
    # 4.6.6 maçaneta
    ("M01", "grosseiro", "Ferragens: 'maçaneta tipo bola esférica'", m_ferragens("fechadura e maçaneta tipo bola esférica"), {"4.6.6": "Não Conforme"}, ""),
    ("M02", "omissão", "Ferragens sem tipo de maçaneta ('fechadura')", m_ferragens("fechadura"), {"4.6.6": "Indeterminado"}, ""),
    # 7.5 / 6.11.1 espaços
    ("W01", "grosseiro", "WC PNE com 1,40 m de largura (não cabe ⌀1,50 m)", m_estreitar_wc(1.40), {"7.5": "Não Conforme"},
     "7.7.1 (transferência lateral) depende só do LLM"),
    ("A01", "grosseiro", "ACESSO com 0,85 m de largura (mín. 0,90 m)", m_estreitar_acesso(0.85), {"6.11.1": "Não Conforme"}, ""),
    # 7.8 lavatório
    ("L01", "grosseiro", "Lavatórios renomeados 'com coluna'", m_lavatorio_com_coluna, {"7.8": "Não Conforme"}, ""),
    # multi-erro
    ("X01", "multi", "P01 + G01 + D02", combinar(m_largura_porta(0.75), m_subir(["barra_lateral"], 0.10), m_desnivel_wc(-0.025)),
     {"6.11.2": "Não Conforme", "7.6-7.8": "Não Conforme", "6.3.4": "Não Conforme"}, ""),
    ("X02", "multi", "C01 + R01 + M01", combinar(m_remover_corrimao_parede, m_rampa(10.0), m_ferragens("fechadura e maçaneta tipo bola esférica")),
     {"5.4.3": "Parcial", "6.6": "Não Conforme", "4.6.6": "Não Conforme"}, ""),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="IFC 100%% conforme (BENCHMARK_00_3.ifc)")
    ap.add_argument("--real-corrimao", help="IFC real com corrimão reto (BENCHMARK_00_2.ifc) → variante C02")
    ap.add_argument("--saida", default=str(AQUI / "variantes"))
    a = ap.parse_args()
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)

    # 1) GABARITO primeiro — antes de qualquer execução do auditor
    linhas = []
    for vid, nivel, desc, mut, esperado, efeito in VARIANTES:
        if mut == "REAL" and not a.real_corrimao:
            continue
        for item in ITENS:
            st = esperado.get(item, BASE_ESPERADO[item])
            linhas.append({"variante": vid, "nivel": nivel, "alteracao": desc, "item_nbr": item,
                           "status_esperado": st, "alterado": "sim" if item in esperado else "não",
                           "efeito_colateral_esperado": efeito if item in esperado else ""})
    with open(AQUI / "gabarito.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
        w.writeheader(); w.writerows(linhas)
    print(f"gabarito.csv gravado em {datetime.now():%Y-%m-%d %H:%M:%S} ({len(linhas)} linhas)")

    # 2) Variantes
    for vid, nivel, desc, mut, esperado, efeito in VARIANTES:
        destino = saida / f"{vid}.ifc"
        if mut == "REAL":
            if a.real_corrimao:
                shutil.copy(a.real_corrimao, destino); print(f"{vid}: cópia do IFC real")
            continue
        f = ifcopenshell.open(a.base)
        if mut is not None:
            mut(f)
        f.write(str(destino))
        print(f"{vid}: {desc}")


if __name__ == "__main__":
    main()
