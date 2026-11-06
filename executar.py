"""Roda o pipeline inteiro, do zero, na ordem. Executar com:

    uv run python executar.py

É a saída de emergência de "quebrei tudo e não sei onde": apaga o saude_mental.duckdb
(o banco é descartável, os .sql e o código estão em arquivo) e roda a
ingestão, a transformação e os marts. Qualquer etapa que falhar interrompe
as seguintes: cada uma já encerra com sys.exit(1) e mensagem clara.
"""

from pipeline import db, ingestao, marts, transformacao
from pipeline.saida import configurar_saida


def main() -> None:
    configurar_saida()
    if db.CAMINHO_BANCO.exists():
        db.CAMINHO_BANCO.unlink()
        print(f"(banco {db.CAMINHO_BANCO.name} apagado)")
    etapas = [("1 · ingestão", ingestao), ("2 · transformação", transformacao), ("3 · marts", marts)]
    for nome, modulo in etapas:
        print(f"\n== {nome}")
        modulo.main()


if __name__ == "__main__":
    main()
