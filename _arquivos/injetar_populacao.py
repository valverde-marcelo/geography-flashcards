#!/usr/bin/env python3
"""
injetar_populacao.py
Injeta o atributo 'populacao' (e 'populacao_ano') em cada país de data.json,
usando o indicador 77849 (População total) da API do IBGE.

API: https://servicodados.ibge.gov.br/api/v1/paises/{sigla}/indicadores/77849

Uso:
  python3 injetar_populacao.py data.json
  python3 injetar_populacao.py data.json data_com_populacao.json
"""

import json
import re
import sys
import time
import requests

INDICADOR_POPULACAO = 77849
API_URL = "https://servicodados.ibge.gov.br/api/v1/paises/{sigla}/indicadores/{indicador}"
ANO_RE = re.compile(r"^\d{4}$")  # aceita só chaves como "2023", rejeita "2022-2024" e "-"

# Pausa entre requisições (segundos) — evita sobrecarregar a API do IBGE
DELAY_SEGUNDOS = 0.2


# ── extração (mesma lógica de extrair_populacao.py) ────────────────────────

def extrair_ultima_populacao(data: list):
    """
    Recebe o JSON já parseado (lista, como retornado pela API do IBGE) e
    devolve (ano, populacao) mais recentes disponíveis na série, ou None
    se não houver nenhum valor válido.
    """
    if not data:
        return None

    serie = data[0]["series"][0]["serie"]

    valores_validos = [
        (int(ano), int(valor))
        for item in serie
        for ano, valor in item.items()
        if valor is not None and ANO_RE.match(ano)
    ]

    if not valores_validos:
        return None

    return max(valores_validos, key=lambda par: par[0])


def fetch_populacao(sigla: str, indicador: int = INDICADOR_POPULACAO, timeout: int = 30):
    """Busca o indicador na API do IBGE para o país 'sigla' e extrai o último valor."""
    url = API_URL.format(sigla=sigla, indicador=indicador)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return extrair_ultima_populacao(resp.json())


# ── injeção em data.json ─────────────────────────────────────────────────────

def injetar_populacao(paises: list, delay: float = DELAY_SEGUNDOS) -> tuple:
    """
    Para cada país da lista (dicts com chave 'codigo_iso'), busca a
    população na API do IBGE e injeta 'populacao' / 'populacao_ano'
    diretamente no dict (em memória, modifica e também retorna a lista).

    Retorna (ok_count, falhas) onde falhas é uma lista de (sigla, nome, erro).
    """
    total  = len(paises)
    ok     = 0
    falhas = []

    for i, pais in enumerate(paises, 1):
        sigla = (pais.get("codigo_iso") or "").upper()
        nome  = pais.get("nome", "?")

        if not sigla:
            pais["populacao"]      = None
            pais["populacao_ano"]  = None
            print(f"  [{i:3d}/{total}] {nome:<40} SEM codigo_iso — pulado")
            continue

        try:
            resultado = fetch_populacao(sigla)
            if resultado is None:
                pais["populacao"]     = None
                pais["populacao_ano"] = None
                print(f"  [{i:3d}/{total}] {sigla:<3} {nome:<40} sem dados de população")
            else:
                ano, populacao = resultado
                pais["populacao"]     = populacao
                pais["populacao_ano"] = ano
                ok += 1
                print(f"  [{i:3d}/{total}] {sigla:<3} {nome:<40} {populacao:>12,} ({ano})")
        except Exception as exc:
            pais["populacao"]     = None
            pais["populacao_ano"] = None
            falhas.append((sigla, nome, str(exc)))
            print(f"  [{i:3d}/{total}] {sigla:<3} {nome:<40} ERRO: {exc}", file=sys.stderr)

        if delay:
            time.sleep(delay)

    return ok, falhas


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 injetar_populacao.py <data.json> [saida.json]", file=sys.stderr)
        sys.exit(1)

    in_path  = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else in_path

    with open(in_path, "r", encoding="utf-8") as f:
        paises = json.load(f)

    print(f"Carregados {len(paises)} países de {in_path}\n")

    ok, falhas = injetar_populacao(paises)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(paises, f, ensure_ascii=False, indent=4)

    print(f"\n{'─' * 60}")
    print(f"Sucesso: {ok}/{len(paises)}")
    if falhas:
        print(f"Falhas/sem dados: {len(falhas)}", file=sys.stderr)
        for sigla, nome, erro in falhas:
            print(f"  X {sigla} {nome}: {erro}", file=sys.stderr)

    print(f"\nArquivo salvo em: {out_path}")


if __name__ == "__main__":
    main()