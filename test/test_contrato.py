"""Contrato dos CSVs de entrada (pipeline/contrato.py): cada violação é pega e tem severidade certa."""

import hashlib

from pipeline import contrato
from pipeline.qualidade import AVISO, ERRO, bloqueia, falhas
from test.conftest import COLUNAS_SURVEY, PAISES, escrever_csv, escrever_entradas, resposta


def regras_que_falharam(verificacoes, severidade=None):
    return [v.regra for v in falhas(verificacoes, severidade)]


def test_entrada_boa_passa_em_tudo_e_conta_as_linhas(tmp_path):
    escrever_entradas(tmp_path)
    verificacoes, linhas = contrato.verificar(tmp_path)
    assert falhas(verificacoes) == []
    assert linhas == {"survey.csv": 28, "paises.csv": 6}


def test_arquivo_ausente_e_erro(tmp_path):
    escrever_entradas(tmp_path)
    (tmp_path / "paises.csv").unlink()
    verificacoes, linhas = contrato.verificar(tmp_path)
    assert regras_que_falharam(verificacoes, ERRO) == ["paises.csv: arquivo existe"]
    assert linhas["paises.csv"] is None and bloqueia(verificacoes)


def test_arquivo_totalmente_vazio_e_so_cabecalho_sao_erro(tmp_path):
    escrever_entradas(tmp_path)
    (tmp_path / "survey.csv").write_text("", encoding="utf-8")
    escrever_csv(tmp_path / "paises.csv", contrato.PAISES, [])
    verificacoes, linhas = contrato.verificar(tmp_path)
    assert regras_que_falharam(verificacoes, ERRO) == [
        "survey.csv: cabeçalho e pelo menos 1 linha de dados",
        "paises.csv: cabeçalho e pelo menos 1 linha de dados",
    ]
    assert linhas == {"survey.csv": 0, "paises.csv": 0}


def test_arquivo_que_nao_e_utf8_e_erro(tmp_path):
    escrever_entradas(tmp_path)
    (tmp_path / "survey.csv").write_bytes("Timestamp,Age\n2014,ç\n".encode("latin-1"))
    verificacoes, _ = contrato.verificar(tmp_path)
    assert regras_que_falharam(verificacoes, ERRO) == ["survey.csv: codificação UTF-8 legível"]


def test_coluna_faltando_e_erro_e_diz_qual(tmp_path):
    escrever_entradas(tmp_path)
    colunas = [c for c in COLUNAS_SURVEY if c != "Gender"]
    escrever_csv(tmp_path / "survey.csv", colunas, [{c: "x" for c in colunas}])
    verificacoes, _ = contrato.verificar(tmp_path)
    falha = falhas(verificacoes, ERRO)[0]
    assert falha.regra == "survey.csv: tem todas as colunas obrigatórias"
    assert "Gender" in falha.detalhe


def test_coluna_a_mais_e_so_aviso(tmp_path):
    escrever_entradas(tmp_path)
    colunas = [*COLUNAS_SURVEY, "extra"]
    escrever_csv(tmp_path / "survey.csv", colunas, [{**resposta(), "extra": "1"}])
    verificacoes, _ = contrato.verificar(tmp_path)
    assert regras_que_falharam(verificacoes, AVISO) == ["survey.csv: não tem colunas além das esperadas"]
    assert not bloqueia(verificacoes)


def test_nome_de_coluna_repetido_e_erro(tmp_path):
    escrever_entradas(tmp_path)
    (tmp_path / "paises.csv").write_text(
        "name_short,name_official,ISO3,continent,UNregion,ISO3\nA,B,C,D,E,F\n", encoding="utf-8")
    verificacoes, _ = contrato.verificar(tmp_path)
    assert "paises.csv: nomes de coluna não se repetem" in regras_que_falharam(verificacoes, ERRO)


def test_linha_com_campos_a_mais_ou_a_menos_e_erro(tmp_path):
    escrever_entradas(tmp_path)
    (tmp_path / "paises.csv").write_text(
        "name_short,name_official,ISO3,continent,UNregion\nA,B,C,D,E\nsó,três,campos\n", encoding="utf-8")
    verificacoes, _ = contrato.verificar(tmp_path)
    assert regras_que_falharam(verificacoes, ERRO) == [
        "paises.csv: toda linha tem o mesmo número de campos do cabeçalho"]


def test_linha_em_branco_nao_conta_como_linha_de_dados(tmp_path):
    escrever_entradas(tmp_path)
    with (tmp_path / "paises.csv").open("a", encoding="utf-8") as arquivo:
        arquivo.write("\n\n")
    verificacoes, linhas = contrato.verificar(tmp_path)
    assert falhas(verificacoes) == [] and linhas["paises.csv"] == 6


def test_linhas_100_por_cento_repetidas_sao_aviso(tmp_path):
    escrever_entradas(tmp_path, respostas=[resposta(), resposta()])
    verificacoes, linhas = contrato.verificar(tmp_path)
    assert regras_que_falharam(verificacoes) == ["survey.csv: sem linhas 100% repetidas"]
    assert regras_que_falharam(verificacoes, AVISO) and linhas["survey.csv"] == 2


def test_chave_repetida_em_paises_e_erro(tmp_path):
    escrever_entradas(tmp_path, paises=[*PAISES, PAISES[0]])
    verificacoes, _ = contrato.verificar(tmp_path)
    erros = regras_que_falharam(verificacoes, ERRO)
    assert erros == ["paises.csv: name_short não se repete"]


def test_sha256_confere_com_o_hashlib(tmp_path):
    escrever_entradas(tmp_path)
    arquivo = tmp_path / "survey.csv"
    assert contrato.sha256(arquivo) == hashlib.sha256(arquivo.read_bytes()).hexdigest()
