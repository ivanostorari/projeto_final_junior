"""app.py (Streamlit) rodado sem navegador, com o painel.ler trocado por dados inventados."""

import pytest
from streamlit.testing.v1 import AppTest

import painel
from pipeline import orquestrador
from test.test_painel import dados_inventados


@pytest.fixture(autouse=True)
def limpar_cache(monkeypatch, tmp_path):
    import streamlit as st
    st.cache_data.clear()
    st.cache_resource.clear()
    # banco "existente" por padrão: os testes não rodam o pipeline de verdade
    banco = tmp_path / "saude_mental.duckdb"
    banco.write_text("")
    monkeypatch.setattr(painel, "CAMINHO_BANCO", banco)
    yield
    st.cache_data.clear()
    st.cache_resource.clear()


class ExecucaoFalsa:
    def __init__(self, status, etapas=()):
        self.status, self.etapas = status, list(etapas)


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


def test_sem_banco_a_pagina_roda_o_pipeline_uma_vez_e_depois_mostra_os_dados(monkeypatch, tmp_path):
    painel.CAMINHO_BANCO.unlink()
    chamadas = []

    def rodar(**kwargs):
        chamadas.append(kwargs)
        painel.CAMINHO_BANCO.write_text("")
        return ExecucaoFalsa("ok")

    monkeypatch.setattr(orquestrador, "rodar", rodar)
    app = abrir(monkeypatch, dados_inventados)
    app.run()
    assert not app.exception and len(app.metric) == 6
    assert chamadas == [{"caminho_banco": painel.CAMINHO_BANCO}]  # só na primeira abertura


def test_com_banco_existente_o_pipeline_nao_roda(monkeypatch):
    monkeypatch.setattr(orquestrador, "rodar", lambda **k: pytest.fail("não deveria rodar"))
    app = abrir(monkeypatch, dados_inventados)
    assert not app.exception and len(app.metric) == 6


def test_falha_ao_preparar_os_dados_mostra_a_etapa_e_para(monkeypatch):
    painel.CAMINHO_BANCO.unlink()
    falha = ExecucaoFalsa("falhou", [{"etapa": "2 · transformação", "status": "falhou"}])
    monkeypatch.setattr(orquestrador, "rodar", lambda **k: falha)
    app = abrir(monkeypatch, dados_inventados)
    assert not app.exception and len(app.metric) == 0
    assert "2 · transformação" in app.error[0].value
