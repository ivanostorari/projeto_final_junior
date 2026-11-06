"""Painel de saúde mental na tecnologia (pesquisa OSMI 2014): leitura dos marts, formatação e gráficos.

Spec completa em specs/painel.md. Resumo das regras e dos motivos:

1. LEITURA. Só SELECT * FROM marts.<nome>, com o banco aberto read_only e
   FECHADO antes de devolver. Motivo: conexão aberta segura o arquivo, e o
   pipeline.marts não consegue gravar com o painel de pé.
2. NENHUM CÁLCULO neste arquivo: sem agrupar, somar, tirar média, juntar tabelas
   nem fazer conta entre colunas. Permitido: ordenar, filtrar linhas, head(n), buscar uma linha,
   renomear, formatar. Motivo: número novo na tela exige um .sql novo em sql/marts/;
   regra de negócio no painel fica escondida onde ninguém procura.
3. FORMATO. Milhar com ponto e decimal com vírgula, sempre, sem depender do
   locale do computador. Nulo vira "—", nunca "nan".
4. Um gráfico por pergunta, uma cor só, unidade no título; barras começam no zero.
5. Grupo com menos de 20 respostas fica fora dos gráficos de percentual (e a nota
   diz quem ficou e quantas pessoas eram): "100% de 4 pessoas" não é resultado.
6. Este módulo não importa o framework da página: o app.py e o relatorio.py usam as mesmas
   funções, e o formato pode ser testado sozinho.
7. Sem conclusão pronta nas notas: elas dizem o que foi medido, o denominador e o limite.
"""

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go

RAIZ = Path(__file__).resolve().parent
CAMINHO_BANCO = RAIZ / "saude_mental.duckdb"

MARTS = [
    "respostas_por_continente",
    "tratamento_por_genero",
    "historico_familiar",
    "interferencia_trabalho",
    "apoio_empregador",
    "tamanho_empresa",
    "consequencias_percebidas",
    "ranking_paises",
    "faixa_etaria",
    "kpis",
]

COR = "#5b6fb5"
MIN_AMOSTRA = 20

CONTINENTES = {
    "America": "América", "Europe": "Europa", "Oceania": "Oceania", "Asia": "Ásia", "Africa": "África",
    "sem_cadastro": "Sem cadastro",
}
PAISES = {
    "United States": "Estados Unidos", "United Kingdom": "Reino Unido", "Canada": "Canadá",
    "Germany": "Alemanha", "Netherlands": "Países Baixos", "Ireland": "Irlanda", "Australia": "Austrália",
}
PERGUNTAS_APOIO = {
    "beneficios": "Oferece benefícios de saúde mental",
    "opcoes_cuidado": "Conhece as opções de cuidado",
    "programa_bem_estar": "Já falou de saúde mental em programa de bem-estar",
    "recursos_ajuda": "Oferece recursos para buscar ajuda",
    "anonimato": "Anonimato protegido ao usar o tratamento",
}

AVISO = (
    "Fonte: Mental Health in Tech Survey 2014, da OSMI (Open Sourcing Mental Illness), com 1.259 respostas. "
    "É uma amostra de quem quis responder, não da população de pessoas de tecnologia: os percentuais descrevem "
    "quem respondeu. Não separa cientistas de dados (não há coluna de profissão). Mostra associações, não causas, "
    "e não é diagnóstico. Se você está passando por sofrimento, procure um profissional de saúde ou o CVV (188)."
)


class ErroPainel(Exception):
    """Falha de leitura que o app mostra para o humano."""


# ---------------------------------------------------------------- leitura

def ler(marts: list[str] | None = None, caminho: Path | None = None) -> dict[str, pd.DataFrame]:
    """Lê os marts (só SELECT *) e fecha a conexão antes de devolver."""
    marts = marts or MARTS
    caminho = Path(caminho) if caminho else CAMINHO_BANCO
    if not caminho.exists():
        raise ErroPainel(
            f"O banco {caminho.name} não existe. Rode o pipeline antes:\n"
            "uv run python executar.py"
        )
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        existentes = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts'"
            ).fetchall()
        }
        faltando = [m for m in marts if m not in existentes]
        if faltando:
            raise ErroPainel(
                "Faltam marts no banco: " + ", ".join(faltando) + ".\n"
                "Rode antes: uv run python -m pipeline.marts"
            )
        return {m: con.execute(f"SELECT * FROM marts.{m}").df() for m in marts}
    finally:
        con.close()


# ---------------------------------------------------------------- formato

def _nulo(valor) -> bool:
    return valor is None or bool(pd.isna(valor))


def _trocar_separadores(texto: str) -> str:
    """'1,234.5' (padrão inglês) -> '1.234,5' (padrão brasileiro), sem usar locale."""
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def decimal(valor, casas: int = 1) -> str:
    if _nulo(valor):
        return "—"
    return _trocar_separadores(f"{float(valor):,.{casas}f}")


def inteiro(valor) -> str:
    return decimal(valor, 0)


def pct(valor, casas: int = 1) -> str:
    return "—" if _nulo(valor) else decimal(valor, casas) + "%"


def com_n(rotulo: str, n, quebra: bool = False) -> str:
    """'Mulher' + 251 -> 'Mulher (n=251)'; com quebra=True, o n vai para a linha de baixo (eixo vertical)."""
    return f"{rotulo}<br>n={inteiro(n)}" if quebra else f"{rotulo} (n={inteiro(n)})"


# ---------------------------------------------------------------- cartões

def cartoes(kpis: pd.DataFrame) -> list[tuple[str, str]]:
    """Os seis cartões: (rótulo com a definição, valor já formatado). Mart 10."""
    k = kpis.iloc[0]
    return [
        ("Respondentes · pessoas que responderam à pesquisa", inteiro(k["respondentes"])),
        ("Buscaram tratamento · % de quem respondeu", pct(k["pct_tratamento"])),
        ("Têm histórico familiar de doença mental · %", pct(k["pct_historico_familiar"])),
        ("Dizem que o empregador oferece benefícios de saúde mental · %", pct(k["pct_beneficios_sim"])),
        ("Receiam consequência negativa ao falar de saúde mental com o empregador · %", pct(k["pct_receio_consequencia"])),
        ("Falariam do assunto com o supervisor direto · %", pct(k["pct_falaria_supervisor"])),
    ]


# ---------------------------------------------------------------- gráficos

@dataclass
class Grafico:
    id: str
    figura: go.Figure
    nota: str = ""


def _base(fig: go.Figure, titulo: str, altura: int = 340) -> go.Figure:
    fig.update_layout(
        title={"text": titulo, "x": 0, "font": {"size": 14}},
        template="plotly_white",
        height=altura,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        showlegend=False,
        separators=",.",  # decimal com vírgula e milhar com ponto, no eixo e no hover
        font={"size": 12},
    )
    return fig


def _barras_horizontais(rotulos, valores, textos, titulo, eixo_x, maximo=None, hover=None) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(valores),
            y=list(rotulos),
            orientation="h",
            marker_color=COR,
            text=list(textos),
            textposition="outside",
            cliponaxis=False,
            customdata=list(hover) if hover is not None else None,
            hovertemplate="%{customdata}<extra></extra>" if hover is not None else None,
        )
    )
    fig.update_yaxes(autorange="reversed")  # o primeiro da lista fica em cima
    fig.update_xaxes(title_text=eixo_x, rangemode="tozero")
    if maximo is not None:
        fig.update_xaxes(range=[0, maximo])
    _base(fig, titulo)
    fig.update_layout(margin={"l": 10, "r": 90, "t": 50, "b": 10})  # espaço para o texto "837 (66,5%)" fora da barra
    return fig


def _barras_verticais(rotulos, valores, textos, titulo, eixo_y, hover=None) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(rotulos),
            y=list(valores),
            marker_color=COR,
            text=list(textos),
            textposition="outside",
            cliponaxis=False,
            customdata=list(hover) if hover is not None else None,
            hovertemplate="%{customdata}<extra></extra>" if hover is not None else None,
        )
    )
    fig.update_yaxes(title_text=eixo_y, range=[0, 100])
    return _base(fig, titulo)


def grafico_continentes(df: pd.DataFrame) -> Grafico:
    nomes = [CONTINENTES.get(c, c) for c in df["continente"]]
    fig = _barras_horizontais(
        nomes, df["respondentes"], [f"{inteiro(n)} ({pct(p)})" for n, p in zip(df["respondentes"], df["pct_das_respostas"])],
        "Quem respondeu · respostas por continente", "respostas",
    )
    return Grafico("continente", fig, "Contagem, não taxa. 'América' junta Norte, Central e Sul: a maior parte é dos Estados Unidos.")


def grafico_genero(df: pd.DataFrame) -> Grafico:
    grandes = df[df["respondentes"] >= MIN_AMOSTRA].sort_values("ordem")
    pequenos = df[df["respondentes"] < MIN_AMOSTRA].sort_values("ordem")
    rotulos = [com_n(g, n, True) for g, n in zip(grandes["genero"], grandes["respondentes"])]
    fig = _barras_verticais(
        rotulos, grandes["pct_tratamento"], [pct(v) for v in grandes["pct_tratamento"]],
        "Buscaram tratamento por gênero · % de cada grupo", "% do grupo que buscou tratamento",
    )
    nota = "Associação na amostra, não causa."
    if len(pequenos):
        citados = "; ".join(f"{g} ({inteiro(n)})" for g, n in zip(pequenos["genero"], pequenos["respondentes"]))
        nota += f" Ficaram de fora por terem menos de {MIN_AMOSTRA} respostas: {citados}. Estão no mart 02."
    return Grafico("genero", fig, nota)


def grafico_idade(df: pd.DataFrame) -> Grafico:
    faixas = df[df["faixa"] != "sem_idade_valida"].sort_values("ordem")
    sem = df.loc[df["faixa"] == "sem_idade_valida", "respondentes"]
    rotulos = [com_n(f, n, True) for f, n in zip(faixas["faixa"], faixas["respondentes"])]
    fig = _barras_verticais(
        rotulos, faixas["pct_tratamento"], [pct(v) for v in faixas["pct_tratamento"]],
        "Buscaram tratamento por faixa de idade · %", "% da faixa que buscou tratamento",
    )
    nota = "O n de cada faixa está no rótulo: faixa com poucas pessoas varia muito com poucas respostas."
    if len(sem):
        nota += f" {inteiro(sem.iloc[0])} respostas com idade impossível ficam fora."
    return Grafico("idade", fig, nota)


def grafico_apoio(df: pd.DataFrame) -> Grafico:
    sim = df[df["resposta"] == "Sim"].sort_values("pct_das_respostas", ascending=False)
    rotulos = [PERGUNTAS_APOIO.get(p, p) for p in sim["pergunta"]]
    fig = _barras_horizontais(
        rotulos, sim["pct_das_respostas"], [pct(v) for v in sim["pct_das_respostas"]],
        "O que o empregador oferece · % que respondeu Sim", "% de todas as respostas", maximo=100,
        hover=[f"{r}: {pct(p)} responderam Sim ({inteiro(n)} pessoas)" for r, p, n in zip(rotulos, sim["pct_das_respostas"], sim["respondentes"])],
    )
    return Grafico("apoio", fig, "Respostas, não fatos: é o que cada pessoa diz saber. 'Não sei' fica no denominador.")


def grafico_tamanho(df: pd.DataFrame) -> Grafico:
    f = df.sort_values("ordem")
    rotulos = [com_n(x, n, True) for x, n in zip(f["faixa"], f["respondentes"])]
    fig = _barras_verticais(
        rotulos, f["pct_beneficios_sim"], [pct(v) for v in f["pct_beneficios_sim"]],
        "Dizem ter benefícios, por tamanho da empresa · %", "% que respondeu Sim",
    )
    fig.update_xaxes(title_text="número de funcionários")
    return Grafico("tamanho", fig, "Faixas como vieram da pesquisa ('26-100' e '100-500' dividem o valor 100).")


def grafico_paises(df: pd.DataFrame) -> Grafico:
    f = df.sort_values(["posicao", "pais"])
    nomes = [PAISES.get(p, p) for p in f["pais"]]
    rotulos = [com_n(n, q) for n, q in zip(nomes, f["respondentes"])]
    fig = _barras_horizontais(
        rotulos, f["pct_beneficios_sim"], [pct(v) for v in f["pct_beneficios_sim"]],
        "Dizem ter benefícios, por país · %", "% que respondeu Sim", maximo=100,
    )
    return Grafico("paises", fig, f"Só países com {MIN_AMOSTRA}+ respostas. Os Estados Unidos têm a maior parte das respostas da pesquisa.")


def grafico_interferencia(df: pd.DataFrame) -> Grafico:
    f = df.sort_values("ordem")
    rotulos = [("Sem resposta" if i == "sem_resposta" else i) for i in f["interferencia"]]
    fig = _barras_verticais(
        rotulos, f["pct_das_respostas"], [f"{pct(p)}" for p in f["pct_das_respostas"]],
        "A condição interfere no trabalho? · % de todas as respostas", "% das respostas",
        hover=[f"{r}: {inteiro(n)} pessoas · {pct(t)} buscaram tratamento" for r, n, t in zip(rotulos, f["respondentes"], f["pct_tratamento"])],
    )
    return Grafico("interferencia", fig, "A pergunta é para quem tem uma condição; 'Sem resposta' são as pessoas que deixaram em branco.")


def grafico_consequencias(df: pd.DataFrame) -> Grafico:
    f = df.sort_values("ordem")
    rotulos, valores = [], []
    for _, linha in f.iterrows():
        rotulos.append(f"Receia consequência negativa · {linha['saude'].lower()}")
        valores.append(linha["pct_receio_sim"])
    for _, linha in f.iterrows():
        rotulos.append(f"Falaria numa entrevista · {linha['saude'].lower()}")
        valores.append(linha["pct_entrevista_sim"])
    fig = _barras_horizontais(
        rotulos, valores, [pct(v) for v in valores],
        "Falar de saúde mental × saúde física · % que respondeu Sim", "% de todas as respostas", maximo=100,
    )
    return Grafico(
        "consequencias", fig,
        "São duas perguntas diferentes: 'Sim' em receio é medo; 'Sim' em entrevista é disposição de falar.",
    )


def montar_graficos(dados: dict[str, pd.DataFrame]) -> dict[str, Grafico]:
    construtores = [
        (grafico_continentes, "respostas_por_continente"),
        (grafico_genero, "tratamento_por_genero"),
        (grafico_idade, "faixa_etaria"),
        (grafico_apoio, "apoio_empregador"),
        (grafico_tamanho, "tamanho_empresa"),
        (grafico_paises, "ranking_paises"),
        (grafico_interferencia, "interferencia_trabalho"),
        (grafico_consequencias, "consequencias_percebidas"),
    ]
    graficos = [funcao(dados[mart]) for funcao, mart in construtores]
    return {g.id: g for g in graficos}
