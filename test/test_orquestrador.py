"""Integração: o pipeline completo (Bronze -> Silver -> Gold) com CSVs inventados e os .sql de verdade.

Nada aqui abre o saude_mental.duckdb nem lê raw/: tudo em tmp_path. As contagens esperadas saem da conta
sobre o conftest: 8 respostas à mão + 20 geradas (EUA) = 28 respostas, 6 países, 10 marts.
"""

import hashlib
import json
import os

import duckdb
import pytest

from pipeline import contrato, marts, orquestrador, qualidade, transformacao
from test.conftest import (
    COLUNAS_SURVEY,
    escrever_csv,
    escrever_entradas,
    resposta,
    respostas_do_pipeline,
)

TOTAL, PAISES = 28, 6
ETAPAS = ["pré-condições", "1 · ingestão", "1b · conciliação do raw", "2 · transformação",
          "2b · qualidade da Silver", "3 · marts", "3b · qualidade da Gold"]


@pytest.fixture
def ambiente(tmp_path):
    entrada = tmp_path / "entrada"
    escrever_entradas(entrada)
    return {"pasta_raw": entrada, "caminho_banco": tmp_path / "saude.duckdb", "pasta_logs": tmp_path / "logs"}


def rodar(ambiente, **extra):
    return orquestrador.rodar(**{**ambiente, **extra})


def consulta(banco, sql):
    con = duckdb.connect(str(banco), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def conteudo_dos_marts(banco):
    nomes = [n for (n,) in consulta(banco, "SELECT table_name FROM information_schema.tables "
                                           "WHERE table_schema = 'marts' ORDER BY 1")]
    return {n: consulta(banco, f"SELECT * FROM marts.{n} ORDER BY ALL") for n in nomes}


def etapas_por_nome(execucao):
    return {e["etapa"]: e for e in execucao.etapas}


# ---------- caminho feliz: Bronze -> Silver -> Gold ----------

def test_pipeline_completo_do_csv_ao_mart(ambiente):
    execucao = rodar(ambiente)
    banco = ambiente["caminho_banco"]
    assert execucao.status == "ok" and execucao.banco_publicado
    assert [e["etapa"] for e in execucao.etapas] == ETAPAS
    assert {e["status"] for e in execucao.etapas} == {"ok"}
    assert consulta(banco, "SELECT count(*) FROM raw.respostas") == [(TOTAL,)]
    assert consulta(banco, "SELECT count(*) FROM refined.respostas") == [(TOTAL,)]
    assert consulta(banco, "SELECT count(*) FROM refined.paises") == [(PAISES,)]
    assert consulta(banco, "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'marts'") == [(10,)]
    assert consulta(banco, "SELECT sum(respondentes) FROM marts.tamanho_empresa") == [(TOTAL,)]
    assert not (ambiente["caminho_banco"].parent / "saude.duckdb.novo").exists()


def test_contagens_por_etapa_fecham_entre_as_camadas(ambiente):
    etapas = etapas_por_nome(rodar(ambiente))
    assert (etapas["1 · ingestão"]["recebidas"], etapas["1 · ingestão"]["processadas"],
            etapas["1 · ingestão"]["rejeitadas"]) == (TOTAL + PAISES, TOTAL + PAISES, 0)
    transf = etapas["2 · transformação"]
    assert (transf["recebidas"], transf["processadas"], transf["rejeitadas"]) == (TOTAL + PAISES,) * 2 + (0,)
    assert transf["idades_anuladas"] == 2  # r4 (99999999999) e r7 (-5)
    marts_ = etapas["3 · marts"]
    assert (marts_["recebidas"], marts_["processadas"], marts_["rejeitadas"]) == (TOTAL, 10, 0)
    assert marts_["publicadas"] > 0


def test_rastreabilidade_no_banco_controle(ambiente):
    execucao = rodar(ambiente)
    banco = ambiente["caminho_banco"]
    assert consulta(banco, "SELECT execucao_id, status FROM controle.execucoes") == [(execucao.id, "ok")]
    assert len(consulta(banco, "SELECT * FROM controle.etapas")) == len(ETAPAS)
    esperado = hashlib.sha256((ambiente["pasta_raw"] / "survey.csv").read_bytes()).hexdigest()
    assert consulta(banco, "SELECT sha256, linhas FROM controle.arquivos_origem WHERE arquivo = 'survey.csv'") == [
        (esperado, TOTAL)]
    origens = consulta(banco, "SELECT origem FROM controle.linhagem WHERE destino = 'marts.ranking_paises' "
                              "ORDER BY 1")
    assert origens == [("refined.paises",), ("refined.respostas",)]
    assert consulta(banco, "SELECT origem FROM controle.linhagem WHERE destino = 'raw.respostas'") == [("survey.csv",)]
    assert consulta(banco, "SELECT count(*) FROM controle.qualidade WHERE NOT aprovada AND severidade = 'erro'") == [(0,)]


def test_arquivos_json_e_log_estruturado(ambiente):
    execucao = rodar(ambiente)
    pasta = ambiente["pasta_logs"] / "execucoes" / execucao.id
    resumo = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))
    assert resumo["status"] == "ok" and resumo["versao_pipeline"] == execucao.versao
    assert resumo["etapas"][1]["recebidas"] == TOTAL + PAISES
    assert resumo["arquivos_origem"][0]["sha256"] and resumo["linhagem"]
    relatorio = json.loads((pasta / "qualidade.json").read_text(encoding="utf-8"))
    assert relatorio["resumo"]["falhas_erro"] == 0 and relatorio["verificacoes"]

    eventos = [json.loads(linha) for linha in (ambiente["pasta_logs"] / "pipeline.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert {e["execucao_id"] for e in eventos} == {execucao.id}
    nomes = [e["evento"] for e in eventos]
    assert nomes[0] == "execucao_inicio" and nomes[-1] == "execucao_fim"
    assert nomes.count("etapa_inicio") == nomes.count("etapa_fim") == len(ETAPAS)
    assert all({"ts", "nivel", "evento", "execucao_id"} <= set(e) for e in eventos)
    fins = [e for e in eventos if e["evento"] == "etapa_fim"]
    assert all("duracao_s" in e and e["status"] == "ok" for e in fins)


def test_logs_e_banco_nao_levam_comentario_nem_resposta_individual(ambiente):
    segredo = "SEGREDO-COMENTARIO-123"
    escrever_entradas(ambiente["pasta_raw"], respostas=[resposta(comments=segredo)] * 1 + [
        resposta(Timestamp=f"2015-01-01 00:00:{i:02d}") for i in range(20)])
    execucao = rodar(ambiente)
    assert execucao.status == "ok"
    for arquivo in ambiente["pasta_logs"].rglob("*"):
        if arquivo.is_file():
            assert segredo not in arquivo.read_text(encoding="utf-8"), arquivo.name
    assert consulta(ambiente["caminho_banco"], f"SELECT count(*) FROM refined.respostas WHERE estado = '{segredo}'") == [(0,)]
    colunas = [c for (c,) in consulta(ambiente["caminho_banco"], "SELECT column_name FROM information_schema.columns "
                                      "WHERE table_schema = 'refined'")]
    assert "comments" not in colunas


# ---------- idempotência ----------

def test_duas_execucoes_seguidas_dao_o_mesmo_resultado(ambiente):
    primeira = rodar(ambiente)
    antes = conteudo_dos_marts(ambiente["caminho_banco"])
    contagem = consulta(ambiente["caminho_banco"], "SELECT count(*) FROM refined.respostas")
    segunda = rodar(ambiente)
    assert primeira.id != segunda.id and segunda.status == "ok"
    assert conteudo_dos_marts(ambiente["caminho_banco"]) == antes
    assert consulta(ambiente["caminho_banco"], "SELECT count(*) FROM refined.respostas") == contagem
    assert consulta(ambiente["caminho_banco"], "SELECT execucao_id FROM controle.execucoes") == [(segunda.id,)]
    ids = {json.loads(l)["execucao_id"] for l in (ambiente["pasta_logs"] / "pipeline.jsonl").read_text(
        encoding="utf-8").splitlines()}
    assert ids == {primeira.id, segunda.id}  # o histórico acumula; o banco guarda só a execução que o gerou


# ---------- falhas: banco anterior intacto, etapas seguintes não executadas ----------

def bytes_do_banco(ambiente):
    return ambiente["caminho_banco"].read_bytes()


def confere_falha_limpa(ambiente, execucao, primeira_que_falhou, antes):
    etapas = etapas_por_nome(execucao)
    assert execucao.status == "falhou" and not execucao.banco_publicado
    assert etapas[primeira_que_falhou]["status"] == "falhou"
    depois = ETAPAS[ETAPAS.index(primeira_que_falhou) + 1:]
    assert [etapas[n]["status"] for n in depois] == ["nao_executada"] * len(depois)
    assert bytes_do_banco(ambiente) == antes  # o banco da última execução boa não foi tocado
    assert not list(ambiente["caminho_banco"].parent.glob("*.novo*"))
    resumo = json.loads((ambiente["pasta_logs"] / "execucoes" / execucao.id / "execucao.json").read_text(encoding="utf-8"))
    assert resumo["status"] == "falhou" and resumo["banco_publicado"] is False


def test_simulacao_de_falha_no_meio_nao_destroi_o_banco_anterior(ambiente, monkeypatch, capsys):
    assert rodar(ambiente).status == "ok"
    antes = bytes_do_banco(ambiente)

    def quebra(con, pasta=None):
        con.execute("CREATE SCHEMA marts")  # deixa lixo no banco em construção antes de falhar
        raise duckdb.Error("falha simulada")

    monkeypatch.setattr(marts, "executar", quebra)
    execucao = rodar(ambiente)
    confere_falha_limpa(ambiente, execucao, "3 · marts", antes)
    assert etapas_por_nome(execucao)["3 · marts"]["erro_tipo"] == "Error"
    assert "Erro do DuckDB: falha simulada" in capsys.readouterr().out


def test_erro_inesperado_vira_falha_registrada_e_nao_traceback(ambiente, monkeypatch, capsys):
    assert rodar(ambiente).status == "ok"
    antes = bytes_do_banco(ambiente)
    monkeypatch.setattr(transformacao, "transformar", lambda con: (_ for _ in ()).throw(RuntimeError("boom")))
    execucao = rodar(ambiente)
    confere_falha_limpa(ambiente, execucao, "2 · transformação", antes)
    assert "Erro inesperado (RuntimeError): boom" in capsys.readouterr().out


def test_erro_de_transformacao_propria_e_tratado(ambiente):
    # 'Age' que não é número: a transformação é estrita e para (sem TRY_CAST)
    escrever_entradas(ambiente["pasta_raw"], respostas=[resposta(Age="abc")] + [
        resposta(Timestamp=f"2015-01-01 00:00:{i:02d}") for i in range(20)])
    execucao = rodar(ambiente)
    assert execucao.status == "falhou"
    assert etapas_por_nome(execucao)["2 · transformação"]["status"] == "falhou"
    assert not ambiente["caminho_banco"].exists()  # primeira execução que falha: nada é publicado


def test_falha_ao_trocar_o_banco_mantem_o_anterior(ambiente, monkeypatch, capsys):
    assert rodar(ambiente).status == "ok"
    antes = bytes_do_banco(ambiente)

    def nega(origem, destino):
        raise PermissionError("em uso")

    monkeypatch.setattr(os, "replace", nega)
    execucao = rodar(ambiente)
    assert execucao.status == "falhou" and not execucao.banco_publicado
    assert bytes_do_banco(ambiente) == antes and not list(ambiente["caminho_banco"].parent.glob("*.novo*"))
    assert "Feche o painel" in capsys.readouterr().out


def test_sobra_de_execucao_interrompida_e_removida(ambiente):
    sobra = ambiente["caminho_banco"].with_name("saude.duckdb.novo")
    sobra.write_text("lixo")
    assert rodar(ambiente).status == "ok" and not sobra.exists()


# ---------- arquivos de entrada ruins ----------

@pytest.mark.parametrize(
    "preparar",
    [
        lambda pasta: (pasta / "paises.csv").unlink(),
        lambda pasta: (pasta / "survey.csv").write_text("", encoding="utf-8"),
        lambda pasta: escrever_csv(pasta / "survey.csv", COLUNAS_SURVEY, []),
        lambda pasta: (pasta / "survey.csv").write_bytes("Timestamp,Age\n2014,ç\n".encode("latin-1")),
        lambda pasta: escrever_csv(pasta / "survey.csv", COLUNAS_SURVEY[:-1], [{}]),
        lambda pasta: (pasta / "paises.csv").write_text("name_short,name_official,ISO3,continent,UNregion\nA,B\n"),
    ],
    ids=["ausente", "vazio", "so-cabecalho", "encoding", "coluna-faltando", "linha-quebrada"],
)
def test_entradas_invalidas_param_nas_precondicoes(ambiente, preparar):
    preparar(ambiente["pasta_raw"])
    execucao = rodar(ambiente)
    etapas = etapas_por_nome(execucao)
    assert execucao.status == "falhou" and etapas["pré-condições"]["status"] == "falhou"
    assert {e["status"] for n, e in etapas.items() if n != "pré-condições"} == {"nao_executada"}
    assert not ambiente["caminho_banco"].exists()
    assert qualidade.bloqueia(execucao.verificacoes)


def test_chave_de_paises_duplicada_para_nas_precondicoes(ambiente):
    caminho = ambiente["pasta_raw"] / "paises.csv"
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    caminho.write_text("\n".join([*linhas, linhas[1]]) + "\n", encoding="utf-8")
    execucao = rodar(ambiente)
    assert execucao.status == "falhou"
    assert "name_short não se repete" in " ".join(v.regra for v in qualidade.falhas(execucao.verificacoes, qualidade.ERRO))


def test_linhas_repetidas_e_coluna_extra_sao_aviso_e_o_pipeline_segue(ambiente):
    repetida = resposta(Timestamp="2015-02-02 00:00:00")
    escrever_csv(ambiente["pasta_raw"] / "survey.csv", [*COLUNAS_SURVEY, "extra"],
                 [{**r, "extra": "1"} for r in respostas_do_pipeline() + [repetida, repetida]])
    execucao = rodar(ambiente)
    assert execucao.status == "ok"
    avisos = {v.regra for v in qualidade.falhas(execucao.verificacoes, qualidade.AVISO)}
    assert "survey.csv: sem linhas 100% repetidas" in avisos
    assert "survey.csv: não tem colunas além das esperadas" in avisos
    assert consulta(ambiente["caminho_banco"], "SELECT count(*) FROM raw.respostas") == [(TOTAL + 2,)]


def test_pasta_de_sql_vazia_e_pasta_do_banco_inexistente_sao_precondicoes(ambiente, tmp_path):
    vazia = tmp_path / "sql_vazio"
    vazia.mkdir()
    execucao = rodar(ambiente, pasta_sql=vazia)
    assert execucao.status == "falhou" and etapas_por_nome(execucao)["pré-condições"]["status"] == "falhou"
    execucao = rodar(ambiente, caminho_banco=tmp_path / "nao_existe" / "x.duckdb")
    assert execucao.status == "falhou" and etapas_por_nome(execucao)["pré-condições"]["status"] == "falhou"


# ---------- bloqueio por qualidade ----------

def forcar_erro(camada):
    return [qualidade.Verificacao(camada, "validade", "regra forçada", qualidade.ERRO, False, "1", "0")]


def test_silver_reprovada_impede_os_marts(ambiente, monkeypatch):
    assert rodar(ambiente).status == "ok"
    antes = bytes_do_banco(ambiente)
    monkeypatch.setattr(qualidade, "verificar_silver", lambda con: forcar_erro("refined"))
    chamadas = []
    monkeypatch.setattr(marts, "executar", lambda *a, **k: chamadas.append(1))
    execucao = rodar(ambiente)
    confere_falha_limpa(ambiente, execucao, "2b · qualidade da Silver", antes)
    assert chamadas == []  # a Gold nem começou


def test_gold_reprovada_nao_e_publicada(ambiente, monkeypatch):
    assert rodar(ambiente).status == "ok"
    antes = bytes_do_banco(ambiente)
    monkeypatch.setattr(qualidade, "verificar_gold", lambda con, nomes: forcar_erro("marts"))
    execucao = rodar(ambiente)
    confere_falha_limpa(ambiente, execucao, "3b · qualidade da Gold", antes)


def test_mart_com_percentual_impossivel_e_barrado_pela_qualidade_da_gold(ambiente, tmp_path):
    pasta = tmp_path / "sql"
    pasta.mkdir()
    (pasta / "01_ruim.sql").write_text(
        "SELECT count(*) AS respondentes, 150.0 AS pct_impossivel FROM refined.respostas;", encoding="utf-8")
    execucao = rodar(ambiente, pasta_sql=pasta)
    assert execucao.status == "falhou" and not ambiente["caminho_banco"].exists()
    assert etapas_por_nome(execucao)["3b · qualidade da Gold"]["status"] == "falhou"
    assert "colunas pct_* entre 0 e 100" in {v.regra for v in qualidade.falhas(execucao.verificacoes)}


def test_mart_que_particiona_e_nao_fecha_com_refined_e_barrado(ambiente, tmp_path):
    pasta = tmp_path / "sql"
    pasta.mkdir()
    (pasta / "01_respostas_por_continente.sql").write_text(
        "SELECT 'x' AS continente, 1 AS respondentes FROM refined.respostas LIMIT 1;", encoding="utf-8")
    execucao = rodar(ambiente, pasta_sql=pasta)
    assert execucao.status == "falhou"
    assert any("soma de respondentes" in v.regra for v in qualidade.falhas(execucao.verificacoes, qualidade.ERRO))


def test_mart_sem_linhas_continua_sendo_erro_de_marts(ambiente, tmp_path):
    pasta = tmp_path / "sql"
    pasta.mkdir()
    (pasta / "01_vazio.sql").write_text("SELECT 1 AS respondentes WHERE false;", encoding="utf-8")
    execucao = rodar(ambiente, pasta_sql=pasta)
    assert execucao.status == "falhou" and etapas_por_nome(execucao)["3 · marts"]["status"] == "falhou"


# ---------- resumo e log ----------

def test_resumo_impresso_mostra_etapas_e_destino_do_banco(ambiente, capsys):
    execucao = rodar(ambiente)
    orquestrador.imprimir_resumo(execucao)
    saida = capsys.readouterr().out
    assert execucao.id in saida and "banco novo publicado" in saida and "3b · qualidade da Gold" in saida
    escrever_csv(ambiente["pasta_raw"] / "survey.csv", COLUNAS_SURVEY, [])
    orquestrador.imprimir_resumo(rodar(ambiente))
    assert "banco anterior mantido" in capsys.readouterr().out


def test_log_que_nao_pode_ser_gravado_avisa_mas_nao_derruba_o_pipeline(ambiente, tmp_path, capsys):
    arquivo = tmp_path / "isto_e_um_arquivo"
    arquivo.write_text("x")
    execucao = rodar(ambiente, pasta_logs=arquivo)  # pasta_logs apontando para um arquivo
    assert execucao.status == "ok" and execucao.aviso_log
    orquestrador.imprimir_resumo(execucao)
    assert "aviso:" in capsys.readouterr().out


def test_versao_vem_do_pyproject_e_tem_fallback(monkeypatch, tmp_path):
    from pipeline import db, execucao
    assert execucao.versao_pipeline() == "0.1.0"
    monkeypatch.setattr(db, "RAIZ", tmp_path)
    assert execucao.versao_pipeline() == "desconhecida"


def test_contrato_exporta_as_colunas_que_a_ingestao_espera():
    assert contrato.SURVEY == COLUNAS_SURVEY
