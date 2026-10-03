"""
gerar_errata.py — Deriva, por REGRA, o status esperado no nível do ITEM.

Por que existe (transparência metodológica):
  O gabarito.csv (pré-registrado em 2026-10-03 17:26) anotou o status
  esperado do ELEMENTO alterado (ex.: "porta 0,75 m → Não Conforme").
  Mas o relatório do auditor dá um status por ITEM, agregando todos os
  elementos daquele item pela regra que já existia ANTES do benchmark:
    • nbr9050_rules.json — "X de Y elementos conformes": X=Y → Conforme,
      X=0 → Não Conforme, 0<X<Y → Parcial;
    • verificacoes.status_item_python (commit 8fd71d5, 15:21) — conformes +
      indeterminados → Parcial.
  Essa diferença só foi percebida depois da primeira execução. Para não
  "ajustar o gabarito ao resultado", a errata NÃO é escrita à mão: ela é
  calculada aqui a partir de (1) quantos elementos cada item tem no
  modelo-base (Y) e (2) quantos elementos cada mutação altera (X),
  aplicando a MESMA função de agregação do auditor. Nenhum resultado do
  auditor é lido por este script.

  As métricas binárias (precisão, recall, F1, acurácia) usam o gabarito
  ORIGINAL; a errata só afeta a "acurácia de status exato", reportada
  com e sem errata.

Uso: python benchmark/gerar_errata.py
"""
import csv
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from verificacoes import status_item_python  # noqa: E402  (regra de agregação do próprio auditor)

# (1) Inventário do modelo-base BENCHMARK_00_3: elementos avaliados por item (Y)
Y = {
    "6.6": 1,      # 1 rampa (IfcSlab inclinado)
    "6.11.1": 1,   # 1 corredor (ACESSO)
    "6.11.2": 2,   # 2 portas
    "6.11.3": 2,   # 2 janelas
    "5.4.3": 1,    # 1 rampa (o status do elemento já combina os 2 lados)
    "6.3.4": 3,    # 3 passagens: porta ACESSO↔WC, porta ACESSO↔PORTARIA, junta rampa↔ACESSO
    "7.5": 1,      # 1 sanitário PNE
    "7.7.2.1": 1,  # 1 bacia
    "4.6.6": 1,    # 1 porta de ambiente PCD
    "7.6-7.8": 5,  # 5 barras de apoio
    "7.8": 2,      # 2 lavatórios
}

# (2) Elementos alterados por cada mutação (X) — tirado da ESPECIFICAÇÃO das
#     variantes em gerar_variantes.py (descrição + efeito colateral declarado).
X = {
    ("P01", "6.11.2"): 1, ("P02", "6.11.2"): 1, ("P04", "6.11.2"): 1,
    ("J01", "6.11.3"): 1,
    ("R01", "6.6"): 1, ("R03", "6.6"): 1,
    ("C01", "5.4.3"): 1, ("C02", "5.4.3"): 1, ("C03", "5.4.3"): 1,
    ("D01", "6.3.4"): 1, ("D02", "6.3.4"): 1,
    ("S01", "7.7.2.1"): 1, ("S02", "7.7.2.1"): 1,
    ("S01", "7.6-7.8"): 1, ("S02", "7.6-7.8"): 1,   # barra de fundo × tampa
    ("G01", "7.6-7.8"): 2,                           # lateral + vertical (efeito declarado)
    ("G02", "7.6-7.8"): 1, ("G03", "7.6-7.8"): 1,
    ("G04", "7.6-7.8"): 2, ("G05", "7.6-7.8"): 2,    # as 2 barras do lavatório
    ("M01", "4.6.6"): 1, ("M02", "4.6.6"): 1,
    ("W01", "7.5"): 1, ("A01", "6.11.1"): 1,
    ("L01", "7.8"): 2,                               # os 2 lavatórios
    ("X01", "6.11.2"): 1, ("X01", "7.6-7.8"): 2, ("X01", "6.3.4"): 1,
    ("X02", "5.4.3"): 1, ("X02", "6.6"): 1, ("X02", "4.6.6"): 1,
}


def main():
    with open(AQUI / "gabarito.csv", encoding="utf-8") as fh:
        gab = list(csv.DictReader(fh))
    saida = []
    for g in gab:
        k = (g["variante"], g["item_nbr"])
        if g["alterado"] != "sim" or g["item_nbr"] not in Y:
            continue
        if k not in X:
            raise SystemExit(f"falta X para {k} — atualize a tabela X")
        x, y = X[k], Y[g["item_nbr"]]
        elementos = [{"status": g["status_esperado"]}] * x + [{"status": "Conforme"}] * (y - x)
        agregado = status_item_python(elementos)
        if agregado != g["status_esperado"]:
            saida.append({"variante": k[0], "item_nbr": k[1],
                          "status_esperado_original": g["status_esperado"],
                          "status_esperado_agregado": agregado,
                          "motivo": f"{x} de {y} elemento(s) com '{g['status_esperado']}', demais Conforme → "
                                    f"regra de agregação do auditor dá '{agregado}'"})
    with open(AQUI / "gabarito_errata.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["variante", "item_nbr", "status_esperado_original",
                                           "status_esperado_agregado", "motivo"])
        w.writeheader(); w.writerows(saida)
    print(f"errata: {len(saida)} linhas (de {sum(1 for g in gab if g['alterado'] == 'sim')} pares alterados)")
    for s in saida:
        print(f"  {s['variante']} {s['item_nbr']}: {s['status_esperado_original']} → {s['status_esperado_agregado']} ({s['motivo']})")


if __name__ == "__main__":
    main()
