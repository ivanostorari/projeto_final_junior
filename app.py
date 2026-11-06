"""A página do painel. Executar com:

    uv run streamlit run app.py

Só arruma na tela o que o painel.py entrega: não lê o banco por conta própria
e não calcula nada (spec: specs/painel.md).
"""

import streamlit as st

import painel

st.set_page_config(page_title="Saúde mental na tecnologia", layout="wide")


@st.cache_data(show_spinner=False)
def carregar():
    return painel.ler()


def mostrar(grafico: painel.Grafico) -> None:
    st.plotly_chart(grafico.figura, width="stretch")
    if grafico.nota:
        st.caption(grafico.nota)


cabecalho, botao = st.columns([5, 1])
cabecalho.title("Saúde mental na tecnologia · pesquisa OSMI 2014")
if botao.button("Recarregar dados"):
    carregar.clear()

try:
    dados = carregar()
except painel.ErroPainel as erro:
    st.error(str(erro))
    st.stop()

st.info(painel.AVISO)

# Faixa 1: o retrato geral
colunas = st.columns(6)
for coluna, (rotulo, valor) in zip(colunas, painel.cartoes(dados["kpis"])):
    coluna.metric(rotulo, valor)

graficos = painel.montar_graficos(dados)

# Faixa 2: quem respondeu e quem busca ajuda?
st.subheader("Quem respondeu, e quem buscou tratamento")
a, b, c = st.columns(3)
with a:
    mostrar(graficos["continente"])
with b:
    mostrar(graficos["genero"])
with c:
    mostrar(graficos["idade"])

# Faixa 3: o que o empregador oferece?
st.subheader("O que o empregador oferece")
d, e, f = st.columns(3)
with d:
    mostrar(graficos["apoio"])
with e:
    mostrar(graficos["tamanho"])
with f:
    mostrar(graficos["paises"])

# Faixa 4: falar abertamente
st.subheader("Falar abertamente sobre o assunto")
g, h = st.columns(2)
with g:
    mostrar(graficos["interferencia"])
with h:
    mostrar(graficos["consequencias"])
