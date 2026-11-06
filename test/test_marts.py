"""O executor de marts (pipeline/marts.py), com SQL inventado de uma linha."""

import pytest

from pipeline import db, marts
from pipeline.marts import ErroDeMarts


@pytest.fixture
def refined_vazio(con):
    """As cinco tabelas de refined existem (vazias): é só o que o executor confere."""
    con.execute("CREATE SCHEMA refined")
    for tabela in marts.TABELAS_NECESSARIAS:
        con.execute(f"CREATE TABLE refined.{tabela} (x INTEGER)")
    return con


def sql(pasta, nome, texto):
    pasta.mkdir(exist_ok=True)
    (pasta / nome).write_text(texto, encoding="utf-8")


def tabelas_de_marts(con):
    return sorted(r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts'").fetchall())


def test_nome_da_tabela_sai_do_arquivo_sem_o_prefixo(refined_vazio, tmp_path):
    sql(tmp_path, "00_teste.sql", "SELECT 1 AS x")
    sql(tmp_path, "01_outro_mart.sql", "SELECT 1 AS a UNION ALL SELECT 2")
    resultados = marts.executar(refined_vazio, tmp_path)
    assert resultados == [("teste", 1), ("outro_mart", 2)]
    assert tabelas_de_marts(refined_vazio) == ["outro_mart", "teste"]


def test_apagar_o_arquivo_faz_o_mart_sumir(refined_vazio, tmp_path):
    sql(tmp_path, "00_teste.sql", "SELECT 1 AS x")
    sql(tmp_path, "01_velho.sql", "SELECT 1 AS x")
    marts.executar(refined_vazio, tmp_path)
    (tmp_path / "01_velho.sql").unlink()
    marts.executar(refined_vazio, tmp_path)
    assert tabelas_de_marts(refined_vazio) == ["teste"]


def test_ponto_e_virgula_final_e_espacos_sao_tirados(refined_vazio, tmp_path):
    sql(tmp_path, "00_teste.sql", "\n  SELECT 1 AS x ;  \n\n")
    assert marts.executar(refined_vazio, tmp_path) == [("teste", 1)]
    assert marts.limpar_sql("SELECT 1;;") == "SELECT 1;"  # só UM ponto e vírgula; o resto é problema do arquivo


def test_erro_de_sql_para_tudo_com_o_nome_do_arquivo_e_marts_fica_como_estava(refined_vazio, tmp_path):
    sql(tmp_path, "00_bom.sql", "SELECT 1 AS x")
    marts.executar(refined_vazio, tmp_path)
    sql(tmp_path, "01_quebrado.sql", "SELEC 1 AS x")
    with pytest.raises(ErroDeMarts) as erro:
        marts.executar(refined_vazio, tmp_path)
    assert "01_quebrado.sql" in str(erro.value)
    assert tabelas_de_marts(refined_vazio) == ["bom"]  # o schema voltou ao que era


def test_mart_vazio_para_tudo(refined_vazio, tmp_path):
    sql(tmp_path, "00_ok.sql", "SELECT 1 AS x")
    sql(tmp_path, "01_vazio.sql", "SELECT 1 AS x WHERE false")
    with pytest.raises(ErroDeMarts) as erro:
        marts.executar(refined_vazio, tmp_path)
    assert "vazio" in str(erro.value) and "zero linhas" in str(erro.value)
    assert tabelas_de_marts(refined_vazio) == []  # nenhum mart parcial


def test_arquivo_sem_prefixo_para_antes_de_executar_qualquer_sql(refined_vazio, tmp_path):
    sql(tmp_path, "teste.sql", "SELECT 1 AS x")
    with pytest.raises(ErroDeMarts) as erro:
        marts.executar(refined_vazio, tmp_path)
    assert "teste.sql" in str(erro.value)
    assert tabelas_de_marts(refined_vazio) == []


def test_maiuscula_ou_um_digito_so_tambem_sao_recusados(tmp_path):
    sql(tmp_path, "1_curto.sql", "SELECT 1")
    sql(tmp_path, "02_Maiuscula.sql", "SELECT 1")
    with pytest.raises(ErroDeMarts) as erro:
        marts.listar_arquivos(tmp_path)
    assert "1_curto.sql" in str(erro.value) and "02_Maiuscula.sql" in str(erro.value)


def test_dois_arquivos_com_o_mesmo_nome_de_tabela_param(tmp_path):
    sql(tmp_path, "01_vendas.sql", "SELECT 1")
    sql(tmp_path, "02_vendas.sql", "SELECT 1")
    with pytest.raises(ErroDeMarts) as erro:
        marts.listar_arquivos(tmp_path)
    assert "vendas" in str(erro.value) and "01_vendas.sql" in str(erro.value)


def test_pasta_sem_sql_avisa(tmp_path):
    with pytest.raises(ErroDeMarts) as erro:
        marts.listar_arquivos(tmp_path)
    assert "Nenhum arquivo" in str(erro.value)
    with pytest.raises(ErroDeMarts):
        marts.listar_arquivos(tmp_path / "nao_existe")


def test_faltando_refined_manda_rodar_a_transformacao(con, tmp_path):
    sql(tmp_path, "00_teste.sql", "SELECT 1 AS x")
    with pytest.raises(ErroDeMarts) as erro:
        marts.executar(con, tmp_path)
    assert "pipeline.transformacao" in str(erro.value)


def test_rodar_duas_vezes_da_o_mesmo_resultado(refined_vazio, tmp_path):
    sql(tmp_path, "00_teste.sql", "SELECT 1 AS x")
    assert marts.executar(refined_vazio, tmp_path) == marts.executar(refined_vazio, tmp_path)


def test_imprimir_singular_plural_e_milhar(capsys):
    marts.imprimir([("kpis", 1), ("rotas", 1224)])
    saida = capsys.readouterr().out
    assert "1 linha\n" in saida and "1.224 linhas" in saida and "2 marts" in saida and "1.225 linhas" in saida


def test_main_sai_com_codigo_1_e_main_feliz(tmp_path, monkeypatch, capsys):
    caminho = tmp_path / "t.duckdb"
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)
    monkeypatch.setattr(marts, "PASTA_SQL", tmp_path / "sql")
    sql(tmp_path / "sql", "00_teste.sql", "SELECT 1 AS x")
    with pytest.raises(SystemExit) as saida:  # banco novo: refined não existe
        marts.main()
    assert saida.value.code == 1
    capsys.readouterr()

    con = db.conectar()
    con.execute("CREATE SCHEMA refined")
    for tabela in marts.TABELAS_NECESSARIAS:
        con.execute(f"CREATE TABLE refined.{tabela} (x INTEGER)")
    con.close()
    marts.main()
    assert "✓ marts.teste" in capsys.readouterr().out
