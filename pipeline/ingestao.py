"""Etapa 1 · Ingestão: CSV -> schema raw. Executar com:

    uv run python -m pipeline.ingestao

Spec completa em specs/ingestao.md. Resumo das regras e dos motivos:

1. ESCOPO E NOMES. Dois arquivos viram duas tabelas em raw, com o mapa literal
   de ARQUIVOS abaixo. Nomes de tabela em português; nomes de coluna ficam os
   originais.
2. PROIBIDO AQUI. Nenhuma conversão de tipo, linha descartada, coluna
   renomeada ou valor corrigido. Motivo: a fronteira entre "o dado que chegou"
   e "o dado que eu decidi" é a passagem de raw para refined.
3. REEXECUÇÃO. CREATE OR REPLACE, nunca acrescenta. Motivo: poder errar sem
   medo e rodar de novo.
4. NULO POR ARQUIVO. A pesquisa usa "NA" (herança do R) como marcador de nulo;
   o arquivo de países só usa campo vazio. Motivo: a regra de um arquivo não
   pode vazar para o outro, e "NA" tem de virar nulo na pesquisa (sem isso,
   264 respostas sem resposta virariam a resposta "NA").
5. TIPAGEM. Tudo texto (dtype=str). Motivo: Age tem 99999999999 e -1726; a
   decisão sobre esses valores é registrada na etapa 2, não escondida na leitura.
6. SAÍDA. Uma linha por tabela, contagem vinda do banco, milhar com ponto.
7. ERRO. Faltou arquivo: lista quais, diz a pasta e sai com código 1, antes
   de gravar qualquer coisa. Motivo: ingerir 1 de 2 tabelas em silêncio gera um
   painel errado que parece certo.
"""

import sys

import pandas as pd

from pipeline import db
from pipeline.saida import configurar_saida, milhar

SCHEMA = "raw"

# arquivo em raw/ -> (tabela no schema raw, marcadores de nulo daquele arquivo)
ARQUIVOS = {
    "survey.csv": ("respostas", ["NA", ""]),
    "paises.csv": ("paises", [""]),
}


def verificar_arquivos(pasta=None) -> None:
    """Para tudo, com mensagem clara, se faltar qualquer arquivo de entrada."""
    pasta = pasta or db.PASTA_RAW
    faltando = [nome for nome in ARQUIVOS if not (pasta / nome).exists()]
    if faltando:
        print(f"Faltam arquivos na pasta {pasta}:")
        for nome in faltando:
            print(f"  - {nome}")
        print("Nada foi gravado. Coloque os arquivos em raw/ e rode de novo.")
        sys.exit(1)


def ler_csv(caminho, marcadores_de_nulo: list[str]) -> pd.DataFrame:
    """Lê um CSV como texto puro, sem inferir tipo."""
    return pd.read_csv(
        caminho,
        dtype=str,
        encoding="utf-8",
        na_values=marcadores_de_nulo,
        keep_default_na=False,
    )


def main() -> None:
    configurar_saida()
    verificar_arquivos()

    con = db.conectar()
    try:
        db.criar_schema(con, SCHEMA)
        total = 0
        for arquivo, (tabela, nulos) in ARQUIVOS.items():
            df = ler_csv(db.PASTA_RAW / arquivo, nulos)
            linhas = db.gravar(con, df, SCHEMA, tabela)
            total += linhas
            print(f"✓ {SCHEMA}.{tabela:<12} {milhar(linhas):>9} linhas")
        print(f"  total{'':<13} {milhar(total):>9} linhas")
    finally:
        con.close()


if __name__ == "__main__":
    main()
