"""Conexão com o DuckDB. Spec completa em specs/ingestao.md (seção db.py).

Regras, e por que existem:

D1. Os caminhos saem da localização deste arquivo, nunca do diretório
    corrente. Motivo: rodar o script de outra pasta não pode criar um
    saude_mental.duckdb vazio no lugar errado, que parece ingestão quebrada.
D2. Só estas funções e constantes. Este módulo não lê CSV, não conhece nome
    de tabela, não imprime e não converte tipo. Motivo: as etapas 2, 3 e 4
    importam este arquivo; regra de negócio escondida aqui valeria para todas
    sem aparecer em nenhuma spec.
D3. gravar() recria a tabela com os tipos do DataFrame e devolve a contagem
    lida do banco. Motivo: o número que aparece na tela tem que ser o do que
    foi gravado, não o do que estava na memória.
D4. conectar() devolve a conexão aberta; quem chama é quem fecha. Sem conexão
    global.
"""

from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
PASTA_RAW = RAIZ / "raw"
CAMINHO_BANCO = RAIZ / "saude_mental.duckdb"
PASTA_LOGS = RAIZ / "logs"


def conectar() -> duckdb.DuckDBPyConnection:
    """Abre o banco, criando o arquivo se ele não existir."""
    return duckdb.connect(str(CAMINHO_BANCO))


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{nome}"')


def gravar(con: duckdb.DuckDBPyConnection, df, schema: str, tabela: str) -> int:
    """Recria schema.tabela com o conteúdo do DataFrame e devolve a contagem do banco."""
    con.register("_df_para_gravar", df)
    try:
        con.execute(f'CREATE OR REPLACE TABLE "{schema}"."{tabela}" AS SELECT * FROM _df_para_gravar')
    finally:
        con.unregister("_df_para_gravar")
    # fetchall (e não fetchone): fetchone deixa o resultado aberto e a próxima chamada falha.
    return con.execute(f'SELECT count(*) FROM "{schema}"."{tabela}"').fetchall()[0][0]
