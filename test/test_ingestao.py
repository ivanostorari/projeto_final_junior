"""pipeline/ingestao.py com CSV inventado em tmp_path."""

import pytest

from pipeline import db, ingestao


def escrever(pasta, nome, texto):
    pasta.mkdir(exist_ok=True)
    (pasta / nome).write_text(texto, encoding="utf-8")


def test_ler_csv_nao_infere_tipo_e_mantem_zero_a_esquerda(tmp_path):
    escrever(tmp_path, "a.csv", "Age,codigo\n99999999999,007\n-1726,0\n")
    df = ingestao.ler_csv(tmp_path / "a.csv", ["NA", ""])
    assert df["Age"].tolist() == ["99999999999", "-1726"]  # texto, nunca número
    assert df["codigo"].tolist() == ["007", "0"]


def test_na_e_campo_vazio_viram_nulo_na_pesquisa(tmp_path):
    escrever(tmp_path, "a.csv", "state,work_interfere\nNA,Often\n,NA\nIL,Never\n")
    df = ingestao.ler_csv(tmp_path / "a.csv", ingestao.ARQUIVOS["survey.csv"][1])
    assert df["state"].isna().tolist() == [True, True, False]
    assert df["work_interfere"].isna().tolist() == [False, True, False]


def test_na_em_paises_nao_vira_nulo(tmp_path):
    # O marcador "NA" é da pesquisa. No arquivo de países um "NA" legítimo (como a Namíbia
    # tinha em ISO2) tem de continuar texto; só o campo vazio é nulo.
    escrever(tmp_path, "p.csv", "name_short,ISO3\nNamibia,NA\nAlgum,\n")
    df = ingestao.ler_csv(tmp_path / "p.csv", ingestao.ARQUIVOS["paises.csv"][1])
    assert df["ISO3"].tolist()[0] == "NA"
    assert df["ISO3"].isna().tolist() == [False, True]


def test_arquivo_faltando_para_antes_de_gravar(tmp_path, monkeypatch, capsys):
    escrever(tmp_path, "survey.csv", "Age\n1\n")  # falta paises.csv
    monkeypatch.setattr(db, "PASTA_RAW", tmp_path)
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "t.duckdb")
    with pytest.raises(SystemExit) as saida:
        ingestao.main()
    assert saida.value.code == 1
    texto = capsys.readouterr().out
    assert "paises.csv" in texto and "Nada foi gravado" in texto
    assert not (tmp_path / "t.duckdb").exists()  # nem o banco foi criado


def test_main_grava_duas_tabelas_como_texto_e_imprime_total(tmp_path, monkeypatch, capsys):
    escrever(tmp_path, "survey.csv", "Age,state\n30,NA\n31,IL\n")
    escrever(tmp_path, "paises.csv", "name_short,ISO3\nBrasil,BRA\n")
    monkeypatch.setattr(db, "PASTA_RAW", tmp_path)
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "t.duckdb")
    ingestao.main()
    saida = capsys.readouterr().out
    assert "✓ raw.respostas" in saida and "✓ raw.paises" in saida and "3 linhas" in saida
    con = db.conectar()
    try:
        assert con.execute("SELECT typeof(Age) FROM raw.respostas LIMIT 1").fetchall()[0][0] == "VARCHAR"
        assert con.execute("SELECT count(*) FROM raw.respostas WHERE state IS NULL").fetchall()[0][0] == 1
    finally:
        con.close()


def test_main_duas_vezes_da_o_mesmo_banco(tmp_path, monkeypatch):
    escrever(tmp_path, "survey.csv", "Age\n30\n")
    escrever(tmp_path, "paises.csv", "name_short\nBrasil\n")
    monkeypatch.setattr(db, "PASTA_RAW", tmp_path)
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "t.duckdb")
    ingestao.main()
    ingestao.main()
    con = db.conectar()
    try:
        assert con.execute("SELECT count(*) FROM raw.respostas").fetchall()[0][0] == 1
    finally:
        con.close()
