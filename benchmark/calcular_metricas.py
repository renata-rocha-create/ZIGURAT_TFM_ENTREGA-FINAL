"""
calcular_metricas.py — Acurácia, precisão, recall e F1 do auditor a partir de
resultados.csv (variante × item: esperado vs. obtido por camada).

Definições (unidade de análise = par variante × item NBR):
  POSITIVO REAL     → status esperado ≠ Conforme e ≠ N/A (o item TEM problema).
  POSITIVO PREVISTO
     critério ESTRITO → auditor deu "Não Conforme" ou "Parcial";
     critério AMPLO   → idem + "Indeterminado" (sinalizou para revisão humana).
  No critério ESTRITO, pares cujo gabarito espera "Indeterminado" (ex.: dado
  omitido no modelo) ficam fora — só fazem sentido no critério AMPLO.
  Pares em que a camada não avaliou o item ("—") ficam FORA da conta
  daquela camada e são reportados como "não avaliados" (cobertura).

  Analogia: VP = alarme que tocou com incêndio; FP = alarme falso;
  FN = incêndio sem alarme; VN = silêncio sem incêndio.
  precisão = VP/(VP+FP)  → "quando acusa, acerta?"
  recall   = VP/(VP+FN)  → "dos problemas reais, quantos pegou?"
  F1       = média harmônica de precisão e recall
  acurácia = (VP+VN)/total
  acurácia de status exato → acertou a CATEGORIA (Conforme/Parcial/NC/Indet./N/A)

Uso: python benchmark/calcular_metricas.py [--resultados ...] [--saida ...]
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

# Terminal do Windows: aceitar acentos e setas nas mensagens sem travar
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


AQUI = Path(__file__).resolve().parent
NEG = {"Conforme", "N/A"}
POS_ESTRITO = {"Não Conforme", "Parcial"}
POS_AMPLO = POS_ESTRITO | {"Indeterminado"}


def _div(a, b):
    return round(a / b, 4) if b else None


def metricas(pares, criterio):
    vp = fp = fn = vn = exato = 0
    for esp, obt in pares:
        if criterio is POS_ESTRITO and esp == "Indeterminado":
            continue  # esperado "Indeterminado" (omissão de dado) só é avaliado no critério amplo
        real = esp not in NEG
        prev = obt in criterio
        vp += real and prev; fn += real and not prev
        fp += (not real) and prev; vn += (not real) and not prev
        exato += esp == obt
    n = vp + fp + fn + vn
    p, r = _div(vp, vp + fp), _div(vp, vp + fn)
    if p is None or r is None:
        f1 = None
    else:
        f1 = round(2 * p * r / (p + r), 4) if (p + r) else 0.0
    return {"n": n, "VP": vp, "FP": fp, "FN": fn, "VN": vn,
            "acuracia": _div(vp + vn, n), "precisao": p, "recall": r, "f1": f1,
            "acuracia_status_exato": _div(exato, n)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resultados", default=str(AQUI / "resultados.csv"))
    ap.add_argument("--saida", default=str(AQUI / "metricas.csv"))
    ap.add_argument("--erros", default=str(AQUI / "erros_auditor.csv"))
    ap.add_argument("--errata", default=str(AQUI / "gabarito_errata.csv"),
                    help="status esperado no nível do ITEM pela regra 'X de Y' (não altera o gabarito pré-registrado)")
    a = ap.parse_args()
    with open(a.resultados, encoding="utf-8") as fh:
        res = list(csv.DictReader(fh))

    errata = {}
    if Path(a.errata).exists():
        with open(a.errata, encoding="utf-8") as fh:
            errata = {(e["variante"], e["item_nbr"]): e["status_esperado_agregado"] for e in csv.DictReader(fh)}
    for r in res:
        r["status_esperado_agregado"] = errata.get((r["variante"], r["item_nbr"]), r["status_esperado"])

    camadas = [c for c in ("python", "llm", "final") if any(r[c] != "—" for r in res)]
    saida, erros = [], []
    for camada in camadas:
        avaliados = [r for r in res if r[camada] != "—"]
        cobertura = f"{len(avaliados)}/{len(res)}"
        grupos = defaultdict(list)
        for r in avaliados:
            grupos["GLOBAL"].append(r); grupos[r["item_nbr"]].append(r)
        for chave in ["GLOBAL"] + sorted(k for k in grupos if k != "GLOBAL"):
            pares = [(r["status_esperado"], r[camada]) for r in grupos[chave]]
            pares_ag = [(r["status_esperado_agregado"], r[camada]) for r in grupos[chave]]
            exato = _div(sum(e == o for e, o in pares), len(pares))          # sobre todos os pares avaliados
            exato_ag = _div(sum(e == o for e, o in pares_ag), len(pares_ag))
            for nome_crit, crit in (("estrito", POS_ESTRITO), ("amplo", POS_AMPLO)):
                m = metricas(pares, crit)
                m["acuracia_status_exato"] = exato
                m["acuracia_status_exato_errata"] = exato_ag
                saida.append({"camada": camada, "escopo": chave, "criterio": nome_crit,
                              "cobertura": cobertura if chave == "GLOBAL" else len(pares), **m})
        for r in avaliados:
            if r["status_esperado_agregado"] != r[camada]:
                esp, obt = r["status_esperado"], r[camada]
                real = esp not in NEG
                def _tipo(crit):
                    if crit is POS_ESTRITO and esp == "Indeterminado":
                        return "fora (só amplo)"
                    if real and obt not in crit: return "FN"
                    if not real and obt in crit: return "FP"
                    return "categoria"
                tipo = f"estrito={_tipo(POS_ESTRITO)}; amplo={_tipo(POS_AMPLO)}"
                erros.append({"camada": camada, "variante": r["variante"], "item_nbr": r["item_nbr"],
                              "esperado": r["status_esperado_agregado"], "obtido": r[camada], "tipo_erro": tipo,
                              "detalhe_python": r.get("detalhe_python", "")})

    with open(a.saida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(saida[0].keys())); w.writeheader(); w.writerows(saida)
    with open(a.erros, "w", newline="", encoding="utf-8") as fh:
        campos = ["camada", "variante", "item_nbr", "esperado", "obtido", "tipo_erro", "detalhe_python"]
        w = csv.DictWriter(fh, fieldnames=campos); w.writeheader(); w.writerows(erros)

    for s in saida:
        if s["escopo"] == "GLOBAL":
            print(f"[{s['camada']:6}|{s['criterio']:7}] n={s['n']:3} cobertura={s['cobertura']:8} "
                  f"VP={s['VP']:2} FP={s['FP']:2} FN={s['FN']:2} VN={s['VN']:3} | acc={s['acuracia']} "
                  f"prec={s['precisao']} rec={s['recall']} F1={s['f1']} | status exato={s['acuracia_status_exato']} "
                  f"(c/ errata {s['acuracia_status_exato_errata']})")
    print(f"{len(erros)} divergências (contra o gabarito com errata) → {a.erros}")


if __name__ == "__main__":
    main()
