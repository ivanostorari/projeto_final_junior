"""relatorio.py: o HTML congelado, com dados inventados e data fixa."""

from datetime import datetime

import pytest

import painel
import relatorio
from test.test_painel import dados_inventados

AGORA = datetime(2026, 3, 15, 9, 5)


def test_html_tem_os_oito_graficos_com_id_fixo():
    html = relatorio.montar_html(dados_inventados(), AGORA)
    for i in range(1, 9):
        assert f'id="g{i:02d}"' in html
    assert 'id="g09"' not in html


def test_mesmos_dados_e_mesma_data_geram_o_mesmo_arquivo():
    assert relatorio.montar_html(dados_inventados(), AGORA) == relatorio.montar_html(dados_inventados(), AGORA)


def test_rodape_diz_a_data_e_hora_da_geracao():
    assert "Dados de 15/03/2026 09:05" in relatorio.montar_html(dados_inventados(), AGORA)


def test_plotly_vem_do_cdn_uma_vez_so():
    assert relatorio.montar_html(dados_inventados(), AGORA).count("cdn.plot.ly") == 1


def test_tem_os_seis_cartoes_o_aviso_da_amostra_e_as_tres_faixas():
    html = relatorio.montar_html(dados_inventados(), AGORA)
    assert html.count('class="cartao"') == 6
    assert "1.259" in html
    assert "amostra de quem quis responder" in html
    assert html.count("<h2>") == 3


def test_main_grava_o_arquivo_e_avisa(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(painel, "ler", dados_inventados)
    monkeypatch.setattr(relatorio, "SAIDA", tmp_path / "r.html")
    relatorio.main()
    assert (tmp_path / "r.html").read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "✓ r.html" in capsys.readouterr().out


def test_main_sem_banco_sai_com_codigo_1_e_nao_cria_arquivo(tmp_path, monkeypatch, capsys):
    def falha():
        raise painel.ErroPainel("sem banco")
    monkeypatch.setattr(painel, "ler", falha)
    monkeypatch.setattr(relatorio, "SAIDA", tmp_path / "r.html")
    with pytest.raises(SystemExit) as saida:
        relatorio.main()
    assert saida.value.code == 1
    assert not (tmp_path / "r.html").exists()
    assert "sem banco" in capsys.readouterr().out
