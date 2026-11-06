"""Regras de qualidade de dados, por camada e por dimensão. Spec: specs/operacao.md.

Cada verificação devolve uma `Verificacao` (nunca levanta exceção por dado ruim): quem decide parar é
o orquestrador, olhando `bloqueia()`. Severidades:

- erro: falhou => a execução para e a Gold não é publicada;
- aviso: falhou => fica registrado e visível, a execução continua;
- informacao: só mede (nunca falha).

Nenhuma mensagem aqui carrega valor de linha: só nomes de coluna/tabela e contagens.
"""

from dataclasses import asdict, dataclass

from pipeline import ingestao
from pipeline.dicionario import GENERO, IDADE_MAXIMA, IDADE_MINIMA, MAPAS
from pipeline.transformacao import TABELAS

ERRO, AVISO, INFORMACAO = "erro", "aviso", "informacao"

LIMITE_IDADE_NULA = 0.05
GENEROS_VALIDOS = sorted(set(GENERO.values()))
# Marts em que cada resposta cai em exatamente uma linha: a soma de `respondentes` tem de fechar com refined.
MARTS_QUE_PARTICIONAM = (
    "respostas_por_continente",
    "tratamento_por_genero",
    "historico_familiar",
    "interferencia_trabalho",
    "tamanho_empresa",
    "faixa_etaria",
)
TIPOS = {"id": "INTEGER", "ts": "TIMESTAMP", "bigint": "BIGINT", "idade": "INTEGER", "bool": "BOOLEAN"}


@dataclass(frozen=True)
class Verificacao:
    camada: str
    dimensao: str
    regra: str
    severidade: str
    ok: bool
    observado: str
    esperado: str
    detalhe: str = ""

    def como_dict(self) -> dict:
        return asdict(self)


def bloqueia(verificacoes) -> bool:
    return any(not v.ok and v.severidade == ERRO for v in verificacoes)


def falhas(verificacoes, severidade: str | None = None) -> list[Verificacao]:
    return [v for v in verificacoes if not v.ok and (severidade is None or v.severidade == severidade)]


def resumo(verificacoes) -> dict:
    return {
        "total": len(verificacoes),
        "aprovadas": sum(v.ok for v in verificacoes),
        "falhas_erro": len(falhas(verificacoes, ERRO)),
        "falhas_aviso": len(falhas(verificacoes, AVISO)),
        "bloqueia": bloqueia(verificacoes),
    }


def relatorio(verificacoes) -> dict:
    return {"resumo": resumo(verificacoes), "verificacoes": [v.como_dict() for v in verificacoes]}


def imprimir(titulo: str, verificacoes) -> None:
    r = resumo(verificacoes)
    print(
        f"  qualidade · {titulo}: {r['aprovadas']}/{r['total']} ok"
        f" · {r['falhas_erro']} erro(s) · {r['falhas_aviso']} aviso(s)"
    )
    for v in falhas(verificacoes):
        print(f"    ✗ [{v.severidade}] {v.camada}/{v.dimensao}: {v.regra} (obtido {v.observado}, esperado {v.esperado})")


def _n(con, sql: str, parametros=None) -> int:
    return con.execute(sql, parametros or []).fetchall()[0][0]


def _regra(camada, dimensao, regra, severidade, observado, esperado, ok=None, detalhe="") -> Verificacao:
    aprovou = (observado == esperado) if ok is None else ok
    return Verificacao(camada, dimensao, regra, severidade, bool(aprovou), str(observado), str(esperado), detalhe)


def _colunas(con, schema: str, tabela: str) -> list[tuple[str, str]]:
    return con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
        [schema, tabela],
    ).fetchall()


def _esquema_esperado(tabela: str) -> list[tuple[str, str]]:
    return [(novo, TIPOS.get(tipo, "VARCHAR")) for _, novo, tipo in TABELAS[tabela]["colunas"]]


def _verificar_esquema(con) -> tuple[list[Verificacao], bool]:
    resultado, esquema_ok = [], True
    for tabela in TABELAS:
        observado, esperado = _colunas(con, "refined", tabela), _esquema_esperado(tabela)
        esquema_ok = esquema_ok and observado == esperado
        diferencas = sorted(set(esperado) ^ set(observado))
        detalhe = "diferem: " + ", ".join(f"{c}:{t}" for c, t in diferencas) if diferencas else ""
        resultado.append(
            _regra("refined", "esquema", f"colunas e tipos de refined.{tabela} conforme o definido", ERRO,
                   len(diferencas), 0, ok=observado == esperado, detalhe=detalhe)
        )
    nomes = [c for c, _ in _colunas(con, "refined", "respostas")]
    comentario = [c for c in nomes if "coment" in c.lower() or c.lower() == "comments"]
    resultado.append(
        _regra("refined", "privacidade", "texto livre dos comentários não existe em refined", ERRO,
               len(comentario), 0)
    )
    return resultado, esquema_ok


def _nome_novo(original: str) -> str:
    return next(novo for orig, novo, _ in TABELAS["respostas"]["colunas"] if orig == original)


def _verificar_dominios(con) -> Verificacao:
    fora, colunas = 0, []
    for original, mapa in MAPAS.items():
        coluna = _nome_novo(original)
        valores = sorted(set(mapa.values()))
        marcas = ", ".join("?" for _ in valores)
        n = _n(con, f'SELECT count(*) FROM refined.respostas WHERE "{coluna}" IS NOT NULL '
                    f'AND "{coluna}" NOT IN ({marcas})', valores)
        if n:
            fora += n
            colunas.append(coluna)
    return _regra("refined", "dominio", "colunas categóricas só têm valores do dicionário", ERRO, fora, 0,
                  detalhe="colunas: " + ", ".join(colunas) if colunas else "")


def verificar_silver(con) -> list[Verificacao]:
    """Qualidade de refined: esquema, completude, unicidade, validade, domínio, consistência, integridade."""
    resultado, esquema_ok = _verificar_esquema(con)
    if not esquema_ok:
        return resultado  # com tabela ou coluna fora do definido não há o que medir; o erro de esquema já bloqueia
    r = "refined.respostas"
    total = _n(con, f"SELECT count(*) FROM {r}")
    nulos_obrigatorios = _n(
        con, f"SELECT count(*) FROM {r} WHERE id_resposta IS NULL OR respondido_em IS NULL OR genero IS NULL"
    )
    sem_idade = _n(con, f"SELECT count(*) FROM {r} WHERE idade IS NULL")
    anuladas = _n(con, f"SELECT count(*) FROM {r} WHERE idade IS NULL AND idade_informada IS NOT NULL")
    fora_da_faixa = _n(con, f"SELECT count(*) FROM {r} WHERE idade NOT BETWEEN ? AND ?",
                       [IDADE_MINIMA, IDADE_MAXIMA])
    generos = ", ".join(f"'{g}'" for g in GENEROS_VALIDOS)
    resultado += [
        _regra("refined", "completude", "id_resposta, respondido_em e genero sem nulos", ERRO,
               nulos_obrigatorios, 0),
        _regra("refined", "completude", "pais sem nulos", AVISO,
               _n(con, f"SELECT count(*) FROM {r} WHERE pais IS NULL"), 0),
        _regra("refined", "completude", f"idade nula em no máximo {LIMITE_IDADE_NULA:.0%} das linhas", AVISO,
               f"{sem_idade}/{total}", f"<= {LIMITE_IDADE_NULA:.0%}",
               ok=total > 0 and sem_idade / total <= LIMITE_IDADE_NULA),
        _regra("refined", "unicidade", "id_resposta único", ERRO,
               total - _n(con, f"SELECT count(DISTINCT id_resposta) FROM {r}"), 0),
        _regra("refined", "unicidade", "paises.nome único", ERRO,
               _n(con, "SELECT count(*) - count(DISTINCT nome) FROM refined.paises"), 0),
        _regra("refined", "unicidade", "paises.iso3 único", ERRO,
               _n(con, "SELECT count(iso3) - count(DISTINCT iso3) FROM refined.paises"), 0),
        _regra("refined", "validade", f"idade entre {IDADE_MINIMA} e {IDADE_MAXIMA} quando existe", ERRO,
               fora_da_faixa, 0),
        _regra("refined", "validade", "genero dentro das 4 categorias", ERRO,
               _n(con, f"SELECT count(*) FROM {r} WHERE genero NOT IN ({generos})"), 0),
        _verificar_dominios(con),
        _regra("refined", "consistencia", "idade nula ou igual a idade_informada", ERRO,
               _n(con, f"SELECT count(*) FROM {r} WHERE idade IS NOT NULL AND idade <> idade_informada"), 0),
        _regra("refined", "consistencia", "respondido_em não está no futuro", ERRO,
               _n(con, f"SELECT count(*) FROM {r} WHERE respondido_em > current_timestamp"), 0),
        _regra("refined", "integridade", "todo país de respostas existe em paises", AVISO,
               _n(con, f"SELECT count(*) FROM {r} x WHERE x.pais IS NOT NULL "
                       "AND NOT EXISTS (SELECT 1 FROM refined.paises p WHERE p.nome = x.pais)"), 0),
        _regra("refined", "informacao", "total de respostas em refined", INFORMACAO, total, total),
        _regra("refined", "informacao", "idades anuladas pela regra (informada e fora da faixa)", INFORMACAO,
               anuladas, anuladas),
    ]
    return resultado


def conciliar_raw(con, linhas_csv: dict[str, int]) -> list[Verificacao]:
    """Linhas de cada CSV (contadas pelo contrato) = linhas gravadas em raw."""
    resultado = []
    for arquivo, (tabela, _) in ingestao.ARQUIVOS.items():
        gravadas = _n(con, f"SELECT count(*) FROM raw.{tabela}")
        resultado.append(
            _regra("raw", "conciliacao", f"linhas de {arquivo} = linhas de raw.{tabela}", ERRO,
                   gravadas, linhas_csv.get(arquivo))
        )
    return resultado


def conciliar_silver(con) -> list[Verificacao]:
    """Nenhuma linha some entre raw e refined."""
    return [
        _regra("refined", "conciliacao", f"raw.{t} e refined.{t} têm o mesmo número de linhas", ERRO,
               _n(con, f"SELECT count(*) FROM refined.{t}"), _n(con, f"SELECT count(*) FROM raw.{t}"))
        for t in TABELAS
    ]


def verificar_gold(con, marts_esperados: list[str]) -> list[Verificacao]:
    """Qualidade de marts: existência, linhas, limites dos percentuais e conciliação com refined."""
    existentes = {t for (t,) in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts'").fetchall()}
    faltando = [m for m in marts_esperados if m not in existentes]
    vazios = [m for m in marts_esperados if m in existentes and _n(con, f"SELECT count(*) FROM marts.{m}") == 0]
    pct_fora, negativos, divergentes = 0, 0, []
    total = _n(con, "SELECT count(*) FROM refined.respostas")
    for mart in (m for m in marts_esperados if m in existentes):
        colunas = [c for c, _ in _colunas(con, "marts", mart)]
        for c in (c for c in colunas if c.startswith("pct")):
            pct_fora += _n(con, f'SELECT count(*) FROM marts.{mart} WHERE "{c}" < 0 OR "{c}" > 100')
        if "respondentes" in colunas:
            negativos += _n(con, f"SELECT count(*) FROM marts.{mart} WHERE respondentes < 0")
            if mart in MARTS_QUE_PARTICIONAM and _n(con, f"SELECT sum(respondentes) FROM marts.{mart}") != total:
                divergentes.append(mart)
    return [
        _regra("marts", "completude", "todo .sql tem sua tabela", ERRO, len(faltando), 0,
               detalhe="faltam: " + ", ".join(faltando) if faltando else ""),
        _regra("marts", "completude", "todo mart tem pelo menos 1 linha", ERRO, len(vazios), 0,
               detalhe="vazios: " + ", ".join(vazios) if vazios else ""),
        _regra("marts", "validade", "colunas pct_* entre 0 e 100", ERRO, pct_fora, 0),
        _regra("marts", "validade", "respondentes nunca negativo", ERRO, negativos, 0),
        _regra("marts", "conciliacao", "soma de respondentes dos marts que particionam = refined.respostas",
               ERRO, len(divergentes), 0, detalhe="divergem: " + ", ".join(divergentes) if divergentes else ""),
    ]
