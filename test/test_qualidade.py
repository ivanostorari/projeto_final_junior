"""Regras de qualidade (pipeline/qualidade.py): passam no dado bom e falham, uma a uma, no dado adulterado."""

import shutil

import pytest

from pipeline import marts, qualidade
from pipeline.qualidade import AVISO, ERRO, bloqueia, falhas, relatorio, resumo
from test.conftest import popular_raw


def por_regra(verificacoes, trecho):
    achadas = [v for v in verificacoes if trecho in v.regra]
    assert len(achadas) == 1, trecho
    return achadas[0]


def regras_com_falha(verificacoes, severidade=None):
    return {v.regra for v in falhas(verificacoes, severidade)}


def test_silver_sem_erro_no_dado_bom_e_aviso_de_idade_nula(refined):
    # 2 de 8 respostas ficam sem idade (99999999999 e -5): 25% > 5%, então só o AVISO dispara.
    verificacoes = qualidade.verificar_silver(refined)
    assert not bloqueia(verificacoes)
    assert regras_com_falha(verificacoes) == {"idade nula em no máximo 5% das linhas"}
    assert por_regra(verificacoes, "idade nula em").severidade == AVISO


def test_informacao_nunca_falha_e_mede(refined):
    info = [v for v in qualidade.verificar_silver(refined) if v.severidade == qualidade.INFORMACAO]
    assert [v.observado for v in info] == ["8", "2"] and all(v.ok for v in info)


def test_esquema_coluna_removida_e_erro_e_diz_qual(refined):
    refined.execute("ALTER TABLE refined.respostas DROP COLUMN anonimato")
    falha = falhas(qualidade.verificar_silver(refined), ERRO)[0]
    assert "esquema" == falha.dimensao and "anonimato" in falha.detalhe


def test_esquema_tipo_errado_e_erro(refined):
    refined.execute("ALTER TABLE refined.respostas ALTER tratamento TYPE VARCHAR")
    assert any("tratamento" in v.detalhe for v in falhas(qualidade.verificar_silver(refined), ERRO))


def test_tabela_ausente_para_na_hora_sem_estourar(con):
    popular_raw(con)
    con.execute("CREATE SCHEMA refined")
    verificacoes = qualidade.verificar_silver(con)
    assert bloqueia(verificacoes) and len(verificacoes) == 3  # 2 esquemas + privacidade; nada mais é medido


def test_coluna_de_comentarios_em_refined_e_erro_de_privacidade(refined):
    refined.execute("ALTER TABLE refined.respostas ADD COLUMN comments VARCHAR")
    assert por_regra(qualidade.verificar_silver(refined), "comentários").ok is False


@pytest.mark.parametrize(
    ("ajuste", "regra", "severidade"),
    [
        ("UPDATE refined.respostas SET genero = NULL WHERE id_resposta = 1", "sem nulos", ERRO),
        ("UPDATE refined.respostas SET pais = NULL WHERE id_resposta = 1", "pais sem nulos", AVISO),
        ("UPDATE refined.respostas SET id_resposta = 1 WHERE id_resposta = 2", "id_resposta único", ERRO),
        ("UPDATE refined.paises SET nome = 'Canada' WHERE nome IN ('Canada', 'Germany')", "paises.nome único", ERRO),
        ("UPDATE refined.paises SET iso3 = 'USA'", "paises.iso3 único", ERRO),
        ("UPDATE refined.respostas SET idade = 200, idade_informada = 200 WHERE id_resposta = 1", "idade entre", ERRO),
        ("UPDATE refined.respostas SET genero = 'Outro' WHERE id_resposta = 1", "genero dentro", ERRO),
        ("UPDATE refined.respostas SET tamanho_empresa = 'Muitas' WHERE id_resposta = 1", "valores do dicionário", ERRO),
        ("UPDATE refined.respostas SET idade = 31 WHERE id_resposta = 1", "igual a idade_informada", ERRO),
        ("UPDATE refined.respostas SET respondido_em = TIMESTAMP '2999-01-01 00:00:00' WHERE id_resposta = 1",
         "não está no futuro", ERRO),
        ("UPDATE refined.respostas SET pais = 'Atlantis' WHERE id_resposta = 1", "existe em paises", AVISO),
    ],
)
def test_cada_regra_falha_quando_o_dado_e_adulterado(refined, ajuste, regra, severidade):
    refined.execute(ajuste)
    achada = [v for v in qualidade.verificar_silver(refined) if regra in v.regra and not v.ok]
    assert achada and achada[0].severidade == severidade


def test_conciliar_raw_compara_csv_com_raw(con):
    popular_raw(con)
    ok = qualidade.conciliar_raw(con, {"survey.csv": 8, "paises.csv": 6})
    assert not falhas(ok)
    errado = qualidade.conciliar_raw(con, {"survey.csv": 9, "paises.csv": 6})
    assert regras_com_falha(errado, ERRO) == {"linhas de survey.csv = linhas de raw.respostas"}


def test_conciliar_silver_pega_linha_que_sumiu(refined):
    assert not falhas(qualidade.conciliar_silver(refined))
    refined.execute("DELETE FROM refined.respostas WHERE id_resposta = 3")
    assert regras_com_falha(qualidade.conciliar_silver(refined), ERRO) == {
        "raw.respostas e refined.respostas têm o mesmo número de linhas"}


@pytest.fixture
def gold(refined, tmp_path):
    pasta = tmp_path / "sql"
    pasta.mkdir()
    for arquivo in marts.PASTA_SQL.glob("*.sql"):
        if not arquivo.name.startswith("08_"):  # o 08 exige 20 respostas por país
            shutil.copy(arquivo, pasta / arquivo.name)
    marts.executar(refined, pasta)
    return refined, [nome for _, nome in marts.listar_arquivos(pasta)]


def test_gold_boa_passa_em_tudo(gold):
    con, nomes = gold
    assert not falhas(qualidade.verificar_gold(con, nomes))


@pytest.mark.parametrize(
    ("ajuste", "regra"),
    [
        ("DROP TABLE marts.kpis", "todo .sql tem sua tabela"),
        ("DELETE FROM marts.historico_familiar", "pelo menos 1 linha"),
        ("UPDATE marts.tratamento_por_genero SET pct_tratamento = 100.5", "pct_* entre 0 e 100"),
        ("UPDATE marts.tamanho_empresa SET respondentes = -1 WHERE respondentes = 1", "nunca negativo"),
        ("UPDATE marts.faixa_etaria SET respondentes = respondentes + 1", "soma de respondentes"),
    ],
)
def test_cada_regra_da_gold_falha_quando_o_mart_e_adulterado(gold, ajuste, regra):
    con, nomes = gold
    con.execute(ajuste)
    achadas = [v for v in qualidade.verificar_gold(con, nomes) if regra in v.regra and not v.ok]
    assert achadas and achadas[0].severidade == ERRO


def test_resumo_relatorio_e_impressao(capsys):
    boa = qualidade.Verificacao("refined", "validade", "r1", ERRO, True, "0", "0")
    ruim = qualidade.Verificacao("refined", "validade", "r2", AVISO, False, "3", "0", "detalhe")
    assert resumo([boa, ruim]) == {"total": 2, "aprovadas": 1, "falhas_erro": 0, "falhas_aviso": 1,
                                   "bloqueia": False}
    assert relatorio([boa, ruim])["verificacoes"][1]["detalhe"] == "detalhe"
    qualidade.imprimir("Silver", [boa, ruim])
    saida = capsys.readouterr().out
    assert "1/2 ok" in saida and "[aviso]" in saida and "r2" in saida
