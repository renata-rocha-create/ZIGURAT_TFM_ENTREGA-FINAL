"""
testar_conexao.py — Diagnóstico da conexão com a API da Anthropic.

Mostra versões, se a chave está definida, se a internet chega até
api.anthropic.com e a CAUSA REAL de um "Connection error".
Não gasta quase nada: faz uma única chamada de 5 tokens.

Uso: python benchmark/testar_conexao.py [--modelo claude-sonnet-4-5]
"""
import argparse
import os
import platform
import ssl
import sys
import urllib.request

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def linha(t):
    print(f"\n── {t} " + "─" * max(0, 60 - len(t)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="claude-sonnet-4-5")
    a = ap.parse_args()

    linha("1. Ambiente")
    print("Python   :", sys.version.split()[0], "|", sys.executable)
    print("Sistema  :", platform.platform())
    try:
        import anthropic, httpx  # noqa: E401
        print("anthropic:", anthropic.__version__, "| httpx:", httpx.__version__)
    except Exception as e:
        print("ERRO ao importar anthropic/httpx:", repr(e)); return
    for v in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        if os.environ.get(v):
            print(f"{v} = {os.environ[v]}")

    linha("2. Chave")
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    if not k:
        print("NÃO definida nesta janela → rode:  $env:ANTHROPIC_API_KEY = \"sk-ant-...\"")
    else:
        print(f"definida: {k[:10]}…{k[-4:]} ({len(k)} caracteres)",
              "" if k.startswith("sk-ant-") else "  ⚠ não começa com sk-ant-")
        if k != k.strip():
            print("⚠ a chave tem espaço no começo ou no fim")

    linha("3. Internet até api.anthropic.com (sem a biblioteca)")
    try:
        urllib.request.urlopen("https://api.anthropic.com", timeout=15)
        print("OK")
    except urllib.error.HTTPError as e:
        print(f"OK (o servidor respondeu HTTP {e.code} — conexão funciona)")
    except Exception as e:
        print("FALHOU:", repr(e))
        if isinstance(getattr(e, "reason", None), ssl.SSLError) or "CERTIFICATE" in repr(e).upper():
            print("→ Problema de CERTIFICADO (antivírus/rede inspecionando HTTPS).")

    linha("4. Chamada real pela biblioteca anthropic (5 tokens)")
    if not k:
        print("pulado (sem chave)"); return
    try:
        c = anthropic.Anthropic(api_key=k.strip())
        r = c.messages.create(model=a.modelo, max_tokens=5, messages=[{"role": "user", "content": "oi"}])
        print("OK — resposta:", r.content[0].text)
    except Exception as e:
        print("FALHOU:", type(e).__name__, "-", e)
        causa, n = e.__cause__ or e.__context__, 0
        while causa is not None and n < 6:
            print("  causa:", type(causa).__name__, "-", causa)
            causa, n = causa.__cause__ or causa.__context__, n + 1


if __name__ == "__main__":
    main()
