"""app.py (Streamlit) rodado sem navegador, com o painel.ler trocado por dados inventados."""

import pytest
from streamlit.testing.v1 import AppTest

import painel
from test.test_painel import dados_inventados


@pytest.fixture(autouse=True)
def limpar_cache():
    import streamlit as st
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def abrir(monkeypatch, ler):
    monkeypatch.setattr(painel, "ler", ler)
    return AppTest.from_file(str(painel.RAIZ / "app.py"), default_timeout=30).run()


def test_pagina_abre_sem_excecao_com_seis_cartoes_e_o_aviso(monkeypatch):
    app = abrir(monkeypatch, dados_inventados)
    assert not app.exception
    assert [m.value for m in app.metric] == ["1.259", "50,6%", "39,1%", "37,9%", "23,2%", "41,0%"]
    assert "amostra" in app.info[0].value
    assert [s.value for s in app.subheader] == [
        "Quem respondeu, e quem buscou tratamento", "O que o empregador oferece", "Falar abertamente sobre o assunto"]


def test_erro_de_leitura_aparece_como_mensagem_e_nada_mais_e_desenhado(monkeypatch):
    def falha():
        raise painel.ErroPainel("O banco saude_mental.duckdb não existe.")
    app = abrir(monkeypatch, falha)
    assert not app.exception
    assert "não existe" in app.error[0].value
    assert len(app.metric) == 0


def test_botao_recarregar_le_de_novo(monkeypatch):
    chamadas = []

    def ler():
        chamadas.append(1)
        return dados_inventados()
    app = abrir(monkeypatch, ler)
    app.run()
    assert len(chamadas) == 1  # a segunda execução vem do cache
    app.button[0].click().run()
    assert len(chamadas) == 2
    assert not app.exception
