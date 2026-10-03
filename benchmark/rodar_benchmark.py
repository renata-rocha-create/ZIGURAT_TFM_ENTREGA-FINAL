"""
rodar_benchmark.py — Executa o auditor em todas as variantes e grava resultados.csv.

Três "camadas" são registradas por (variante × item NBR):
  python → status calculado só pela verificação determinística (verificacoes.py);
           "—" quando o Python não avalia o item (ex.: 7.7.1).
  llm    → status dado pelo LLM (só com --llm; precisa de chave de API).
  final  → o que o RELATÓRIO mostra: Python sobrescreve o LLM nos itens que
           ele avalia (aplicar_veredito_python); nos demais, vale o LLM.

Uso (na raiz do repositório):
    python benchmark/rodar_benchmark.py                               # só Python
    python benchmark/rodar_benchmark.py --llm anthropic --modelo <id> # + LLM
       (chave em ANTHROPIC_API_KEY ou GOOGLE_API_KEY, conforme o provedor)

Pré-requisito: benchmark/variantes/*.ifc (gerados por gerar_variantes.py).
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from extracao import extract_ifc_elements                      # noqa: E402
from verificacoes import (gerar_verificacoes, status_item_python,  # noqa: E402
                          classificar_status, aplicar_veredito_python)

# Terminal do Windows: aceitar acentos e setas nas mensagens sem travar
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _norm(i):
    return str(i).replace("–", "-").replace("—", "-").replace(" ", "")


def status_python(linhas, itens):
    out = {}
    for item in itens:
        ls = [l for l in linhas if _norm(l["item_nbr"]) == _norm(item)]
        st = status_item_python(ls)
        out[item] = st if st is not None else "—"
    return out


def status_llm(resultados, itens):
    por_item = {_norm(r.get("item_nbr")): classificar_status(r.get("status", "")) for r in resultados or []}
    return {item: por_item.get(_norm(item), "—") for item in itens}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variantes", default=str(AQUI / "variantes"))
    ap.add_argument("--gabarito", default=str(AQUI / "gabarito.csv"))
    ap.add_argument("--saida", default=str(AQUI / "resultados.csv"))
    ap.add_argument("--llm", choices=["anthropic", "gemini"], help="inclui a camada LLM")
    ap.add_argument("--modelo", help="id do modelo (o mesmo selecionado no app)")
    ap.add_argument("--temperatura", type=float, default=0.0)
    ap.add_argument("--so", nargs="*", help="rodar só estas variantes (ex.: --so B00 P01)")
    a = ap.parse_args()

    with open(a.gabarito, encoding="utf-8") as fh:
        gab = list(csv.DictReader(fh))
    variantes = list(dict.fromkeys(g["variante"] for g in gab))
    itens = list(dict.fromkeys(g["item_nbr"] for g in gab))
    esperado = {(g["variante"], g["item_nbr"]): g["status_esperado"] for g in gab}
    if a.so:
        variantes = [v for v in variantes if v in a.so]

    chamar = None
    if a.llm:
        if not a.modelo:
            sys.exit("--modelo é obrigatório com --llm")
        from llm_auditor import build_audit_prompt, call_anthropic, call_gemini
        # .strip(): uma chave colada com espaço no começo/fim quebra o cabeçalho
        # HTTP e aparece só como "Connection error" (aconteceu na 1ª rodada).
        chave = (os.environ.get("ANTHROPIC_API_KEY" if a.llm == "anthropic" else "GOOGLE_API_KEY") or "").strip()
        if not chave:
            sys.exit("defina ANTHROPIC_API_KEY / GOOGLE_API_KEY no ambiente")
        fn = call_anthropic if a.llm == "anthropic" else call_gemini
        chamar = lambda elem, nome: fn(chave, a.modelo, build_audit_prompt(elem, nome), a.temperatura)  # noqa: E731

    linhas_saida = []
    for n_v, v in enumerate(variantes, 1):
        caminho = Path(a.variantes) / f"{v}.ifc"
        if not caminho.exists():
            print(f"{v}: arquivo não encontrado — pulando"); continue
        t0 = time.time()
        elem = extract_ifc_elements(str(caminho))
        if not isinstance(elem, dict) or elem.get("error") or "_completo" not in elem:
            erro = elem.get("error") if isinstance(elem, dict) else elem
            sys.exit(f"\n{v}: a extração do IFC FALHOU → {erro}\n"
                     f"Nada foi gravado. Confira se o ifcopenshell está instalado neste Python:\n"
                     f'    python -c "import ifcopenshell; print(ifcopenshell.version)"')
        linhas = gerar_verificacoes(elem)
        if not linhas:
            sys.exit(f"\n{v}: o auditor não gerou nenhuma verificação — algo está errado na extração. Nada foi gravado.")
        py = status_python(linhas, itens)
        llm = {i: "—" for i in itens}
        final = {i: "—" for i in itens}   # sem LLM não há "relatório final" a medir
        if chamar:
            try:
                res = chamar(elem, caminho.name)
                llm = status_llm(res.get("resultados", []), itens)
                final = status_llm(aplicar_veredito_python(res.get("resultados", []), linhas), itens)
            except Exception as e:
                print(f"{v}: falha no LLM ({e}) — camada LLM fica '—'")
        for item in itens:
            linhas_saida.append({
                "variante": v, "item_nbr": item, "status_esperado": esperado[(v, item)],
                "python": py[item], "llm": llm[item], "final": final[item],
                "detalhe_python": " | ".join(f"{l['status']}: {l['mensagem']}"[:160]
                                             for l in linhas if _norm(l["item_nbr"]) == _norm(item)
                                             and l["status"] != "Conforme"),
            })
        print(f"[{n_v}/{len(variantes)}] {v}: ok ({time.time() - t0:.1f}s)", flush=True)

    with open(a.saida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas_saida[0].keys()))
        w.writeheader(); w.writerows(linhas_saida)
    print(f"resultados → {a.saida} ({len(linhas_saida)} linhas)")


if __name__ == "__main__":
    main()
