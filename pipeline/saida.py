"""Formatação da saída na tela, comum às etapas do pipeline.

Existe separado do db.py de propósito: db.py não imprime nada (spec D2).
"""

import sys


def configurar_saida() -> None:
    """Força UTF-8 no stdout: o Prompt de Comando do Windows usa outro por padrão."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def milhar(n: int) -> str:
    """99441 -> '99.441' (ponto como separador de milhar, sempre, sem depender do locale)."""
    return f"{n:,}".replace(",", ".")
