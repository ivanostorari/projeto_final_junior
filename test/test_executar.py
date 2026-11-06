"""executar.py: ordem das etapas e banco apagado, sem rodar o pipeline de verdade."""

import pytest

import executar
from pipeline import db, ingestao, marts, transformacao


def espiar(monkeypatch, tmp_path, existe=True):
    caminho = tmp_path / "saude_mental.duckdb"
    if existe:
        caminho.write_text("velho")
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)
    chamadas = []
    for nome, modulo in [("ingestao", ingestao), ("transformacao", transformacao), ("marts", marts)]:
        monkeypatch.setattr(modulo, "main", lambda n=nome: chamadas.append((n, caminho.exists())))
    return caminho, chamadas


def test_apaga_o_banco_e_roda_as_tres_etapas_na_ordem(monkeypatch, tmp_path, capsys):
    _caminho, chamadas = espiar(monkeypatch, tmp_path)
    executar.main()
    assert chamadas == [("ingestao", False), ("transformacao", False), ("marts", False)]  # banco já apagado
    assert "apagado" in capsys.readouterr().out


def test_sem_banco_anterior_nao_reclama(monkeypatch, tmp_path, capsys):
    _, chamadas = espiar(monkeypatch, tmp_path, existe=False)
    executar.main()
    assert [c[0] for c in chamadas] == ["ingestao", "transformacao", "marts"]
    assert "apagado" not in capsys.readouterr().out


def test_se_uma_etapa_falha_as_seguintes_nao_rodam(monkeypatch, tmp_path):
    _, chamadas = espiar(monkeypatch, tmp_path)
    def quebra():
        raise SystemExit(1)
    monkeypatch.setattr(transformacao, "main", quebra)
    with pytest.raises(SystemExit):
        executar.main()
    assert [c[0] for c in chamadas] == ["ingestao"]
