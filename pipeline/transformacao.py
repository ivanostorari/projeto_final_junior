"""Etapa 2 · Transformação: raw -> refined. Executar com:

    uv run python -m pipeline.transformacao

Spec completa, com os números que a motivam, em specs/transformacao.md.
Resumo das regras e dos motivos:

1. ESCOPO. Lê de raw, escreve em refined, nunca escreve em raw. Duas tabelas.
2. NOMES. Colunas em português, mapa literal em TABELAS. A única coluna que não
   passa é comments (texto livre, nenhum indicador usa, pode ter dado pessoal).
3. TIPOS. Timestamp -> TIMESTAMP; Age -> BIGINT (99999999999 não cabe em
   INTEGER); colunas Sim/Não -> BOOLEAN; respostas fechadas -> texto em português
   pelo dicionário (pipeline/dicionario.py), que também é a lista de valores permitidos.
4. VALOR FORA DO DICIONÁRIO PARA TUDO. Também conversão que falha. TRY_CAST só é
   usado ANTES, para detectar e explicar. Motivo: um nulo fabricado pela
   conversão fica indistinguível de um nulo verdadeiro para sempre.
5. IDADE FORA DE 16..80: idade fica nula, idade_informada guarda o original.
   É a única regra que cria nulo, e ela é contada na saída.
6. GÊNERO: texto livre agrupado em 4 categorias pelo mapa GENERO. Grafia nova para tudo.
7. CHAVE. respostas não tem chave natural: id_resposta = ordem no arquivo (rowid + 1).
   paises tem chave nome; repetida para tudo.
8. NULOS. Nenhuma linha apagada por ter nulo, nenhum nulo preenchido.
9. PAÍS. Todo país de respostas precisa existir em paises (depois dos dois
   aliases); senão ele sumiria do indicador por continente sem aviso.

REEXECUÇÃO: CREATE OR REPLACE. Tudo roda numa transação: se algo falhar,
refined continua como estava na última execução que deu certo.
"""

import sys

import duckdb

from pipeline import db
from pipeline.dicionario import (
    ALIAS_PAISES,
    BOOLEANO,
    GENERO,
    IDADE_MAXIMA,
    IDADE_MINIMA,
    MAPAS,
)
from pipeline.saida import configurar_saida, milhar

ORIGEM = "raw"
DESTINO = "refined"
FORMATO_TIMESTAMP = "%Y-%m-%d %H:%M:%S"

# (coluna original, coluna nova, tipo). Tipos: id, ts, bigint, idade, bool, mapa, genero, pais, texto.
TABELAS = {
    "respostas": {
        "chave": ["id_resposta"],
        "colunas": [
            ("rowid", "id_resposta", "id"),
            ("Timestamp", "respondido_em", "ts"),
            ("Age", "idade_informada", "bigint"),
            ("Age", "idade", "idade"),
            ("Gender", "genero", "genero"),
            ("Country", "pais", "pais"),
            ("state", "estado", "texto"),
            ("self_employed", "autonomo", "bool"),
            ("family_history", "historico_familiar", "bool"),
            ("treatment", "tratamento", "bool"),
            ("work_interfere", "interferencia_trabalho", "mapa"),
            ("no_employees", "tamanho_empresa", "mapa"),
            ("remote_work", "trabalho_remoto", "bool"),
            ("tech_company", "empresa_tecnologia", "bool"),
            ("benefits", "beneficios", "mapa"),
            ("care_options", "opcoes_cuidado", "mapa"),
            ("wellness_program", "programa_bem_estar", "mapa"),
            ("seek_help", "recursos_ajuda", "mapa"),
            ("anonymity", "anonimato", "mapa"),
            ("leave", "licenca", "mapa"),
            ("mental_health_consequence", "consequencia_saude_mental", "mapa"),
            ("phys_health_consequence", "consequencia_saude_fisica", "mapa"),
            ("coworkers", "falaria_colegas", "mapa"),
            ("supervisor", "falaria_supervisor", "mapa"),
            ("mental_health_interview", "falaria_entrevista_mental", "mapa"),
            ("phys_health_interview", "falaria_entrevista_fisica", "mapa"),
            ("mental_vs_physical", "mental_igual_fisica", "mapa"),
            ("obs_consequence", "observou_consequencia", "bool"),
        ],
    },
    "paises": {
        "chave": ["nome"],
        "colunas": [
            ("name_short", "nome", "texto"),
            ("name_official", "nome_oficial", "texto"),
            ("ISO3", "iso3", "texto"),
            ("continent", "continente", "texto"),
            ("UNregion", "regiao_onu", "texto"),
        ],
    },
}


class ErroDeTransformacao(Exception):
    """Falha que interrompe a transformação com uma mensagem para o humano."""


def _lit(texto: str) -> str:
    """Texto como literal SQL (aspas simples dobradas: Don't know -> 'Don''t know')."""
    return "'" + texto.replace("'", "''") + "'"


def _col(coluna: str) -> str:
    return f'"{coluna}"'


def _case(coluna_sql: str, pares: dict, sem_correspondencia: str = "") -> str:
    quando = " ".join(f"WHEN {_lit(k)} THEN {_lit(v)}" for k, v in pares.items())
    return f"CASE {coluna_sql} {quando} {sem_correspondencia} END"


def expressao(coluna: str, tipo: str) -> str:
    """SQL estrito de conversão. Nunca TRY_*: se o valor não converte, estoura."""
    c = _col(coluna)
    if tipo == "id":
        return "CAST(rowid + 1 AS INTEGER)"
    if tipo == "texto":
        return c
    if tipo == "ts":
        return f"strptime({c}, {_lit(FORMATO_TIMESTAMP)})"
    if tipo == "bigint":
        return f"CAST({c} AS BIGINT)"
    if tipo == "idade":
        return f"CASE WHEN CAST({c} AS BIGINT) BETWEEN {IDADE_MINIMA} AND {IDADE_MAXIMA} THEN CAST({c} AS INTEGER) END"
    if tipo == "bool":
        quando = " ".join(f"WHEN {_lit(k)} THEN {str(v).upper()}" for k, v in BOOLEANO.items())
        return f"CASE {c} {quando} END"
    if tipo == "mapa":
        return _case(c, MAPAS[coluna])
    if tipo == "genero":
        return _case(f"lower(trim({c}))", GENERO)
    if tipo == "pais":
        quando = " ".join(f"WHEN {_lit(k)} THEN {_lit(v)}" for k, v in ALIAS_PAISES.items())
        return f"CASE {c} {quando} ELSE {c} END"
    raise ValueError(f"tipo desconhecido: {tipo}")


def condicao_invalida(coluna: str, tipo: str) -> str | None:
    """Condição que acha valores que NÃO convertem ou não estão no dicionário. Só para detectar."""
    c = _col(coluna)
    if tipo in ("bigint", "idade"):
        return f"{c} IS NOT NULL AND try_cast({c} AS BIGINT) IS NULL"
    if tipo == "ts":
        return f"{c} IS NOT NULL AND try_strptime({c}, {_lit(FORMATO_TIMESTAMP)}) IS NULL"
    if tipo == "bool":
        lista = ", ".join(_lit(k) for k in BOOLEANO)
        return f"{c} IS NOT NULL AND {c} NOT IN ({lista})"
    if tipo == "mapa":
        lista = ", ".join(_lit(k) for k in MAPAS[coluna])
        return f"{c} IS NOT NULL AND {c} NOT IN ({lista})"
    if tipo == "genero":
        lista = ", ".join(_lit(k) for k in GENERO)
        return f"{c} IS NOT NULL AND lower(trim({c})) NOT IN ({lista})"
    return None


def _um(con, sql: str, parametros=None):
    return con.execute(sql, parametros or []).fetchall()[0]


def verificar_entrada(con) -> None:
    """Para tudo se faltar qualquer tabela em raw."""
    existentes = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", [ORIGEM]
        ).fetchall()
    }
    faltando = [t for t in TABELAS if t not in existentes]
    if faltando:
        raise ErroDeTransformacao(
            "Faltam tabelas em raw: "
            + ", ".join(faltando)
            + ".\nRode antes: uv run python -m pipeline.ingestao"
        )


def validar_conversoes(con, tabela: str, colunas) -> None:
    for original, _novo, tipo in colunas:
        cond = condicao_invalida(original, tipo)
        if cond is None:
            continue
        quantos, exemplo = _um(con, f"SELECT count(*), min({_col(original)}) FROM {ORIGEM}.{tabela} WHERE {cond}")
        if quantos:
            raise ErroDeTransformacao(
                f"A coluna {original} de {ORIGEM}.{tabela} tem {milhar(quantos)} valor(es) que não "
                f"convertem para '{tipo}' ou não estão no dicionário. Exemplo: {exemplo!r}.\n"
                "Nada foi alterado: a conversão não vira nulo em silêncio. Investigue o valor "
                "e, se for válido, acrescente-o ao dicionário (pipeline/dicionario.py) e à spec."
            )


def verificar_chave(con, tabela: str, chave: list[str], colunas) -> None:
    """Chave natural (paises): sem repetição. respostas usa id_resposta, que é único por construção."""
    if tabela == "respostas":
        return
    original = {novo: orig for orig, novo, _ in colunas}
    lista = ", ".join(_col(original[c]) for c in chave)
    n, distintas = _um(con, f"SELECT count(*), count(DISTINCT ({lista})) FROM {ORIGEM}.{tabela}")
    if n != distintas:
        exemplo = con.execute(
            f"SELECT {lista}, count(*) FROM {ORIGEM}.{tabela} GROUP BY {lista} HAVING count(*) > 1 LIMIT 1"
        ).fetchall()
        raise ErroDeTransformacao(
            f"Em {ORIGEM}.{tabela}, a chave ({lista}) se repete. Exemplo: {exemplo[0] if exemplo else '?'}.\n"
            "Não escolho uma linha por conta própria: decida qual vale e ajuste a spec."
        )


def transformar_tabela(con, tabela: str, especificacao: dict) -> dict:
    colunas = especificacao["colunas"]
    entrada = _um(con, f"SELECT count(*) FROM {ORIGEM}.{tabela}")[0]
    identicas = entrada - _um(con, f"SELECT count(*) FROM (SELECT DISTINCT * FROM {ORIGEM}.{tabela})")[0]

    verificar_chave(con, tabela, especificacao["chave"], colunas)
    validar_conversoes(con, tabela, colunas)

    selecao = ",\n    ".join(f"{expressao(o, t)} AS {n}" for o, n, t in colunas)
    ordem = " ORDER BY rowid" if tabela == "respostas" else ""
    con.execute(f"CREATE OR REPLACE TABLE {DESTINO}.{tabela} AS SELECT\n    {selecao}\nFROM {ORIGEM}.{tabela}{ordem}")

    saida = _um(con, f"SELECT count(*) FROM {DESTINO}.{tabela}")[0]
    nulos, idades_zeradas = {}, 0
    for original, novo, tipo in colunas:
        if tipo == "id":
            continue
        antes = _um(con, f"SELECT count(*) - count({_col(original)}) FROM {ORIGEM}.{tabela}")[0]
        depois = _um(con, f"SELECT count(*) - count({novo}) FROM {DESTINO}.{tabela}")[0]
        if tipo == "idade":
            idades_zeradas = depois - antes
            continue
        if antes != depois:
            raise ErroDeTransformacao(
                f"{DESTINO}.{tabela}.{novo}: {antes} nulos antes e {depois} depois. "
                "A conversão fabricou ou engoliu nulos."
            )
        if depois:
            nulos[novo] = depois
    if idades_zeradas:
        nulos["idade"] = idades_zeradas + _um(con, f"SELECT count(*) - count(\"Age\") FROM {ORIGEM}.{tabela}")[0]
    return {
        "tabela": tabela, "entrada": entrada, "saida": saida, "identicas": identicas,
        "nulos": nulos, "idades_zeradas": idades_zeradas,
    }


def verificar_paises(con) -> None:
    """Todo país de respostas tem de existir em paises, senão some do indicador por continente."""
    sem_cadastro = con.execute(
        f"SELECT r.pais, count(*) FROM {DESTINO}.respostas r LEFT JOIN {DESTINO}.paises p ON p.nome = r.pais "
        "WHERE r.pais IS NOT NULL AND p.nome IS NULL GROUP BY r.pais ORDER BY 2 DESC"
    ).fetchall()
    if sem_cadastro:
        lista = ", ".join(f"{p} ({n})" for p, n in sem_cadastro)
        raise ErroDeTransformacao(
            f"Países da pesquisa que não existem em {DESTINO}.paises: {lista}.\n"
            "Acrescente o apelido em ALIAS_PAISES (pipeline/dicionario.py) se for só outra grafia."
        )


def transformar(con) -> list[dict]:
    """Roda as duas tabelas numa transação. Se algo falhar, refined fica como estava."""
    verificar_entrada(con)
    con.execute("BEGIN")
    try:
        db.criar_schema(con, DESTINO)
        resultados = [transformar_tabela(con, t, e) for t, e in TABELAS.items()]
        verificar_paises(con)
        generos = con.execute(
            f"SELECT genero, count(*) FROM {DESTINO}.respostas GROUP BY 1 ORDER BY 2 DESC, 1"
        ).fetchall()
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")
    resultados[0]["generos"] = generos
    return resultados


def imprimir(resultados: list[dict]) -> None:
    total = 0
    for r in resultados:
        total += r["saida"]
        print(
            f"✓ {DESTINO}.{r['tabela']:<10} {milhar(r['entrada']):>7} → {milhar(r['saida']):>7} linhas"
            f"  ({r['identicas']} linhas idênticas)"
        )
        if r["nulos"]:
            print("    nulos: " + ", ".join(f"{c} {milhar(n)}" for c, n in r["nulos"].items()))
        if r["idades_zeradas"]:
            print(
                f"    {r['idades_zeradas']} idades fora de {IDADE_MINIMA}..{IDADE_MAXIMA} viraram nulo em idade "
                "(o valor original continua em idade_informada)"
            )
        if r.get("generos"):
            print("    gênero: " + " · ".join(f"{g} {milhar(n)}" for g, n in r["generos"]))
    print(f"  total{'':<24} {milhar(total):>7} linhas")


def main() -> None:
    configurar_saida()
    con = db.conectar()
    try:
        resultados = transformar(con)
    except ErroDeTransformacao as erro:
        print(erro)
        sys.exit(1)
    except duckdb.Error as erro:
        print(f"Erro do DuckDB (nada foi alterado em {DESTINO}): {erro}")
        sys.exit(1)
    finally:
        con.close()
    imprimir(resultados)


if __name__ == "__main__":
    main()
