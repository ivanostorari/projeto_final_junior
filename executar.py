"""Roda o pipeline inteiro, do zero, na ordem. Executar com:

    uv run python executar.py

Confere os CSVs, roda ingestão, transformação e marts, confere a qualidade de cada camada e só então
troca o saude_mental.duckdb. Se qualquer etapa falhar, o banco anterior continua como estava (o novo é
construído ao lado e descartado). Cada execução fica registrada em logs/ e no schema `controle`.
Código de saída: 0 deu certo, 1 falhou. Regras completas em specs/operacao.md.
"""

import sys

from pipeline import orquestrador
from pipeline.saida import configurar_saida


def main() -> None:
    configurar_saida()
    resultado = orquestrador.rodar()
    orquestrador.imprimir_resumo(resultado)
    if resultado.status != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
