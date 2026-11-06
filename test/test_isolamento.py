"""O guarda de isolamento (conftest.isolar_do_projeto) funciona: tocar no banco ou no raw/ do projeto quebra."""

import duckdb
import pandas as pd
import pytest

from pipeline import db


def test_abrir_o_banco_do_projeto_e_barrado():
    with pytest.raises(AssertionError, match="banco do projeto"):
        duckdb.connect(str(db.CAMINHO_BANCO))


def test_ler_o_raw_do_projeto_e_barrado():
    with pytest.raises(AssertionError, match="raw/"):
        (db.PASTA_RAW / "survey.csv").read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match="raw/"):
        pd.read_csv(db.PASTA_RAW / "survey.csv")


def test_banco_temporario_e_em_memoria_continuam_permitidos(tmp_path):
    duckdb.connect(str(tmp_path / "ok.duckdb")).close()
    duckdb.connect().close()
    (tmp_path / "a.csv").write_text("x\n1\n", encoding="utf-8")
    assert len(pd.read_csv(tmp_path / "a.csv")) == 1
