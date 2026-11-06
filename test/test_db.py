"""pipeline/db.py: caminhos e gravação."""

from pathlib import Path

import pandas as pd

from pipeline import db


def test_caminhos_nao_dependem_do_diretorio_corrente(tmp_path, monkeypatch):
    raiz = Path(db.__file__).resolve().parent.parent
    monkeypatch.chdir(tmp_path)
    assert db.RAIZ == raiz
    assert db.CAMINHO_BANCO == raiz / "saude_mental.duckdb"
    assert db.PASTA_RAW == raiz / "raw"


def test_conectar_cria_o_arquivo_se_faltar(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "novo.duckdb")
    con = db.conectar()
    con.close()
    assert (tmp_path / "novo.duckdb").exists()


def test_criar_schema_pode_rodar_duas_vezes(con):
    db.criar_schema(con, "raw")
    db.criar_schema(con, "raw")
    assert con.execute("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'raw'").fetchall()[0][0] == 1


def test_gravar_devolve_a_contagem_do_banco_e_recria_a_tabela(con):
    db.criar_schema(con, "raw")
    assert db.gravar(con, pd.DataFrame({"a": ["1", "2", "3"]}), "raw", "t") == 3
    assert db.gravar(con, pd.DataFrame({"a": ["9"]}), "raw", "t") == 1  # troca, não acrescenta


def test_gravar_mantem_texto_e_nulo(con):
    db.criar_schema(con, "raw")
    db.gravar(con, pd.DataFrame({"a": ["007", None]}), "raw", "t")
    assert con.execute("SELECT a FROM raw.t ORDER BY rowid").fetchall() == [("007",), (None,)]


def test_gravar_nao_deixa_tabela_temporaria_para_tras(con):
    db.criar_schema(con, "raw")
    db.gravar(con, pd.DataFrame({"a": ["1"]}), "raw", "t")
    db.gravar(con, pd.DataFrame({"a": ["1"]}), "raw", "u")  # a 2ª gravação funciona: nada ficou aberto
    assert con.execute("SELECT count(*) FROM raw.u").fetchall()[0][0] == 1
