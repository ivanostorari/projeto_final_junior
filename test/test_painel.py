"""painel.py: leitura, formato e gráficos, com tabelas pequenas inventadas.

Nenhum teste abre o saude_mental.duckdb real: ler() recebe o caminho de um banco temporário.
"""

import duckdb
import pandas as pd
import pytest

import painel
from painel import ErroPainel

# ---------------------------------------------------------------- formato

@pytest.mark.parametrize("valor, esperado", [
    (1234567.891, "1.234.567,9"),
    (0, "0,0"),
    (-10.04, "-10,0"),
    (None, "—"),
    (float("nan"), "—"),
    (pd.NA, "—"),
])
def test_decimal_usa_ponto_no_milhar_e_virgula_no_decimal(valor, esperado):
    assert painel.decimal(valor) == esperado


def test_inteiro_pct_com_n():
    assert painel.inteiro(1259) == "1.259"
    assert painel.inteiro(None) == "—"
    assert painel.pct(50.55) in ("50,5%", "50,6%")  # arredondamento de float; o mart já entrega 1 casa
    assert painel.pct(2.0, 2) == "2,00%"
    assert painel.pct(float("nan")) == "—"
    assert painel.com_n("Mulher", 1251) == "Mulher (n=1.251)"
    assert painel.com_n("Mulher", 251, quebra=True) == "Mulher<br>n=251"


def test_nunca_aparece_nan_no_texto():
    for funcao in (painel.decimal, painel.inteiro, painel.pct):
        assert "nan" not in funcao(float("nan")).lower()


# ---------------------------------------------------------------- cartões

KPIS = pd.DataFrame([{
    "respondentes": 1259, "pct_tratamento": 50.6, "pct_historico_familiar": 39.1, "pct_beneficios_sim": 37.9,
    "pct_receio_consequencia": 23.2, "pct_falaria_supervisor": 41.0}])


def test_cartoes_seis_com_a_definicao_no_rotulo():
    c = painel.cartoes(KPIS)
    assert len(c) == 6
    assert c[0][1] == "1.259" and "pessoas que responderam" in c[0][0]
    assert [v for _, v in c[1:]] == ["50,6%", "39,1%", "37,9%", "23,2%", "41,0%"]
    assert "empregador" in c[4][0] and "supervisor" in c[5][0]


def test_cartao_com_nulo_vira_traco():
    kpis = KPIS.copy()
    kpis["pct_tratamento"] = None
    assert painel.cartoes(kpis)[1][1] == "—"


# ---------------------------------------------------------------- gráficos

def dados_inventados():
    return {
        "respostas_por_continente": pd.DataFrame({
            "continente": ["America", "Europe", "sem_cadastro"], "respondentes": [5, 3, 1], "pct_das_respostas": [55.6, 33.3, 11.1],
            "pct_tratamento": [40.0, 66.7, 0.0], "pct_historico_familiar": [20.0, 66.7, 0.0]}),
        "tratamento_por_genero": pd.DataFrame({
            "genero": ["Homem", "Mulher", "Outras identidades", "Não informado"], "ordem": [1, 2, 3, 4],
            "respondentes": [990, 251, 19, 4], "pct_tratamento": [45.4, 68.9, 78.6, 100.0], "pct_historico_familiar": [1.0] * 4}),
        "faixa_etaria": pd.DataFrame({
            "faixa": ["Até 24", "25 a 34", "sem_idade_valida"], "ordem": [1, 2, 5], "respondentes": [156, 707, 8],
            "pct_tratamento": [44.9, 48.9, 62.5], "pct_historico_familiar": [1.0] * 3}),
        "apoio_empregador": pd.DataFrame({
            "pergunta": ["beneficios", "beneficios", "anonimato", "anonimato", "recursos_ajuda", "recursos_ajuda"],
            "resposta": ["Sim", "Não", "Sim", "Não", "Sim", "Não"], "ordem": [1, 2, 1, 2, 1, 2],
            "respondentes": [477, 374, 375, 65, 250, 646], "pct_das_respostas": [37.9, 29.7, 29.8, 5.2, 19.9, 51.3],
            "pct_tratamento": [1.0] * 6}),
        "tamanho_empresa": pd.DataFrame({
            "faixa": ["Mais de 1000", "1-5", "6-25"], "ordem": [6, 1, 2], "respondentes": [282, 162, 290],
            "pct_beneficios_sim": [64.9, 11.7, 20.7], "pct_licenca_facil": [1.0] * 3, "pct_tratamento": [1.0] * 3}),
        "ranking_paises": pd.DataFrame({
            "pais": ["United Kingdom", "United States", "Wakanda"], "continente": ["Europe", "America", "America"],
            "regiao_onu": ["x"] * 3, "respondentes": [185, 751, 30], "pct_beneficios_sim": [10.8, 53.0, 20.0],
            "pct_tratamento": [1.0] * 3, "posicao": [3, 1, 2]}),
        "interferencia_trabalho": pd.DataFrame({
            "interferencia": ["sem_resposta", "Nunca", "Frequentemente"], "ordem": [5, 1, 4], "respondentes": [264, 213, 144],
            "pct_das_respostas": [21.0, 16.9, 11.4], "pct_tratamento": [1.5, 14.1, 85.4]}),
        "consequencias_percebidas": pd.DataFrame({
            "saude": ["Saúde física", "Saúde mental"], "ordem": [2, 1], "respondentes": [1259, 1259],
            "pct_receio_sim": [4.8, 23.2], "pct_receio_talvez": [21.7, 37.9], "pct_receio_nao": [73.5, 38.9],
            "pct_entrevista_sim": [16.0, 3.5], "pct_entrevista_talvez": [44.2, 16.4], "pct_entrevista_nao": [39.7, 80.1]}),
        "historico_familiar": pd.DataFrame({"historico_familiar": ["Sim", "Não"], "respondentes": [492, 767], "pct_tratamento": [74.2, 35.5]}),
        "kpis": KPIS,
    }


def test_montar_graficos_devolve_os_oito_ids():
    g = painel.montar_graficos(dados_inventados())
    assert set(g) == {"continente", "genero", "idade", "apoio", "tamanho", "paises", "interferencia", "consequencias"}


def test_continentes_traduzidos_com_contagem_e_percentual_no_texto():
    g = painel.grafico_continentes(dados_inventados()["respostas_por_continente"])
    assert list(g.figura.data[0].y) == ["América", "Europa", "Sem cadastro"]
    assert g.figura.data[0].text[0] == "5 (55,6%)"
    assert "Contagem, não taxa" in g.nota


def test_genero_deixa_de_fora_grupo_com_menos_de_20_respostas_e_a_nota_diz_quem():
    g = painel.grafico_genero(dados_inventados()["tratamento_por_genero"])
    assert list(g.figura.data[0].x) == ["Homem<br>n=990", "Mulher<br>n=251"]
    assert "Outras identidades (19)" in g.nota and "Não informado (4)" in g.nota
    assert "menos de 20 respostas" in g.nota


def test_genero_20_respostas_exatas_entram():
    df = dados_inventados()["tratamento_por_genero"].copy()
    df.loc[df["genero"] == "Outras identidades", "respondentes"] = 20
    g = painel.grafico_genero(df)
    assert len(g.figura.data[0].x) == 3


def test_idade_sem_idade_valida_fica_fora_e_a_nota_conta():
    g = painel.grafico_idade(dados_inventados()["faixa_etaria"])
    assert [x.split("<br>")[0] for x in g.figura.data[0].x] == ["Até 24", "25 a 34"]
    assert "8 respostas com idade impossível" in g.nota


def test_apoio_so_respostas_sim_maior_primeiro_com_rotulo_em_portugues():
    g = painel.grafico_apoio(dados_inventados()["apoio_empregador"])
    assert list(g.figura.data[0].y) == [
        "Oferece benefícios de saúde mental", "Anonimato protegido ao usar o tratamento", "Oferece recursos para buscar ajuda"]
    assert tuple(g.figura.layout.xaxis.range) == (0, 100)
    assert g.figura.layout.yaxis.autorange == "reversed"


def test_tamanho_na_ordem_das_faixas_e_com_n():
    g = painel.grafico_tamanho(dados_inventados()["tamanho_empresa"])
    assert list(g.figura.data[0].x) == ["1-5<br>n=162", "6-25<br>n=290", "Mais de 1000<br>n=282"]


def test_paises_na_ordem_do_ranking_com_nome_em_portugues_e_n():
    g = painel.grafico_paises(dados_inventados()["ranking_paises"])
    assert list(g.figura.data[0].y) == ["Estados Unidos (n=751)", "Wakanda (n=30)", "Reino Unido (n=185)"]


def test_interferencia_sem_resposta_aparece_com_nome_legivel():
    g = painel.grafico_interferencia(dados_inventados()["interferencia_trabalho"])
    assert list(g.figura.data[0].x) == ["Nunca", "Frequentemente", "Sem resposta"]
    assert list(g.figura.data[0].text) == ["16,9%", "11,4%", "21,0%"]


def test_consequencias_receio_e_disposicao_sao_barras_separadas_com_rotulo_que_diz_qual_e():
    g = painel.grafico_consequencias(dados_inventados()["consequencias_percebidas"])
    assert list(g.figura.data[0].y) == [
        "Receia consequência negativa · saúde mental", "Receia consequência negativa · saúde física",
        "Falaria numa entrevista · saúde mental", "Falaria numa entrevista · saúde física"]
    assert list(g.figura.data[0].x) == [23.2, 4.8, 3.5, 16.0]
    assert "duas perguntas diferentes" in g.nota


def test_barras_comecam_no_zero_e_percentual_vai_ate_100():
    d = dados_inventados()
    assert tuple(painel.grafico_genero(d["tratamento_por_genero"]).figura.layout.yaxis.range) == (0, 100)
    assert tuple(painel.grafico_tamanho(d["tamanho_empresa"]).figura.layout.yaxis.range) == (0, 100)
    assert painel.grafico_continentes(d["respostas_por_continente"]).figura.layout.xaxis.rangemode == "tozero"


def test_todos_usam_formato_brasileiro_nos_eixos():
    for g in painel.montar_graficos(dados_inventados()).values():
        assert g.figura.layout.separators == ",."


def test_aviso_diz_que_e_amostra_e_que_nao_separa_cientista_de_dados():
    assert "amostra" in painel.AVISO and "cientistas de dados" in painel.AVISO and "diagnóstico" in painel.AVISO



def test_nenhuma_nota_afirma_conclusao_pronta():
    for g in painel.montar_graficos(dados_inventados()).values():
        for proibido in ("prova que", "mostra que", "comprova", "demonstra"):
            assert proibido not in g.nota.lower(), g.id


def test_painel_nao_importa_streamlit():
    linhas = (painel.RAIZ / "painel.py").read_text(encoding="utf-8").splitlines()
    assert not any(l.strip().startswith(("import streamlit", "from streamlit")) for l in linhas)


# ---------------------------------------------------------------- leitura

@pytest.fixture
def banco_com_marts(tmp_path):
    caminho = tmp_path / "t.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    for nome in painel.MARTS:
        con.execute(f"CREATE TABLE marts.{nome} AS SELECT 1 AS x")
    con.close()
    return caminho


def test_ler_devolve_um_dataframe_por_mart(banco_com_marts):
    dados = painel.ler(caminho=banco_com_marts)
    assert set(dados) == set(painel.MARTS)
    assert all(len(df) == 1 for df in dados.values())


def test_ler_fecha_a_conexao_e_o_pipeline_ainda_consegue_gravar(banco_com_marts):
    painel.ler(caminho=banco_com_marts)
    con = duckdb.connect(str(banco_com_marts))  # se a leitura tivesse deixado aberta, falharia aqui
    con.execute("CREATE TABLE marts.novo AS SELECT 2 AS y")
    con.close()


def test_ler_fecha_a_conexao_mesmo_quando_falta_mart(banco_com_marts):
    con = duckdb.connect(str(banco_com_marts))
    con.execute("DROP TABLE marts.kpis")
    con.close()
    with pytest.raises(ErroPainel):
        painel.ler(caminho=banco_com_marts)
    con = duckdb.connect(str(banco_com_marts))  # gravável de novo
    con.close()


def test_ler_sem_banco_manda_rodar_o_pipeline(tmp_path):
    with pytest.raises(ErroPainel) as erro:
        painel.ler(caminho=tmp_path / "nao_existe.duckdb")
    assert "executar.py" in str(erro.value)


def test_ler_com_mart_faltando_diz_qual_e_o_comando(banco_com_marts):
    con = duckdb.connect(str(banco_com_marts))
    con.execute("DROP TABLE marts.kpis")
    con.execute("DROP TABLE marts.ranking_paises")
    con.close()
    with pytest.raises(ErroPainel) as erro:
        painel.ler(caminho=banco_com_marts)
    texto = str(erro.value)
    assert "kpis" in texto and "ranking_paises" in texto and "pipeline.marts" in texto


def test_ler_abre_somente_leitura(banco_com_marts, monkeypatch):
    chamadas = []
    original = duckdb.connect
    monkeypatch.setattr(duckdb, "connect", lambda *a, **k: chamadas.append(k) or original(*a, **k))
    painel.ler(caminho=banco_com_marts)
    assert chamadas[0].get("read_only") is True


def test_nenhum_calculo_no_codigo_do_painel():
    for nome in ("painel.py", "app.py", "relatorio.py"):
        codigo = (painel.RAIZ / nome).read_text(encoding="utf-8")
        for proibido in (".groupby(", ".sum(", ".mean(", ".merge(", ".pivot"):
            assert proibido not in codigo, f"{nome} usa {proibido}"
