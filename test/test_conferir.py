"""conferir.py: só a lógica de comparação, com um banco inventado (o banco real não é aberto aqui)."""

import duckdb
import pytest

import conferir
import painel


@pytest.fixture
def banco(tmp_path):
    caminho = tmp_path / "t.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.t AS SELECT * FROM (VALUES ('a', 10.04), ('b', 20.0)) v(nome, pct)")
    con.close()
    return caminho


def test_igual_ao_esperado_passa_e_diferente_falha(banco):
    con = duckdb.connect(str(banco), read_only=True)
    lista = [
        ("certo", "um", "SELECT pct FROM marts.t WHERE nome = 'b'", 20.0),
        ("certo", "dois", "SELECT pct FROM marts.t WHERE nome = 'b'", 21.0),
    ]
    resultados = conferir.conferir(con, lista)
    con.close()
    assert [r[4] for r in resultados] == [True, False]
    assert resultados[1][2] == 20.0 and resultados[1][3] == 21.0


def test_float_e_arredondado_em_duas_casas_antes_de_comparar(banco):
    con = duckdb.connect(str(banco), read_only=True)
    resultados = conferir.conferir(con, [("certo", "x", "SELECT sum(pct) / 3 FROM marts.t", 10.01)])  # 10,0133...
    con.close()
    assert resultados[0][4] is True


def test_inteiro_compara_como_inteiro(banco):
    con = duckdb.connect(str(banco), read_only=True)
    assert conferir.conferir(con, [("certo", "n", "SELECT count(*) FROM marts.t", 2)])[0][4] is True
    con.close()


def test_imprimir_devolve_quantos_divergiram_e_mostra_o_esperado(capsys):
    resultados = [("certo", "ok", 1, 1, True), ("certo", "ruim", 2, 3, False), ("errado", "erro comum", 9, 9, True)]
    assert conferir.imprimir(resultados) == 1
    saida = capsys.readouterr().out
    assert "✓ [certo" in saida and "✗ [certo" in saida and "(esperado 3)" in saida
    assert "ERRADO conhecido" in saida and "2 de 3 conferidos" in saida


def test_lista_real_tem_formato_valido_e_descricoes_unicas():
    descricoes = [c[1] for c in conferir.CONFERENCIAS]
    assert len(descricoes) == len(set(descricoes))
    for grupo, _descricao, sql, _esperado in conferir.CONFERENCIAS:
        assert grupo in ("certo", "errado")
        assert sql.lstrip().upper().startswith("SELECT")


def test_todo_numero_errado_conhecido_difere_do_certo_que_ele_substitui():
    # o ponto dos "errados" é serem números diferentes do que a tela mostra
    certos = {c[3] for c in conferir.CONFERENCIAS if c[0] == "certo"}
    for grupo, descricao, _sql, esperado in conferir.CONFERENCIAS:
        if grupo == "errado":
            assert esperado not in (50.6, 37.9, 1259), descricao
    assert 50.6 in certos and 37.9 in certos


def test_main_sem_banco_sai_com_codigo_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(painel, "CAMINHO_BANCO", tmp_path / "nao_existe.duckdb")
    with pytest.raises(SystemExit) as saida:
        conferir.main()
    assert saida.value.code == 1
    assert "executar.py" in capsys.readouterr().out


def test_main_com_banco_sem_marts_sai_com_codigo_1(banco, monkeypatch, capsys):
    monkeypatch.setattr(painel, "CAMINHO_BANCO", banco)  # tem marts.t, mas não os dez marts
    with pytest.raises(SystemExit) as saida:
        conferir.main()
    assert saida.value.code == 1
    assert "Erro ao conferir" in capsys.readouterr().out


def test_main_com_numero_divergente_sai_com_codigo_1(banco, monkeypatch, capsys):
    monkeypatch.setattr(painel, "CAMINHO_BANCO", banco)
    monkeypatch.setattr(conferir, "CONFERENCIAS", [("certo", "x", "SELECT pct FROM marts.t WHERE nome = 'a'", 99.0)])
    with pytest.raises(SystemExit) as saida:
        conferir.main()
    assert saida.value.code == 1
    assert "esperado 99.0" in capsys.readouterr().out


def test_main_tudo_certo_nao_sai_com_erro(banco, monkeypatch, capsys):
    monkeypatch.setattr(painel, "CAMINHO_BANCO", banco)
    monkeypatch.setattr(conferir, "CONFERENCIAS", [("certo", "x", "SELECT pct FROM marts.t WHERE nome = 'b'", 20.0)])
    conferir.main()
    assert "1 de 1 conferidos" in capsys.readouterr().out
