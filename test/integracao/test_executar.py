"""executar.py: código de saída e arquivos criados, com CSVs inventados em tmp_path."""

import pytest

import executar
from pipeline import db
from test.conftest import escrever_entradas

pytestmark = pytest.mark.integracao  # roda o pipeline completo (em tmp_path): fora dos testes unitários


@pytest.fixture
def pastas(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "PASTA_RAW", tmp_path / "raw")
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "saude_mental.duckdb")
    monkeypatch.setattr(db, "PASTA_LOGS", tmp_path / "logs")
    return tmp_path


def test_sucesso_publica_o_banco_e_escreve_o_resumo(pastas, capsys):
    escrever_entradas(pastas / "raw")
    executar.main()  # sem SystemExit
    saida = capsys.readouterr().out
    assert (pastas / "saude_mental.duckdb").exists() and "banco novo publicado" in saida
    assert list((pastas / "logs" / "execucoes").glob("*/execucao.json"))


def test_falha_sai_com_codigo_1_e_nao_cria_banco(pastas, capsys):
    (pastas / "raw").mkdir()  # sem os CSVs
    with pytest.raises(SystemExit) as erro:
        executar.main()
    assert erro.value.code == 1
    assert not (pastas / "saude_mental.duckdb").exists()
    assert "banco anterior mantido" in capsys.readouterr().out
