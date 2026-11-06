"""ver_marts.py: só imprime o que painel.ler() entrega, com dados inventados."""

import pandas as pd
import pytest

import painel
import ver_marts
from test.test_painel import dados_inventados


@pytest.fixture
def com_dados(monkeypatch):
    monkeypatch.setattr(painel, "ler", dados_inventados)


def test_sem_argumento_imprime_os_dez_marts_na_ordem(com_dados, capsys):
    ver_marts.main([])
    saida = capsys.readouterr().out
    posicoes = [saida.index(f"== marts.{m} ") for m in painel.MARTS]
    assert posicoes == sorted(posicoes)  # a ordem de painel.MARTS
    assert saida.count("== marts.") == 10


def test_com_argumento_imprime_so_aquele_mart_com_a_contagem(com_dados, capsys):
    ver_marts.main(["kpis"])
    saida = capsys.readouterr().out
    assert saida.count("== marts.") == 1
    assert "== marts.kpis  (1 linhas)" in saida and "1259" in saida


def test_mart_inexistente_sai_com_codigo_1_e_lista_os_validos(com_dados, capsys):
    with pytest.raises(SystemExit) as saida:
        ver_marts.main(["nao_existe"])
    assert saida.value.code == 1
    texto = capsys.readouterr().out
    assert "nao_existe" in texto and "ranking_paises" in texto


def test_sem_banco_sai_com_codigo_1(monkeypatch, capsys):
    def falha():
        raise painel.ErroPainel("sem banco")
    monkeypatch.setattr(painel, "ler", falha)
    with pytest.raises(SystemExit) as saida:
        ver_marts.main([])
    assert saida.value.code == 1
    assert "sem banco" in capsys.readouterr().out


def test_formatar_nao_imprime_o_indice():
    texto = ver_marts.formatar(pd.DataFrame({"a": [1, 2]}))
    assert texto.splitlines()[0].strip() == "a" and "0" not in texto.splitlines()[1]
