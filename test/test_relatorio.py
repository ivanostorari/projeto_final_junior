"""relatorio.py: o HTML congelado, com dados inventados e data fixa."""

import json
import re
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
    assert html.count("<h2>") == 4  # três faixas de gráficos e "Sobre os dados"
    assert html.count('class="faixa"') == 3


def test_menu_aponta_para_secoes_que_existem():
    html = relatorio.montar_html(dados_inventados(), AGORA)
    for ancora in ("numeros", "quem", "empregador", "conversa", "sobre"):
        assert f'href="#{ancora}"' in html
        assert f'id="{ancora}"' in html


def test_titulo_do_grafico_vai_para_a_pagina_e_sai_de_dentro_do_grafico():
    html = relatorio.montar_html(dados_inventados(), AGORA)
    assert html.count('class="titulo-grafico"') == 8
    # a pergunta fica antes do " · " e a unidade, em <span>, depois
    assert '<h3 class="titulo-grafico">Quem respondeu <span>· respostas por continente</span></h3>' in html


def test_pagina_se_adapta_ao_celular_e_ao_tema_escuro():
    html = relatorio.montar_html(dados_inventados(), AGORA)
    assert 'name="viewport"' in html
    assert "@media (max-width:700px)" in html
    assert "prefers-color-scheme:dark" in html


def test_sem_internet_a_pagina_avisa_que_o_plotly_nao_carregou():
    html = relatorio.montar_html(dados_inventados(), AGORA)
    assert 'id="sem-plotly" hidden' in html


def test_arquivo_continua_abaixo_de_200_kb():
    assert len(relatorio.montar_html(dados_inventados(), AGORA).encode("utf-8")) < 200 * 1024


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


def _dados_da_pagina(html: str) -> dict:
    bruto = re.search(r'id="dados-graficos">(.*?)</script>', html, re.DOTALL).group(1)
    return json.loads(bruto.replace("<\\/", "</"))


def test_detalhe_tem_os_oito_graficos_e_copia_o_que_o_grafico_desenha():
    dados = dados_inventados()
    detalhes = _dados_da_pagina(relatorio.montar_html(dados, AGORA))
    assert sorted(detalhes) == [f"g{i:02d}" for i in range(1, 9)]
    graficos = painel.montar_graficos(dados)
    continentes = detalhes["g01"]["pontos"]
    traco = graficos["continente"].figura.data[0]
    assert [p["rotulo"] for p in continentes] == list(traco.y)
    assert [p["valor"] for p in continentes] == list(traco.text)
    assert detalhes["g01"]["pergunta"] == "Quem respondeu"
    assert detalhes["g01"]["faixa"] == "Quem respondeu, e quem buscou tratamento"


def test_detalhe_de_barra_vertical_usa_o_rotulo_do_eixo_x_sem_br():
    detalhes = _dados_da_pagina(relatorio.montar_html(dados_inventados(), AGORA))
    rotulos = [p["rotulo"] for p in detalhes["g02"]["pontos"]]  # gênero: "Homem<br>n=..." no gráfico
    assert rotulos and all("<br>" not in r and " · n=" in r for r in rotulos)


def test_detalhe_traz_a_dica_so_onde_o_grafico_tem_dica():
    detalhes = _dados_da_pagina(relatorio.montar_html(dados_inventados(), AGORA))
    assert all(p["detalhe"] for p in detalhes["g04"]["pontos"])  # apoio do empregador tem dica em cada barra
    assert not any(p["detalhe"] for p in detalhes["g01"]["pontos"])  # continentes não tem


def test_tela_de_detalhe_tem_voltar_e_inicio():
    html = relatorio.montar_html(dados_inventados(), AGORA)
    assert 'id="detalhe"' in html
    assert 'id="voltar"' in html
    assert html.count("data-home") >= 3  # marca, menu e tela de detalhe
    assert "Clique em uma barra" in html


def test_nenhum_texto_dos_dados_consegue_fechar_o_script_da_pagina(monkeypatch):
    normal = relatorio.montar_html(dados_inventados(), AGORA).count("</script>")
    monkeypatch.setattr(
        relatorio, "_pontos", lambda fig: [{"rotulo": "</script><b>x", "valor": "1", "detalhe": ""}]
    )
    html = relatorio.montar_html(dados_inventados(), AGORA)
    assert html.count("</script>") == normal
    assert _dados_da_pagina(html)["g01"]["pontos"][0]["rotulo"] == "</script><b>x"
