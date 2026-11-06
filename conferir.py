"""Confere os números da tela (README, seção "Números da tela") contra os marts. Executar com:

    uv run python conferir.py

Rodar DEPOIS do pipeline. Sai com código 1 se qualquer número divergir.

Por que existe: o painel, o HTML e o README têm que mostrar o mesmo número. Cada linha abaixo
diz de onde o número sai (um SELECT em um mart) e qual é o valor esperado, medido uma vez rodando
o pipeline e conferido por um segundo caminho (pandas direto no CSV). Se um .sql mudar e um número
mudar, isto acusa antes de o painel mostrar um número errado.

Este arquivo NÃO é um teste do pytest: os testes não abrem o banco do projeto (specs/testes.md).
Aqui abrir o banco é justamente o ponto, então ele fica fora de test/. O que está em test/ é só
a lógica de comparação, com um banco inventado.

Dois grupos: "certo" (o número que a tela mostra) e "errado" (o número que sai de um erro comum,
mantido aqui para o erro ter nome e valor: um número errado que alguém reproduz precisa ser
reconhecido como errado).
"""

import sys

import duckdb

import painel

# (grupo, o que é, SELECT que devolve UM valor, valor esperado)
CONFERENCIAS = [
    # ---- os seis cartões
    ("certo", "Respondentes", "SELECT respondentes FROM marts.kpis", 1259),
    ("certo", "Buscaram tratamento (%)", "SELECT pct_tratamento FROM marts.kpis", 50.6),
    ("certo", "Histórico familiar (%)", "SELECT pct_historico_familiar FROM marts.kpis", 39.1),
    ("certo", "Dizem ter benefícios (%)", "SELECT pct_beneficios_sim FROM marts.kpis", 37.9),
    ("certo", "Receiam consequência, saúde mental (%)", "SELECT pct_receio_consequencia FROM marts.kpis", 23.2),
    ("certo", "Falariam com o supervisor (%)", "SELECT pct_falaria_supervisor FROM marts.kpis", 41.0),
    # ---- gráficos
    ("certo", "Tratamento · Homem (%)", "SELECT pct_tratamento FROM marts.tratamento_por_genero WHERE genero = 'Homem'", 45.4),
    ("certo", "Tratamento · Mulher (%)", "SELECT pct_tratamento FROM marts.tratamento_por_genero WHERE genero = 'Mulher'", 68.9),
    ("certo", "Tratamento · com histórico familiar (%)", "SELECT pct_tratamento FROM marts.historico_familiar WHERE historico_familiar = 'Sim'", 74.2),
    ("certo", "Tratamento · sem histórico familiar (%)", "SELECT pct_tratamento FROM marts.historico_familiar WHERE historico_familiar = 'Não'", 35.5),
    ("certo", "Benefícios · empresa de 1-5 (%)", "SELECT pct_beneficios_sim FROM marts.tamanho_empresa WHERE faixa = '1-5'", 11.7),
    ("certo", "Benefícios · empresa de mais de 1000 (%)", "SELECT pct_beneficios_sim FROM marts.tamanho_empresa WHERE faixa = 'Mais de 1000'", 64.9),
    ("certo", "Benefícios · Estados Unidos (%)", "SELECT pct_beneficios_sim FROM marts.ranking_paises WHERE pais = 'United States'", 53.0),
    ("certo", "Benefícios · Reino Unido, posição", "SELECT posicao FROM marts.ranking_paises WHERE pais = 'United Kingdom'", 7),
    ("certo", "Receio · saúde física (%)", "SELECT pct_receio_sim FROM marts.consequencias_percebidas WHERE saude = 'Saúde física'", 4.8),
    ("certo", "Entrevista · saúde mental (%)", "SELECT pct_entrevista_sim FROM marts.consequencias_percebidas WHERE saude = 'Saúde mental'", 3.5),
    ("certo", "Respostas da América", "SELECT respondentes FROM marts.respostas_por_continente WHERE continente = 'America'", 837),
    ("certo", "Idades impossíveis (faixa sem_idade_valida)", "SELECT respondentes FROM marts.faixa_etaria WHERE faixa = 'sem_idade_valida'", 8),
    # ---- conferências cruzadas (mesmo número por caminhos diferentes)
    ("certo", "Soma de respondentes, mart 01", "SELECT sum(respondentes) FROM marts.respostas_por_continente", 1259),
    ("certo", "Soma de respondentes, mart 02", "SELECT sum(respondentes) FROM marts.tratamento_por_genero", 1259),
    ("certo", "Soma de respondentes, mart 04", "SELECT sum(respondentes) FROM marts.interferencia_trabalho", 1259),
    ("certo", "Soma de respondentes, mart 06", "SELECT sum(respondentes) FROM marts.tamanho_empresa", 1259),
    ("certo", "Soma de respondentes, mart 09", "SELECT sum(respondentes) FROM marts.faixa_etaria", 1259),
    ("certo", "Soma de respondentes, mart 05, só 'beneficios'", "SELECT sum(respondentes) FROM marts.apoio_empregador WHERE pergunta = 'beneficios'", 1259),
    ("certo", "Linhas nos dez marts", ("SELECT (SELECT count(*) FROM marts.respostas_por_continente) + (SELECT count(*) FROM marts.tratamento_por_genero)"
     " + (SELECT count(*) FROM marts.historico_familiar) + (SELECT count(*) FROM marts.interferencia_trabalho)"
     " + (SELECT count(*) FROM marts.apoio_empregador) + (SELECT count(*) FROM marts.tamanho_empresa)"
     " + (SELECT count(*) FROM marts.consequencias_percebidas) + (SELECT count(*) FROM marts.ranking_paises)"
     " + (SELECT count(*) FROM marts.faixa_etaria) + (SELECT count(*) FROM marts.kpis)"), 52),
    # ---- os erros comuns, com o valor que eles dão (devem ser DIFERENTES do certo)
    ("errado", "Média dos 4 percentuais por gênero, em vez de 50,6 (média de médias)", "SELECT round(avg(pct_tratamento), 1) FROM marts.tratamento_por_genero", 73.2),
    ("errado", "Média dos 5 percentuais por continente, em vez de 50,6 (média de médias)", "SELECT round(avg(pct_tratamento), 1) FROM marts.respostas_por_continente", 48.6),
    ("errado", "Soma dos 4 percentuais por gênero, em vez de 50,6", "SELECT round(sum(pct_tratamento), 1) FROM marts.tratamento_por_genero", 292.9),
    ("errado", "Soma de respondentes do mart 05 sem filtrar a pergunta (5 × 1.259)", "SELECT sum(respondentes) FROM marts.apoio_empregador", 6295),
    ("errado", "Benefícios sem contar o 'Não sei' no denominador, em vez de 37,9",
     ("SELECT round(100.0 * sum(respondentes) FILTER (WHERE resposta = 'Sim') / sum(respondentes) FILTER (WHERE resposta IN ('Sim', 'Não')), 1)"
     " FROM marts.apoio_empregador WHERE pergunta = 'beneficios'"), 56.1),
    ("errado", "Respostas após JOIN com países pelo continente, em vez de 1.259",
     ("SELECT count(*) FROM refined.respostas r JOIN refined.paises p"
     " ON p.continente = (SELECT continente FROM refined.paises WHERE nome = r.pais)"), 67313),
]


def conferir(con, conferencias=None) -> list[tuple[str, str, object, object, bool]]:
    """Roda cada SELECT e compara com o esperado. Devolve [(grupo, descrição, obtido, esperado, ok)]."""
    resultados = []
    for grupo, descricao, sql, esperado in conferencias if conferencias is not None else CONFERENCIAS:
        obtido = con.execute(sql).fetchall()[0][0]
        if isinstance(obtido, float):
            obtido = round(obtido, 2)
        resultados.append((grupo, descricao, obtido, esperado, obtido == esperado))
    return resultados


def imprimir(resultados) -> int:
    """Imprime e devolve quantos divergiram."""
    falhas = 0
    for grupo, descricao, obtido, esperado, ok in resultados:
        marca = "✓" if ok else "✗"
        rotulo = "ERRADO conhecido" if grupo == "errado" else "certo"
        linha = f"{marca} [{rotulo:<16}] {descricao}: {obtido}"
        if not ok:
            linha += f"  (esperado {esperado})"
            falhas += 1
        print(linha)
    print(f"\n{len(resultados) - falhas} de {len(resultados)} conferidos")
    return falhas


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not painel.CAMINHO_BANCO.exists():
        print(f"O banco {painel.CAMINHO_BANCO.name} não existe. Rode antes: uv run python executar.py")
        sys.exit(1)
    con = duckdb.connect(str(painel.CAMINHO_BANCO), read_only=True)
    try:
        resultados = conferir(con)
    except duckdb.Error as erro:
        print(f"Erro ao conferir (rode o pipeline antes: uv run python executar.py):\n{erro}")
        sys.exit(1)
    finally:
        con.close()
    if imprimir(resultados):
        sys.exit(1)


if __name__ == "__main__":
    main()
