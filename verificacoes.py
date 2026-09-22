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
