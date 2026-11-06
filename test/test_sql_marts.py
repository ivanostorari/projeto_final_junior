"""Os .sql DE VERDADE (sql/marts/*.sql), rodados sobre as oito respostas inventadas do conftest.

Cada valor esperado sai da conta feita à mão sobre as linhas r1..r8 de conftest.py
(a tabela com o que cada uma responde está nos comentários de lá), nunca de um
número medido no dado real.
"""

import shutil

import pytest

from pipeline import marts, transformacao
from test.conftest import PAISES, pais, popular_raw, resposta

PASTA_REAL = marts.PASTA_SQL


@pytest.fixture(scope="module")
def banco(tmp_path_factory):
    import duckdb

    base = tmp_path_factory.mktemp("marts")
    con = duckdb.connect(str(base / "t.duckdb"))
    popular_raw(con)
    transformacao.transformar(con)
    # O mart 08 exige 20 respostas por país (HAVING); com 8 respostas ele voltaria vazio e o
    # executor pararia. Ele tem teste próprio, mais abaixo, com respostas geradas para isso.
    pasta = base / "sql"
    pasta.mkdir()
    for arquivo in PASTA_REAL.glob("*.sql"):
        if not arquivo.name.startswith("08_"):
            shutil.copy(arquivo, pasta / arquivo.name)
    marts.executar(con, pasta)
    yield con
    con.close()


def linhas(banco, sql):
    return banco.execute(sql).fetchall()


def test_dez_arquivos_cada_um_com_o_grao_no_cabecalho():
    arquivos = sorted(PASTA_REAL.glob("*.sql"))
    assert len(arquivos) == 10
    for arquivo in arquivos:
        primeira = arquivo.read_text(encoding="utf-8").splitlines()[0]
        assert primeira.startswith("-- Grão:"), arquivo.name


def test_01_respostas_por_continente(banco):
    # América: r1,r3,r6,r7,r8 (5; tratamento r1,r7 = 40,0%; histórico r1 = 20,0%)
    # Europa: r2,r4,r5 (3; tratamento r2,r5 = 66,7%; histórico r4,r5 = 66,7%)
    assert linhas(banco, "SELECT * FROM marts.respostas_por_continente") == [
        ("America", 5, 62.5, 40.0, 20.0),
        ("Europe", 3, 37.5, 66.7, 66.7),
    ]


def test_o_join_com_paises_pelo_nome_nao_multiplica_linhas(banco):
    assert linhas(banco, "SELECT count(*) FROM refined.respostas r LEFT JOIN refined.paises p ON p.nome = r.pais")[0][0] == 8
    # a armadilha: ligar pelo continente cruza cada resposta com todos os países do continente
    errado = linhas(banco, "SELECT count(*) FROM refined.respostas r JOIN refined.paises p ON p.continente = "
                           "(SELECT continente FROM refined.paises WHERE nome = r.pais)")[0][0]
    assert errado == 5 * 3 + 3 * 3  # 5 respostas da América × 3 países + 3 da Europa × 3 países
    assert errado > 8


def test_02_tratamento_por_genero(banco):
    # Homem r1,r3,r7: tratamento r1,r7 = 66,7%; histórico r1 = 33,3%
    # Mulher r2,r6,r8: tratamento r2 = 33,3%; histórico nenhum = 0,0%
    # Outras r5: 100/100. Não informado r4: tratamento 0, histórico 100.
    assert linhas(banco, "SELECT * FROM marts.tratamento_por_genero") == [
        ("Homem", 1, 3, 66.7, 33.3),
        ("Mulher", 2, 3, 33.3, 0.0),
        ("Outras identidades", 3, 1, 100.0, 100.0),
        ("Não informado", 4, 1, 0.0, 100.0),
    ]


def test_03_historico_familiar(banco):
    # Sim: r1,r4,r5 -> tratamento r1,r5 = 66,7% | Não: os outros 5 -> tratamento r2,r7 = 40,0%
    assert linhas(banco, "SELECT * FROM marts.historico_familiar") == [("Sim", 3, 66.7), ("Não", 5, 40.0)]


def test_04_interferencia_nulo_vira_sem_resposta_e_tudo_soma_8(banco):
    assert linhas(banco, "SELECT * FROM marts.interferencia_trabalho") == [
        ("Nunca", 1, 1, 12.5, 0.0),             # r4
        ("Raramente", 2, 1, 12.5, 100.0),       # r5
        ("Às vezes", 3, 2, 25.0, 50.0),         # r2 (tratamento) e r6
        ("Frequentemente", 4, 1, 12.5, 100.0),  # r1
        ("sem_resposta", 5, 3, 37.5, 33.3),     # r3, r7 (tratamento), r8
    ]
    assert linhas(banco, "SELECT sum(respondentes) FROM marts.interferencia_trabalho")[0][0] == 8


def test_05_apoio_empregador(banco):
    assert linhas(banco, "SELECT resposta, respondentes, pct_das_respostas, pct_tratamento FROM marts.apoio_empregador "
                         "WHERE pergunta = 'beneficios' ORDER BY ordem") == [
        ("Sim", 4, 50.0, 25.0),        # r1,r4,r6,r8: só r1 buscou tratamento
        ("Não", 3, 37.5, 100.0),       # r2,r5,r7: os três buscaram
        ("Não sei", 1, 12.5, 0.0),     # r3
    ]
    assert linhas(banco, "SELECT resposta, respondentes, pct_tratamento FROM marts.apoio_empregador "
                         "WHERE pergunta = 'anonimato' ORDER BY ordem") == [
        ("Sim", 1, 100.0), ("Não", 1, 0.0), ("Não sei", 6, 50.0)]


def test_05_cada_pergunta_soma_8_e_a_ordem_das_respostas_e_a_da_tela(banco):
    assert linhas(banco, "SELECT pergunta, sum(respondentes) FROM marts.apoio_empregador GROUP BY 1 ORDER BY 1") == [
        ("anonimato", 8), ("beneficios", 8), ("opcoes_cuidado", 8), ("programa_bem_estar", 8), ("recursos_ajuda", 8)]
    assert linhas(banco, "SELECT resposta FROM marts.apoio_empregador WHERE pergunta = 'opcoes_cuidado' ORDER BY ordem") == [
        ("Sim",), ("Não",), ("Não tenho certeza",)]


def test_06_tamanho_empresa(banco):
    assert linhas(banco, "SELECT * FROM marts.tamanho_empresa") == [
        ("1-5", 1, 2, 100.0, 50.0, 50.0),          # r1 (licença muito fácil, tratamento), r8
        ("6-25", 2, 2, 0.0, 0.0, 100.0),           # r2, r7: os dois buscaram tratamento
        ("26-100", 3, 1, 0.0, 0.0, 0.0),           # r3
        ("100-500", 4, 1, 100.0, 100.0, 0.0),      # r4 (licença um pouco fácil)
        ("500-1000", 5, 1, 0.0, 0.0, 100.0),       # r5
        ("Mais de 1000", 6, 1, 100.0, 100.0, 0.0), # r6
    ]


def test_07_receio_e_disposicao_sao_colunas_separadas(banco):
    # mental: receio Sim r1,r5,r8 / Talvez r2 / Não 4; entrevista Sim r1 / Talvez 0 / Não 7
    # física: receio Sim 0 / Talvez r4 / Não 7; entrevista Sim r3 / Talvez r2 / Não 6
    assert linhas(banco, "SELECT * FROM marts.consequencias_percebidas") == [
        ("Saúde mental", 1, 8, 37.5, 12.5, 50.0, 12.5, 0.0, 87.5),
        ("Saúde física", 2, 8, 0.0, 12.5, 87.5, 12.5, 12.5, 75.0),
    ]


def test_07_cada_grupo_de_tres_percentuais_soma_100(banco):
    # cada percentual é arredondado em uma casa: a soma dos três pode diferir de 100 por até 0,2
    for receio, entrevista in linhas(banco, "SELECT pct_receio_sim + pct_receio_talvez + pct_receio_nao, "
                                            "pct_entrevista_sim + pct_entrevista_talvez + pct_entrevista_nao "
                                            "FROM marts.consequencias_percebidas"):
        assert abs(receio - 100) <= 0.2 and abs(entrevista - 100) <= 0.2


def test_09_faixa_etaria_idade_invalida_nao_some(banco):
    assert linhas(banco, "SELECT * FROM marts.faixa_etaria") == [
        ("Até 24", 1, 2, 50.0, 50.0),             # r5 (24) e r8 (17)
        ("25 a 34", 2, 2, 100.0, 50.0),           # r1 (25) e r2 (34)
        ("35 a 44", 3, 1, 0.0, 0.0),              # r6 (35)
        ("45 ou mais", 4, 1, 0.0, 0.0),           # r3 (45)
        ("sem_idade_valida", 5, 2, 50.0, 50.0),   # r4 (99999999999) e r7 (-5)
    ]


def test_10_kpis(banco):
    # tratamento r1,r2,r5,r7 = 50,0 | histórico r1,r4,r5 = 37,5 | benefícios Sim r1,r4,r6,r8 = 50,0
    # receio Sim r1,r5,r8 = 37,5 | falaria com o supervisor Sim r1,r4,r8 = 37,5
    assert linhas(banco, "SELECT * FROM marts.kpis") == [(8, 50.0, 37.5, 50.0, 37.5, 37.5)]


def test_conferencia_cruzada_todo_mart_por_grupo_soma_os_mesmos_8(banco):
    for mart in ["respostas_por_continente", "tratamento_por_genero", "historico_familiar",
                 "interferencia_trabalho", "tamanho_empresa", "faixa_etaria"]:
        assert linhas(banco, f"SELECT sum(respondentes) FROM marts.{mart}")[0][0] == 8, mart


def test_08_ranking_so_com_20_respostas_ou_mais_e_empate_leva_a_mesma_posicao(con, tmp_path):
    # Respostas GERADAS (não escolhidas a dedo) porque a regra é o limite de 20:
    # EUA 20 respostas, 10 com benefícios (50,0%) | Reino Unido 20, 4 (20,0%) | Canadá 20, 4 (20,0%)
    # Alemanha só 19, todas com benefícios (100,0%): fica de fora, e é o pior caso do ranking se entrasse
    geradas = []
    for nome, quantidade, com_beneficio in [("United States", 20, 10), ("United Kingdom", 20, 4),
                                            ("Canada", 20, 4), ("Germany", 19, 19)]:
        geradas += [resposta(Country=nome, benefits="Yes" if i < com_beneficio else "No") for i in range(quantidade)]
    popular_raw(con, respostas=geradas)
    transformacao.transformar(con)
    pasta = tmp_path / "sql"
    pasta.mkdir()
    shutil.copy(PASTA_REAL / "08_ranking_paises.sql", pasta / "08_ranking_paises.sql")
    marts.executar(con, pasta)
    assert con.execute("SELECT pais, respondentes, pct_beneficios_sim, posicao FROM marts.ranking_paises "
                       "ORDER BY posicao, pais").fetchall() == [
        ("United States", 20, 50.0, 1),
        ("Canada", 20, 20.0, 2),
        ("United Kingdom", 20, 20.0, 2),  # empate: mesma posição (2)
    ]


def test_08_continente_vem_do_join(con, tmp_path):
    popular_raw(con, respostas=[resposta(Country="Canada") for _ in range(20)], paises=PAISES + [pais("Chile", "America", "South America")])
    transformacao.transformar(con)
    pasta = tmp_path / "sql"
    pasta.mkdir()
    shutil.copy(PASTA_REAL / "08_ranking_paises.sql", pasta / "08_ranking_paises.sql")
    marts.executar(con, pasta)
    assert con.execute("SELECT pais, continente, regiao_onu FROM marts.ranking_paises").fetchall() == [
        ("Canada", "America", "Northern America")]
