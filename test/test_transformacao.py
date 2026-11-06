"""pipeline/transformacao.py com dado inventado (test/conftest.py)."""

import pytest

from pipeline import transformacao
from pipeline.transformacao import ErroDeTransformacao
from test.conftest import PAISES, popular_raw, resposta


def um(con, sql):
    return con.execute(sql).fetchall()[0][0]


def test_tipos_das_colunas_convertidas(refined):
    tipos = {r[0]: r[1] for r in refined.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'refined' AND table_name = 'respostas'").fetchall()}
    assert tipos["id_resposta"] == "INTEGER"
    assert tipos["respondido_em"] == "TIMESTAMP"
    assert tipos["idade_informada"] == "BIGINT"  # 99999999999 não cabe em INTEGER
    assert tipos["idade"] == "INTEGER"
    assert tipos["tratamento"] == "BOOLEAN" and tipos["autonomo"] == "BOOLEAN"
    assert tipos["beneficios"] == "VARCHAR"


def test_id_e_a_ordem_do_arquivo(refined):
    ids = refined.execute("SELECT id_resposta, idade_informada FROM refined.respostas ORDER BY id_resposta").fetchall()
    assert [i for i, _ in ids] == list(range(1, 9))
    assert ids[0][1] == 25 and ids[3][1] == 99999999999 and ids[6][1] == -5  # r1, r4, r7 na ordem de entrada


def test_idade_fora_de_16_a_80_vira_nulo_e_o_original_fica(refined):
    linhas = refined.execute("SELECT id_resposta, idade_informada, idade FROM refined.respostas ORDER BY 1").fetchall()
    assert [(i, v) for i, _, v in linhas if v is None] == [(4, None), (7, None)]
    assert (8, 17, 17) in linhas  # 17 está dentro do limite
    assert (4, 99999999999, None) in linhas


@pytest.mark.parametrize("idade, esperado", [("16", 16), ("80", 80), ("15", None), ("81", None), ("0", None)])
def test_limites_da_idade_sao_inclusivos(con, idade, esperado):
    popular_raw(con, respostas=[resposta(Age=idade)])
    transformacao.transformar(con)
    assert um(con, "SELECT idade FROM refined.respostas") == esperado


def test_genero_agrupa_em_quatro_categorias(refined):
    assert refined.execute("SELECT id_resposta, genero FROM refined.respostas ORDER BY 1").fetchall() == [
        (1, "Homem"), (2, "Mulher"), (3, "Homem"), (4, "Não informado"),
        (5, "Outras identidades"), (6, "Mulher"), (7, "Homem"), (8, "Mulher"),
    ]


def test_dicionario_de_genero_cobre_so_valores_em_minuscula_sem_espaco():
    from pipeline.dicionario import GENERO
    assert all(k == k.strip().lower() for k in GENERO)  # a chave é o que sobra depois de lower(trim())


def test_genero_nao_previsto_para_tudo_e_cita_o_valor(con):
    popular_raw(con, respostas=[resposta(), resposta(Gender="xyz")])
    with pytest.raises(ErroDeTransformacao) as erro:
        transformacao.transformar(con)
    assert "xyz" in str(erro.value) and "Gender" in str(erro.value)


def test_resposta_fora_do_dicionario_para_tudo(con):
    popular_raw(con, respostas=[resposta(benefits="Talvez?")])
    with pytest.raises(ErroDeTransformacao) as erro:
        transformacao.transformar(con)
    assert "benefits" in str(erro.value) and "Talvez?" in str(erro.value)


def test_sim_nao_com_valor_estranho_para_tudo(con):
    popular_raw(con, respostas=[resposta(treatment="Sim")])  # a pesquisa é em inglês: 'Sim' não é permitido
    with pytest.raises(ErroDeTransformacao):
        transformacao.transformar(con)


def test_idade_que_nao_e_numero_para_tudo(con):
    popular_raw(con, respostas=[resposta(Age="trinta")])
    with pytest.raises(ErroDeTransformacao) as erro:
        transformacao.transformar(con)
    assert "trinta" in str(erro.value)


def test_timestamp_fora_do_formato_para(con):
    popular_raw(con, respostas=[resposta(Timestamp="27/08/2014")])
    with pytest.raises(ErroDeTransformacao):
        transformacao.transformar(con)


def test_traducao_com_apostrofo(refined):
    assert um(refined, "SELECT beneficios FROM refined.respostas WHERE id_resposta = 3") == "Não sei"  # "Don't know"
    assert um(refined, "SELECT opcoes_cuidado FROM refined.respostas WHERE id_resposta = 3") == "Não tenho certeza"


def test_booleano_e_nulo_ficam_como_vieram(con):
    popular_raw(con, respostas=[resposta(self_employed=None, treatment="Yes", family_history="No")])
    transformacao.transformar(con)
    assert con.execute("SELECT autonomo, tratamento, historico_familiar FROM refined.respostas").fetchall() == [(None, True, False)]


def test_nulo_de_interferencia_continua_nulo(refined):
    assert um(refined, "SELECT count(*) FROM refined.respostas WHERE interferencia_trabalho IS NULL") == 3  # r3, r7, r8


def test_comments_nao_passa_para_refined(refined):
    colunas = [r[0] for r in refined.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'refined'").fetchall()]
    assert not any("comment" in c for c in colunas)
    assert "comments" not in colunas


def test_pais_com_alias_casa_com_paises(refined):
    assert refined.execute("SELECT pais FROM refined.respostas WHERE id_resposta IN (4, 8) ORDER BY 1").fetchall() == [
        ("Bahamas",), ("Czechia",)]


def test_pais_que_nao_existe_em_paises_para_tudo(con):
    popular_raw(con, respostas=[resposta(Country="Wakanda")])
    with pytest.raises(ErroDeTransformacao) as erro:
        transformacao.transformar(con)
    assert "Wakanda" in str(erro.value) and "ALIAS_PAISES" in str(erro.value)


def test_nome_de_pais_repetido_para_tudo(con):
    popular_raw(con, paises=PAISES + [PAISES[0]])
    with pytest.raises(ErroDeTransformacao) as erro:
        transformacao.transformar(con)
    assert "se repete" in str(erro.value)


def test_linha_identica_e_mantida_e_contada(con):
    popular_raw(con, respostas=[resposta(), resposta()])
    resultados = transformacao.transformar(con)
    assert um(con, "SELECT count(*) FROM refined.respostas") == 2  # sem chave natural, não dá para dizer que repete
    assert resultados[0]["identicas"] == 1


def test_resultado_mostra_antes_depois_nulos_e_idades_zeradas(refined, capsys):
    transformacao.imprimir(transformacao.transformar(refined))
    saida = capsys.readouterr().out
    assert "8 →       8 linhas" in saida
    assert "2 idades fora de 16..80" in saida
    assert "interferencia_trabalho 3" in saida and "idade 2" in saida
    assert "Homem 3" in saida and "Mulher 3" in saida


def test_falta_raw_manda_rodar_a_ingestao(con):
    with pytest.raises(ErroDeTransformacao) as erro:
        transformacao.transformar(con)
    assert "pipeline.ingestao" in str(erro.value)


def test_falha_no_meio_deixa_refined_como_estava(con):
    popular_raw(con)
    transformacao.transformar(con)
    antes = um(con, "SELECT count(*) FROM refined.respostas")
    popular_raw(con, respostas=[resposta(), resposta(), resposta(Gender="xyz")])  # raw novo, com um valor ruim
    with pytest.raises(ErroDeTransformacao):
        transformacao.transformar(con)
    assert um(con, "SELECT count(*) FROM refined.respostas") == antes


def test_falha_no_cadastro_de_paises_desfaz_tudo(con):
    popular_raw(con)
    transformacao.transformar(con)
    popular_raw(con, respostas=[resposta(), resposta(Country="Wakanda")])  # só detectado depois de criar as tabelas
    with pytest.raises(ErroDeTransformacao):
        transformacao.transformar(con)
    assert um(con, "SELECT count(*) FROM refined.respostas") == 8  # voltou ao que era (rollback)


def test_rodar_duas_vezes_da_o_mesmo_resultado(con):
    popular_raw(con)
    a = transformacao.transformar(con)
    b = transformacao.transformar(con)
    assert [(r["tabela"], r["saida"], r["nulos"]) for r in a] == [(r["tabela"], r["saida"], r["nulos"]) for r in b]


def test_expressao_com_tipo_desconhecido_estoura():
    with pytest.raises(ValueError):
        transformacao.expressao("x", "inexistente")


def test_apostrofo_no_literal_sql():
    assert transformacao._lit("Don't know") == "'Don''t know'"


def test_main_sai_com_codigo_1_quando_falta_raw(tmp_path, monkeypatch, capsys):
    from pipeline import db
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "t.duckdb")
    with pytest.raises(SystemExit) as saida:
        transformacao.main()
    assert saida.value.code == 1
    assert "pipeline.ingestao" in capsys.readouterr().out


def test_main_imprime_o_resumo(tmp_path, monkeypatch, capsys):
    from pipeline import db
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "t.duckdb")
    con = db.conectar()
    popular_raw(con)
    con.close()
    transformacao.main()
    assert "✓ refined.respostas" in capsys.readouterr().out
