"""Orquestrador: roda o pipeline inteiro, em ordem, com parada, rastreabilidade e qualidade.

Spec completa em specs/operacao.md. Resumo do que garante:

1. ORDEM E DEPENDÊNCIA. pré-condições -> ingestão -> conciliação do raw -> transformação ->
   qualidade da Silver -> marts -> qualidade da Gold. Se uma etapa falha, as seguintes
   ficam `nao_executada` (registradas, não omitidas).
2. BLOQUEIO. Falha de qualidade com severidade `erro` na Silver impede os marts; na Gold, apaga o schema
   `marts` do banco em construção. Em qualquer falha o banco em construção NÃO é publicado.
3. REEXECUÇÃO SEGURA. O banco novo nasce em `<banco>.novo` e só substitui o anterior se tudo deu certo.
4. RASTREABILIDADE. execução, arquivos (SHA-256), etapas (contagens, tempos), linhagem e qualidade vão
   para o schema `controle` e para logs/.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import duckdb

from pipeline import contrato, db, execucao, ingestao, marts, qualidade, transformacao
from pipeline.saida import milhar


class ErroDePipeline(Exception):
    """Falha prevista (pré-condição, qualidade) com mensagem para o humano."""


def _bloquear(verificacoes, titulo: str) -> None:
    qualidade.imprimir(titulo, verificacoes)
    if qualidade.bloqueia(verificacoes):
        regras = "; ".join(v.regra for v in qualidade.falhas(verificacoes, qualidade.ERRO))
        raise ErroDePipeline(f"Qualidade reprovada ({titulo}): {regras}")


def _contar(registro: dict, recebidas, processadas, publicadas) -> None:
    registro.update(recebidas=recebidas, processadas=processadas,
                    rejeitadas=recebidas - processadas, publicadas=publicadas)


def _linhagem(ctx) -> list[dict]:
    itens = [{"destino": f"raw.{tabela}", "origem": arquivo} for arquivo, (tabela, _) in ingestao.ARQUIVOS.items()]
    itens += [{"destino": f"refined.{t}", "origem": f"raw.{t}"} for t in transformacao.TABELAS]
    for arquivo, nome in marts.listar_arquivos(ctx.pasta_sql):
        for origem in marts.dependencias(arquivo.read_text(encoding="utf-8")):
            itens.append({"destino": f"marts.{nome}", "origem": origem})
    return itens


def _precondicoes(ctx, registro) -> None:
    verificacoes, linhas = contrato.verificar(ctx.pasta_raw)
    ctx.exec.registrar_verificacoes(verificacoes)
    for arquivo in contrato.CONTRATOS:
        caminho = ctx.pasta_raw / arquivo
        if caminho.is_file():
            ctx.exec.arquivos.append({"arquivo": arquivo, "sha256": contrato.sha256(caminho),
                                      "bytes": caminho.stat().st_size, "linhas": linhas[arquivo]})
    _bloquear(verificacoes, "contrato dos CSVs")
    ctx.linhas_csv = linhas
    ctx.exec.linhagem = _linhagem(ctx)  # também valida os nomes dos .sql antes de tocar no banco
    if not ctx.novo.parent.is_dir():
        raise ErroDePipeline(f"A pasta do banco não existe: {ctx.novo.parent}")
    ctx.con = duckdb.connect(str(ctx.novo))
    _contar(registro, sum(linhas.values()), sum(linhas.values()), 0)


def _ingestao(ctx, registro) -> None:
    resultados = ingestao.ingerir(ctx.con, ctx.pasta_raw)
    ingestao.imprimir(resultados)
    gravadas = sum(n for _, n in resultados)
    _contar(registro, sum(ctx.linhas_csv.values()), gravadas, gravadas)


def _conciliar_raw(ctx, registro) -> None:
    verificacoes = qualidade.conciliar_raw(ctx.con, ctx.linhas_csv)
    ctx.exec.registrar_verificacoes(verificacoes)
    _bloquear(verificacoes, "conciliação CSV -> raw")
    total = sum(ctx.linhas_csv.values())
    _contar(registro, total, total, total)


def _transformacao(ctx, registro) -> None:
    resultados = transformacao.transformar(ctx.con)
    transformacao.imprimir(resultados)
    entrada, saida = sum(r["entrada"] for r in resultados), sum(r["saida"] for r in resultados)
    _contar(registro, entrada, saida, saida)
    registro["idades_anuladas"] = sum(r.get("idades_zeradas") or 0 for r in resultados)


def _qualidade_silver(ctx, registro) -> None:
    verificacoes = qualidade.verificar_silver(ctx.con) + qualidade.conciliar_silver(ctx.con)
    ctx.exec.registrar_verificacoes(verificacoes)
    total = ctx.con.execute("SELECT count(*) FROM refined.respostas").fetchall()[0][0]
    _contar(registro, total, total, total)
    _bloquear(verificacoes, "Silver")


def _marts(ctx, registro) -> None:
    resultados = marts.executar(ctx.con, ctx.pasta_sql)
    marts.imprimir(resultados)
    total = ctx.con.execute("SELECT count(*) FROM refined.respostas").fetchall()[0][0]
    registro.update(recebidas=total, processadas=len(resultados), rejeitadas=0,
                    publicadas=sum(n for _, n in resultados))


def _qualidade_gold(ctx, registro) -> None:
    nomes = [nome for _, nome in marts.listar_arquivos(ctx.pasta_sql)]
    verificacoes = qualidade.verificar_gold(ctx.con, nomes)
    ctx.exec.registrar_verificacoes(verificacoes)
    try:
        _bloquear(verificacoes, "Gold")
    except ErroDePipeline:
        ctx.con.execute("DROP SCHEMA IF EXISTS marts CASCADE")  # a Gold reprovada não fica no banco
        raise
    linhas = sum(ctx.con.execute(f"SELECT count(*) FROM marts.{n}").fetchall()[0][0] for n in nomes)
    _contar(registro, linhas, linhas, linhas)


PASSOS = [
    ("pré-condições", _precondicoes),
    ("1 · ingestão", _ingestao),
    ("1b · conciliação do raw", _conciliar_raw),
    ("2 · transformação", _transformacao),
    ("2b · qualidade da Silver", _qualidade_silver),
    ("3 · marts", _marts),
    ("3b · qualidade da Gold", _qualidade_gold),
]


def _mensagem(erro: Exception) -> str:
    if isinstance(erro, (ErroDePipeline, marts.ErroDeMarts, transformacao.ErroDeTransformacao)):
        return str(erro)
    if isinstance(erro, duckdb.Error):
        return f"Erro do DuckDB: {erro}"
    return f"Erro inesperado ({type(erro).__name__}): {erro}"


def _descartar(novo: Path) -> None:
    for arquivo in (novo, novo.with_name(novo.name + ".wal")):
        arquivo.unlink(missing_ok=True)


def _publicar(ctx) -> bool:
    """Grava `controle`, fecha e troca o banco anterior pelo novo. False se a troca não foi possível."""
    ctx.exec.finalizar("ok", banco_publicado=True)
    ctx.exec.gravar_controle(ctx.con)
    ctx.con.close()
    ctx.con = None
    try:
        os.replace(ctx.novo, ctx.destino)
    except OSError as erro:
        print(f"Não consegui substituir {ctx.destino.name} ({type(erro).__name__}). "
              "Feche o painel ou o que estiver usando o banco e rode de novo.")
        return False
    novo_wal = ctx.novo.with_name(ctx.novo.name + ".wal")
    novo_wal.unlink(missing_ok=True)
    return True


def rodar(pasta_raw=None, pasta_sql=None, caminho_banco=None, pasta_logs=None) -> execucao.Execucao:
    """Roda tudo e devolve a Execucao (status 'ok' ou 'falhou'). Nunca levanta por falha do pipeline."""
    destino = Path(caminho_banco or db.CAMINHO_BANCO)
    ctx = SimpleNamespace(
        exec=execucao.Execucao(pasta_logs), pasta_raw=Path(pasta_raw or db.PASTA_RAW),
        pasta_sql=Path(pasta_sql or marts.PASTA_SQL), destino=destino,
        novo=destino.with_name(destino.name + ".novo"), con=None, linhas_csv={},
    )
    _descartar(ctx.novo)  # sobra de uma execução que morreu no meio
    falhou, publicado = False, False
    try:
        for nome, passo in PASSOS:
            if falhou:
                ctx.exec.pular(nome)
                continue
            try:
                with ctx.exec.etapa(nome) as registro:
                    passo(ctx, registro)
            except Exception as erro:  # noqa: BLE001 - qualquer falha vira status 'falhou', nunca traceback cru
                print(f"\n✗ {nome}: {_mensagem(erro)}")
                falhou = True
        if not falhou:
            publicado = _publicar(ctx)
    finally:
        if ctx.con is not None:
            ctx.con.close()
        if not publicado:
            _descartar(ctx.novo)
    if not publicado:
        ctx.exec.finalizar("falhou", banco_publicado=False)
    ctx.exec.gravar_arquivos()
    return ctx.exec


def imprimir_resumo(e: execucao.Execucao) -> None:
    print(f"\n== Resumo · execução {e.id} · versão {e.versao}")
    for etapa in e.etapas:
        marca = {"ok": "✓", "falhou": "✗"}.get(etapa["status"], "–")
        contagem = ""
        if etapa["recebidas"] is not None:
            contagem = (f"recebidas {milhar(etapa['recebidas'])} · processadas {milhar(etapa['processadas'])}"
                        f" · rejeitadas {milhar(etapa['rejeitadas'])} · publicadas {milhar(etapa['publicadas'])}")
        duracao = f"{etapa['duracao_s']:.2f}s" if etapa["duracao_s"] is not None else "-"
        print(f"  {marca} {etapa['etapa']:<26} {etapa['status']:<14} {duracao:>7}  {contagem}")
    r = qualidade.resumo(e.verificacoes)
    print(f"  qualidade: {r['aprovadas']}/{r['total']} verificações ok · {r['falhas_erro']} erro(s) · "
          f"{r['falhas_aviso']} aviso(s)")
    print("  banco novo publicado" if e.banco_publicado else "  banco anterior mantido (nada foi publicado)")
    print(f"  duração total {e.duracao_s:.2f}s · relatório em logs/execucoes/{e.id}/")
    if e.aviso_log:
        print(f"  aviso: {e.aviso_log}")
