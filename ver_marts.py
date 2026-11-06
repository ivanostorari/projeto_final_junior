"""Mostra os indicadores (marts) no terminal, sem abrir o painel. Executar com:

    uv run python ver_marts.py                    # os dez marts
    uv run python ver_marts.py kpis               # só um
    uv run python ver_marts.py kpis ranking_paises

Existe para quem clona o repositório chegar aos números só lendo o README. Só LÊ:
reaproveita painel.ler() (banco aberto somente leitura e fechado antes de imprimir)
e não calcula nada. Cada tabela impressa é exatamente um SELECT * do mart.
"""

import sys

import pandas as pd

import painel


def formatar(df: pd.DataFrame) -> str:
    """O DataFrame como texto, sem índice e sem cortar colunas."""
    return df.to_string(index=False)


def main(argumentos: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    pedidos = sys.argv[1:] if argumentos is None else argumentos
    desconhecidos = [p for p in pedidos if p not in painel.MARTS]
    if desconhecidos:
        print("Mart(s) que não existem: " + ", ".join(desconhecidos))
        print("Os marts são: " + ", ".join(painel.MARTS))
        sys.exit(1)
    try:
        dados = painel.ler()
    except painel.ErroPainel as erro:
        print(erro)
        sys.exit(1)
    for nome in pedidos or painel.MARTS:
        print(f"\n== marts.{nome}  ({len(dados[nome])} linhas)")
        print(formatar(dados[nome]))


if __name__ == "__main__":
    main()
