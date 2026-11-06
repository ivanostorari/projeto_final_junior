"""Gera relatorio.html: o mesmo painel num arquivo só, congelado. Executar com:

    uv run python relatorio.py

Spec: specs/painel.md (decisão 10). Reaproveita as funções de gráfico do
painel.py; não desenha nada que o painel não desenhe e não calcula nada.

O arquivo não fala com o banco: os números ficam congelados no dia da geração,
e por isso o rodapé diz a data e a hora. O Plotly vem do CDN uma vez só
(precisa de internet para abrir os gráficos). Cada gráfico tem div_id fixo:
sem ele o Plotly sorteia um id novo a cada execução e o arquivo muda sem o
dado mudar.
"""

import sys
from datetime import datetime
from html import escape
from pathlib import Path

import painel

SAIDA = Path(__file__).resolve().parent / "relatorio.html"

# (título da faixa, ids dos gráficos, larguras em colunas de 12)
LAYOUT = [
    ("Quem respondeu, e quem buscou tratamento", ["continente", "genero", "idade"], [4, 4, 4]),
    ("O que o empregador oferece", ["apoio", "tamanho", "paises"], [4, 4, 4]),
    ("Falar abertamente sobre o assunto", ["interferencia", "consequencias"], [6, 6]),
]

CSS = """
body{font-family:system-ui,sans-serif;margin:0;background:#f6f7fb;color:#1d2433}
main{max-width:1400px;margin:0 auto;padding:24px}
h1{margin:0 0 12px;font-size:26px}
h2{font-size:17px;margin:20px 0 8px}
.aviso{background:#eaedf8;border-radius:8px;padding:12px 14px;font-size:13px;margin-bottom:16px}
.cartoes{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:8px}
.cartao{background:#fff;border-radius:8px;padding:14px;box-shadow:0 1px 2px #0002}
.cartao .rotulo{font-size:12px;color:#55607a;min-height:48px}
.cartao .valor{font-size:26px;font-weight:600;margin-top:4px}
.faixa{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin-bottom:12px}
.grafico{background:#fff;border-radius:8px;padding:8px;box-shadow:0 1px 2px #0002}
.nota{font-size:12px;color:#55607a;padding:0 8px 6px}
footer{font-size:12px;color:#55607a;margin-top:16px}
@media(max-width:900px){.cartoes{grid-template-columns:repeat(2,1fr)}.faixa{display:block}.grafico{margin-bottom:12px}}
"""


def montar_html(dados: dict, agora: datetime | None = None) -> str:
    agora = agora or datetime.now()
    graficos = painel.montar_graficos(dados)

    cartoes = "".join(
        f'<div class="cartao"><div class="rotulo">{escape(rotulo)}</div><div class="valor">{escape(valor)}</div></div>'
        for rotulo, valor in painel.cartoes(dados["kpis"])
    )

    faixas = []
    contador = 0
    for titulo, ids, larguras in LAYOUT:
        caixas = []
        for id_, largura in zip(ids, larguras):
            contador += 1
            g = graficos[id_]
            corpo = g.figura.to_html(
                full_html=False,
                include_plotlyjs="cdn" if contador == 1 else False,
                div_id=f"g{contador:02d}",
                config={"displayModeBar": False},
            )
            nota = f'<div class="nota">{escape(g.nota)}</div>' if g.nota else ""
            caixas.append(f'<div class="grafico" style="grid-column:span {largura}">{corpo}{nota}</div>')
        faixas.append(f'<h2>{escape(titulo)}</h2><div class="faixa">{"".join(caixas)}</div>')

    rodape = f"Dados de {agora.strftime('%d/%m/%Y %H:%M')}"
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Saúde mental na tecnologia</title><style>{CSS}</style></head><body><main>"
        f'<h1>Saúde mental na tecnologia · pesquisa OSMI 2014</h1><div class="aviso">{escape(painel.AVISO)}</div>'
        f'<div class="cartoes">{cartoes}</div>{"".join(faixas)}<footer>{escape(rodape)}</footer></main></body></html>'
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        dados = painel.ler()
    except painel.ErroPainel as erro:
        print(erro)
        sys.exit(1)
    SAIDA.write_text(montar_html(dados), encoding="utf-8")
    print(f"✓ {SAIDA.name}  {SAIDA.stat().st_size / 1024:,.0f} KB")


if __name__ == "__main__":
    main()
