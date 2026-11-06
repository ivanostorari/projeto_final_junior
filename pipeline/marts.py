"""Etapa 3 · Marts: refined -> marts, um arquivo .sql por indicador. Executar com:

    uv run python -m pipeline.marts

Spec completa em specs/marts.md. Resumo das regras e dos motivos:

1. UM ARQUIVO, UMA TABELA. Lê sql/marts/*.sql em ordem alfabética. Nome da
   tabela = nome do arquivo sem extensão e sem o prefixo NN_. Executa
   CREATE TABLE marts.<nome> AS <arquivo>. Tira espaços e UM ponto e vírgula
   do final e mais nada. Motivo: a regra de negócio mora inteira no .sql; o
   Python não altera, não monta e não completa a SQL.
2. O schema marts é apagado e recriado a cada execução. Motivo: um mart cujo
   arquivo foi apagado não pode continuar existindo no banco.
3. Tudo numa transação. Motivo: um schema pela metade quebra o painel sem aviso.
4. ERROS que param tudo (sys.exit(1)): falta tabela em refined; pasta sem
   arquivo; arquivo sem prefixo NN_; dois arquivos com o mesmo nome; SQL com
   erro (mostra o arquivo); mart com ZERO linhas. Motivo do último: mart vazio
   é quase sempre um JOIN que não casou, e um painel vazio parece negócio parado.
5. SAÍDA. Uma linha por mart, contagem do banco, milhar com ponto.
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline import db
from pipeline.saida import configurar_saida, milhar

DESTINO = "marts"
ORIGEM = "refined"
PASTA_SQL = db.RAIZ / "sql" / "marts"
TABELAS_NECESSARIAS = ["respostas", "paises"]
PADRAO_ARQUIVO = re.compile(r"^(\d{2})_([a-z][a-z0-9_]*)\.sql$")
REFERENCIA = re.compile(r"\b(raw|refined|marts)\.([a-z_][a-z0-9_]*)")


class ErroDeMarts(Exception):
    """Falha que interrompe a execução com uma mensagem para o humano."""


def listar_arquivos(pasta: Path) -> list[tuple[Path, str]]:
    """Devolve [(arquivo, nome_da_tabela)] em ordem alfabética, validando os nomes."""
    arquivos = sorted(pasta.glob("*.sql")) if pasta.exists() else []
    if not arquivos:
        raise ErroDeMarts(f"Nenhum arquivo .sql em {pasta}. Não há marts para criar.")

    sem_prefixo = [a.name for a in arquivos if not PADRAO_ARQUIVO.match(a.name)]
    if sem_prefixo:
        raise ErroDeMarts(
            "Arquivos fora do padrão NN_nome.sql (dois dígitos, sublinhado, minúsculas):\n  - "
            + "\n  - ".join(sem_prefixo)
        )

    por_nome: dict[str, list[str]] = {}
    for arquivo in arquivos:
        nome = PADRAO_ARQUIVO.match(arquivo.name).group(2)
        por_nome.setdefault(nome, []).append(arquivo.name)
    repetidos = {n: a for n, a in por_nome.items() if len(a) > 1}
    if repetidos:
        linhas = [f"  - {n}: {', '.join(a)}" for n, a in repetidos.items()]
        raise ErroDeMarts("Arquivos que dão o mesmo nome de tabela:\n" + "\n".join(linhas))

    return [(a, PADRAO_ARQUIVO.match(a.name).group(2)) for a in arquivos]


def limpar_sql(texto: str) -> str:
    """Tira espaços e UM ponto e vírgula do final. Nada além disso."""
    texto = texto.strip()
    if texto.endswith(";"):
        texto = texto[:-1].rstrip()
    return texto


def dependencias(sql: str) -> list[str]:
    """Tabelas (schema.tabela) que o SQL cita, sem olhar os comentários. Base da linhagem dos marts."""
    codigo = "\n".join(linha.split("--", 1)[0] for linha in sql.splitlines())
    return sorted({f"{schema}.{tabela}" for schema, tabela in REFERENCIA.findall(codigo)})


def verificar_entrada(con) -> None:
    existentes = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", [ORIGEM]
        ).fetchall()
    }
    faltando = [t for t in TABELAS_NECESSARIAS if t not in existentes]
    if faltando:
        raise ErroDeMarts(
            f"Faltam tabelas em {ORIGEM}: " + ", ".join(faltando) + ".\n"
            "Rode antes: uv run python -m pipeline.transformacao"
        )


def executar(con, pasta: Path | None = None) -> list[tuple[str, int]]:
    """Recria o schema marts numa transação. Devolve [(tabela, linhas)]."""
    pasta = pasta or PASTA_SQL
    arquivos = listar_arquivos(pasta)  # valida os nomes antes de tocar no banco
    verificar_entrada(con)

    resultados = []
    con.execute("BEGIN")
    try:
        con.execute(f"DROP SCHEMA IF EXISTS {DESTINO} CASCADE")
        con.execute(f"CREATE SCHEMA {DESTINO}")
        for arquivo, nome in arquivos:
            sql = limpar_sql(arquivo.read_text(encoding="utf-8"))
            try:
                con.execute(f"CREATE TABLE {DESTINO}.{nome} AS {sql}")
            except duckdb.Error as erro:
                raise ErroDeMarts(f"Erro em {arquivo.name}:\n{erro}") from erro
            linhas = con.execute(f"SELECT count(*) FROM {DESTINO}.{nome}").fetchall()[0][0]
            if linhas == 0:
                raise ErroDeMarts(
                    f"O mart {DESTINO}.{nome} ({arquivo.name}) voltou com zero linhas. "
                    "Quase sempre é um JOIN que não casou ou um filtro que não deixa nada passar."
                )
            resultados.append((nome, linhas))
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")
    return resultados


def imprimir(resultados: list[tuple[str, int]]) -> None:
    for nome, linhas in resultados:
        rotulo = "linha" if linhas == 1 else "linhas"
        print(f"✓ {DESTINO}.{nome:<28} {milhar(linhas):>6} {rotulo}")
    total = sum(linhas for _, linhas in resultados)
    print(f"  {len(resultados)} marts{'':<24} {milhar(total):>6} linhas")


def main() -> None:
    configurar_saida()
    con = db.conectar()
    try:
        resultados = executar(con)
    except ErroDeMarts as erro:
        print(erro)
        sys.exit(1)
    finally:
        con.close()
    imprimir(resultados)


if __name__ == "__main__":
    main()
