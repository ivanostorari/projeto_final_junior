"""Gera relatorio.html: o mesmo painel numa página só, congelada. Executar com:

    uv run python relatorio.py

Spec: specs/painel.md (decisão 10). Reaproveita as funções de gráfico do
painel.py; não desenha nada que o painel não desenhe e não calcula nada.
Aqui só entra apresentação: layout, cores, texto de apoio e navegação.

O arquivo não fala com o banco: os números ficam congelados no dia da geração,
e por isso o rodapé diz a data e a hora. O Plotly vem do CDN uma vez só
(precisa de internet para abrir os gráficos; sem ele a página avisa). Cada
gráfico tem div_id fixo: sem ele o Plotly sorteia um id novo a cada execução e
o arquivo muda sem o dado mudar.

Sem biblioteca de CSS ou de JS além do Plotly: o CSS e o JS (poucas linhas, só
para animar a entrada e destacar o item do menu) ficam dentro do arquivo.
O tema escuro segue a configuração do sistema (prefers-color-scheme).

No fim da página, a seção "Dados completos" tem uma aba para cada um dos dez marts (inclusive o
historico_familiar, que não tem gráfico): as tabelas inteiras, como estão no banco, só formatadas.

Clicar numa barra abre a tela de detalhe daquele item (rótulo, valor, a dica do gráfico e a lista de todos os
itens do gráfico), com os botões Voltar e Início. Os dados dessa tela são os mesmos que o gráfico já desenha
(rótulo, texto da barra e dica), copiados para um JSON dentro da página: nada é calculado aqui.
"""

import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd

import painel

SAIDA = Path(__file__).resolve().parent / "relatorio.html"

# (âncora, texto do menu, título da faixa, o que a faixa mede, ids dos gráficos)
# Os textos dizem o que está medido; nenhum diz o que o resultado "prova" (spec, decisão 8).
LAYOUT = [
    (
        "quem", "Quem respondeu",
        "Quem respondeu, e quem buscou tratamento",
        "Contagem de respostas por continente e % de cada grupo que buscou tratamento, por gênero e por idade.",
        ["continente", "genero", "idade"],
    ),
    (
        "empregador", "O empregador",
        "O que o empregador oferece",
        "% que respondeu Sim sobre apoio, e sobre benefícios por tamanho da empresa e por país.",
        ["apoio", "tamanho", "paises"],
    ),
    (
        "conversa", "Falar abertamente",
        "Falar abertamente sobre o assunto",
        "Como a condição interfere no trabalho, e receio de consequência × disposição de falar.",
        ["interferencia", "consequencias"],
    ),
]

FONTE = 'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'

CSS = """
:root{
  --fundo:#f3f4fb;--superficie:#fff;--texto:#161a2e;--suave:#5b6384;--borda:#e3e6f3;--acento:#6366f1;
  --realce:#eef0ff;--sombra:0 1px 2px rgba(22,26,46,.05),0 12px 28px -16px rgba(40,44,110,.28);
  --hero:linear-gradient(125deg,#3730a3 0%,#6d28d9 52%,#0891b2 118%);--raio:18px;--grade:#e9ebf6;
}
@media (prefers-color-scheme:dark){:root{
  --fundo:#0c0f1e;--superficie:#151a31;--texto:#eceefb;--suave:#9aa3c9;--borda:#262d52;--acento:#8b8ff8;
  --realce:#1c2242;--sombra:0 1px 2px rgba(0,0,0,.4),0 14px 30px -16px rgba(0,0,0,.7);
  --hero:linear-gradient(125deg,#1e1b5e 0%,#3b1a78 55%,#0b5f78 120%);--grade:#262d52;
}}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{scroll-behavior:smooth;scroll-padding-top:76px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fundo);color:var(--texto);font-family:__FONTE__;line-height:1.55;
  font-size:clamp(15px,.35vw + 14px,17px);-webkit-font-smoothing:antialiased}
a{color:inherit}
.topo{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--fundo) 82%,transparent);
  backdrop-filter:saturate(1.6) blur(14px);-webkit-backdrop-filter:saturate(1.6) blur(14px);
  border-bottom:1px solid var(--borda)}
.topo nav{max-width:1320px;margin:0 auto;padding:0 clamp(14px,3vw,32px);height:60px;display:flex;align-items:center;gap:20px}
.marca{font-weight:700;letter-spacing:-.01em;white-space:nowrap;display:flex;align-items:center;gap:10px;text-decoration:none}
.marca i{width:12px;height:12px;border-radius:50%;background:var(--hero);display:inline-block;
  box-shadow:0 0 0 4px var(--realce)}
.menu{display:flex;gap:4px;margin-left:auto;overflow-x:auto;scrollbar-width:none}
.menu::-webkit-scrollbar{display:none}
.menu a{padding:8px 14px;border-radius:999px;font-size:.88rem;font-weight:550;color:var(--suave);
  text-decoration:none;white-space:nowrap;transition:background .2s,color .2s}
.menu a:hover{background:var(--realce);color:var(--texto)}
.menu a.ativo{background:var(--realce);color:var(--acento)}
.hero{background:var(--hero);color:#fff;position:relative;overflow:hidden;
  padding:clamp(40px,7vw,88px) clamp(16px,4vw,48px) clamp(88px,10vw,128px)}
.hero::before,.hero::after{content:"";position:absolute;border-radius:50%;filter:blur(2px);pointer-events:none}
.hero::before{width:420px;height:420px;right:-120px;top:-160px;background:radial-gradient(circle,rgba(255,255,255,.22),transparent 68%)}
.hero::after{width:360px;height:360px;left:-140px;bottom:-200px;background:radial-gradient(circle,rgba(34,211,238,.28),transparent 70%)}
.hero-in{max-width:1320px;margin:0 auto;position:relative;z-index:1}
.selo{display:inline-block;padding:6px 14px;border-radius:999px;background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.28);font-size:.82rem;font-weight:600;letter-spacing:.02em}
h1{margin:18px 0 14px;font-size:clamp(2rem,4.6vw,3.6rem);line-height:1.06;letter-spacing:-.03em;font-weight:800;max-width:16ch}
.lead{max-width:62ch;font-size:clamp(1rem,1vw + .8rem,1.25rem);color:rgba(255,255,255,.88);margin:0}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:26px}
.chip{padding:7px 14px;border-radius:12px;background:rgba(255,255,255,.12);font-size:.84rem;
  border:1px solid rgba(255,255,255,.2)}
main{max-width:1320px;margin:0 auto;padding:0 clamp(14px,3vw,32px) 40px}
.cartoes{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:clamp(10px,1.4vw,18px);
  margin-top:calc(clamp(88px,10vw,128px) * -.62);position:relative;z-index:2}
.cartao{background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);box-shadow:var(--sombra);
  padding:18px 18px 16px;display:flex;flex-direction:column;gap:8px;position:relative;overflow:hidden;
  transition:transform .25s ease,box-shadow .25s ease}
.cartao::before{content:"";position:absolute;left:0;right:0;top:0;height:4px;background:var(--hero)}
.cartao:hover{transform:translateY(-3px)}
.cartao .valor{font-size:clamp(1.7rem,2.4vw,2.35rem);font-weight:800;letter-spacing:-.03em;line-height:1.1;
  color:var(--acento)}
.cartao .rotulo{font-size:.82rem;color:var(--suave);line-height:1.4}
.aviso{margin:28px 0 8px;padding:18px 20px;border-radius:var(--raio);background:var(--realce);
  border:1px solid var(--borda);border-left:5px solid var(--acento);font-size:.92rem;color:var(--texto)}
.aviso b{display:block;margin-bottom:4px;color:var(--acento);font-size:.8rem;letter-spacing:.08em;text-transform:uppercase}
.aviso-rede{margin:12px 0 0;padding:12px 16px;border-radius:12px;background:#fff4e0;color:#6b4300;
  border:1px solid #f3d9a4;font-size:.9rem}
.bloco{margin-top:clamp(36px,6vw,72px)}
.bloco-cab{margin-bottom:18px;max-width:70ch}
.num{font-size:.8rem;font-weight:700;letter-spacing:.12em;color:var(--acento);text-transform:uppercase}
h2{margin:4px 0 6px;font-size:clamp(1.4rem,2.2vw,2rem);letter-spacing:-.02em;line-height:1.2}
.sub{margin:0;color:var(--suave);font-size:.98rem}
.faixa{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:clamp(12px,1.6vw,22px)}
.grafico{margin:0;background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);
  box-shadow:var(--sombra);padding:10px 10px 6px;min-width:0;display:flex;flex-direction:column}
.grafico .plotly-graph-div{width:100%!important}
.titulo-grafico{margin:8px 12px 0;font-size:.98rem;line-height:1.3;letter-spacing:-.01em}
.titulo-grafico span{color:var(--suave);font-weight:450}
.nota{margin-top:auto;padding:8px 12px 10px;font-size:.8rem;color:var(--suave);line-height:1.45;
  border-top:1px dashed var(--borda)}
.sobre{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:clamp(12px,1.6vw,22px)}
.info{background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);padding:20px 22px;
  box-shadow:var(--sombra)}
.info h3{margin:0 0 6px;font-size:1rem;letter-spacing:-.01em}
.info p{margin:0;color:var(--suave);font-size:.92rem}
footer{max-width:1320px;margin:0 auto;padding:28px clamp(14px,3vw,32px) 48px;color:var(--suave);font-size:.84rem;
  display:flex;flex-wrap:wrap;gap:8px 24px;justify-content:space-between;border-top:1px solid var(--borda)}
.js .revela{opacity:0;transform:translateY(18px);transition:opacity .6s ease,transform .6s ease}
.js .revela.visto{opacity:1;transform:none}
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 18px;border-radius:999px;border:1px solid var(--borda);
  background:var(--superficie);color:var(--texto);font:inherit;font-size:.92rem;font-weight:600;cursor:pointer;
  text-decoration:none;box-shadow:var(--sombra);transition:transform .2s,border-color .2s,color .2s}
.btn:hover{transform:translateY(-1px);border-color:var(--acento);color:var(--acento)}
.btn:focus-visible,.menu a:focus-visible,.marca:focus-visible{outline:3px solid var(--acento);outline-offset:2px}
.btn svg,.menu-home svg{width:18px;height:18px;flex:none}
.menu-home{display:inline-flex;align-items:center;gap:6px}
.dica{margin:14px 2px 0;font-size:.88rem;color:var(--suave)}
.grafico .plotly .barlayer .point path{cursor:pointer}
#detalhe{display:none;max-width:1100px;margin:0 auto;padding:clamp(20px,4vw,44px) clamp(14px,3vw,32px) 64px}
.em-detalhe #detalhe{display:block}
.em-detalhe .hero,.em-detalhe main{display:none}
.acoes{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:22px}
.trilha{margin:0 0 6px;font-size:.84rem;color:var(--suave)}
#det-rotulo{margin:0;font-size:clamp(1.6rem,3.4vw,2.6rem);letter-spacing:-.03em;line-height:1.15;outline:none}
.destaque{margin:20px 0 28px;padding:clamp(18px,3vw,28px);border-radius:var(--raio);background:var(--superficie);
  border:1px solid var(--borda);box-shadow:var(--sombra);position:relative;overflow:hidden}
.destaque::before{content:"";position:absolute;left:0;top:0;bottom:0;width:6px;background:var(--hero)}
.det-valor{font-size:clamp(2.4rem,7vw,4.4rem);font-weight:800;letter-spacing:-.04em;line-height:1.05;color:var(--acento)}
.det-unidade{margin:4px 0 0;color:var(--suave);font-size:.95rem}
.det-extra{margin:14px 0 0;padding-top:14px;border-top:1px dashed var(--borda);font-size:1rem}
.det-tab-t{margin:0 0 10px;font-size:1.05rem}
.tabela{width:100%;border-collapse:separate;border-spacing:0;background:var(--superficie);border:1px solid var(--borda);
  border-radius:var(--raio);overflow:hidden;box-shadow:var(--sombra);font-size:.95rem}
.tabela th{text-align:left;padding:12px 16px;font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;
  color:var(--suave);background:var(--realce)}
.tabela td{padding:12px 16px;border-top:1px solid var(--borda)}
.tabela td:last-child,.tabela th:last-child{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tabela tr.sel td{background:var(--realce);font-weight:700;color:var(--acento)}
#det-nota{margin:16px 2px 0;color:var(--suave);font-size:.88rem}
.abas{display:flex;gap:6px;overflow-x:auto;padding:6px;background:var(--superficie);border:1px solid var(--borda);
  border-radius:999px;scrollbar-width:none;box-shadow:var(--sombra)}
.abas::-webkit-scrollbar{display:none}
.aba{border:0;background:transparent;color:var(--suave);font:inherit;font-size:.88rem;font-weight:600;
  padding:9px 16px;border-radius:999px;cursor:pointer;white-space:nowrap;transition:background .2s,color .2s}
.aba:hover{background:var(--realce);color:var(--texto)}
.aba[aria-selected="true"]{background:var(--hero);color:#fff}
.aba:focus-visible{outline:3px solid var(--acento);outline-offset:2px}
.painel-aba{margin-top:20px}
.cab-tabela h3{margin:0 0 4px;font-size:1.2rem;letter-spacing:-.02em}
.cab-tabela p{margin:0 0 6px;color:var(--suave);font-size:.94rem;max-width:80ch}
.cab-tabela .origem{max-width:none;font-size:.8rem;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;margin-bottom:14px}
.rolagem{overflow-x:auto;border:1px solid var(--borda);border-radius:var(--raio);background:var(--superficie);
  box-shadow:var(--sombra)}
.grade{width:100%;border-collapse:collapse;font-size:.9rem;font-variant-numeric:tabular-nums}
.grade th{padding:12px 16px;text-align:left;background:var(--realce);white-space:nowrap;font-weight:600}
.grade th code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.78rem;color:var(--acento)}
.grade td{padding:11px 16px;border-top:1px solid var(--borda);white-space:nowrap}
.grade .dir{text-align:right}
.grade tbody tr:hover td{background:var(--realce)}
/* Plotly desenha em SVG com cores fixas: no tema escuro, as cores do texto e da grade são trocadas aqui */
@media (prefers-color-scheme:dark){
  .js-plotly-plot .plotly text{fill:var(--texto)!important}
  .js-plotly-plot .plotly .gridlayer path,.js-plotly-plot .plotly .zerolinelayer path{stroke:var(--grade)!important}
  .js-plotly-plot .plotly .xtick text,.js-plotly-plot .plotly .ytick text{fill:var(--suave)!important}
}
@media (max-width:1180px){
  .cartoes{grid-template-columns:repeat(3,minmax(0,1fr))}
  .faixa{grid-template-columns:repeat(2,minmax(0,1fr))}
  .faixa>:nth-child(3):last-child{grid-column:1/-1}
  .sobre{grid-template-columns:1fr}
}
@media (max-width:700px){
  .cartoes{grid-template-columns:repeat(2,minmax(0,1fr))}
  .faixa{grid-template-columns:minmax(0,1fr)}
  .marca span{display:none}
  .menu-home span{display:none}
  .tabela th,.tabela td{padding:10px 12px}
  .topo nav{gap:8px}
  .menu{margin-left:0}
  footer{flex-direction:column}
}
@media (max-width:380px){.cartoes{grid-template-columns:minmax(0,1fr)}}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  .js .revela{opacity:1;transform:none;transition:none}
  .cartao,.menu a{transition:none}
}
@media print{
  .topo{position:static}.hero{background:#fff;color:#000}.js .revela{opacity:1;transform:none}
  .cartao,.grafico,.info{box-shadow:none;break-inside:avoid}
}
""".replace("__FONTE__", FONTE)

JS = """
(function(){
  var corpo = document.body;
  var DADOS = JSON.parse(document.getElementById('dados-graficos').textContent);
  var posicao = 0, irTopo = false, depois = null;
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual'; /* o navegador não restaura a rolagem por conta própria: quem decide é o Voltar */
  var revelar = document.querySelectorAll('.revela');
  var links = document.querySelectorAll('.menu a[href^="#"]');

  /* animação de entrada e item ativo do menu */
  if ('IntersectionObserver' in window) {
    var entrada = new IntersectionObserver(function(itens){
      itens.forEach(function(i){ if (i.isIntersecting) { i.target.classList.add('visto'); entrada.unobserve(i.target); } });
    }, {threshold: 0.06});
    revelar.forEach(function(el){ entrada.observe(el); });
    var atual = new IntersectionObserver(function(itens){
      itens.forEach(function(i){
        if (!i.isIntersecting) return;
        links.forEach(function(a){ a.classList.toggle('ativo', a.getAttribute('href') === '#' + i.target.id); });
      });
    }, {rootMargin: '-35% 0px -60% 0px'});
    document.querySelectorAll('main section[id]').forEach(function(s){ atual.observe(s); });
  } else {
    revelar.forEach(function(el){ el.classList.add('visto'); });
  }

  /* tela de detalhe: tudo vem do JSON, escrito com textContent */
  function texto(id, valor){ document.getElementById(id).textContent = valor; }
  function celula(tr, valor){ var td = document.createElement('td'); td.textContent = valor; tr.appendChild(td); }
  function mostrar(id, i){
    var g = DADOS[id], p = g.pontos[i];
    texto('det-faixa', g.faixa); texto('det-pergunta', g.pergunta);
    document.getElementById('det-sep').hidden = (g.pergunta === g.faixa);
    texto('det-rotulo', p.rotulo); texto('det-valor', p.valor); texto('det-unidade', g.unidade);
    texto('det-extra', p.detalhe); document.getElementById('det-extra').hidden = !p.detalhe;
    texto('det-nota', g.nota); document.getElementById('det-nota').hidden = !g.nota;
    var linhas = document.getElementById('det-linhas'); linhas.textContent = '';
    g.pontos.forEach(function(q, j){
      var tr = document.createElement('tr');
      if (j === i) { tr.className = 'sel'; tr.setAttribute('aria-current', 'true'); }
      celula(tr, q.rotulo); celula(tr, q.valor); linhas.appendChild(tr);
    });
    corpo.classList.add('em-detalhe');
    window.scrollTo({top: 0, behavior: 'instant'});
    document.getElementById('det-rotulo').focus({preventScroll: true});
  }
  function emDetalhe(){ return corpo.classList.contains('em-detalhe'); }
  function sair(){
    corpo.classList.remove('em-detalhe');
    if (depois) { var alvo = document.querySelector(depois); depois = null; if (alvo) alvo.scrollIntoView(); }
    else window.scrollTo({top: irTopo ? 0 : posicao, behavior: 'instant'});
    irTopo = false;
  }
  function abrir(id, i){
    if (!emDetalhe()) posicao = window.scrollY;
    history.pushState({g: id, i: i}, '', '#detalhe');
    mostrar(id, i);
  }
  function voltar(){
    if (history.state && history.state.g) history.back(); else sair();
  }
  window.addEventListener('popstate', function(e){
    if (e.state && e.state.g) mostrar(e.state.g, e.state.i);
    else if (emDetalhe()) sair();
  });
  document.getElementById('voltar').addEventListener('click', voltar);
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && emDetalhe()) voltar(); });

  /* Início: de volta ao topo, e fecha o detalhe se estiver aberto. Menu: fecha o detalhe e vai à seção */
  document.querySelectorAll('[data-home]').forEach(function(a){
    a.addEventListener('click', function(e){
      e.preventDefault();
      if (emDetalhe()) { irTopo = true; voltar(); }
      else window.scrollTo({top: 0, behavior: 'smooth'});
    });
  });
  links.forEach(function(a){
    if (a.hasAttribute('data-home')) return;
    a.addEventListener('click', function(e){
      if (!emDetalhe()) return;
      e.preventDefault(); depois = a.getAttribute('href'); voltar();
    });
  });

  /* abas da seção Dados completos (sem JS, todas as tabelas aparecem uma abaixo da outra) */
  var abas = Array.prototype.slice.call(document.querySelectorAll('.aba'));
  function ativar(aba, foco){
    abas.forEach(function(a){
      var on = a === aba;
      a.setAttribute('aria-selected', on ? 'true' : 'false'); a.tabIndex = on ? 0 : -1;
      document.getElementById(a.getAttribute('aria-controls')).hidden = !on;
    });
    if (foco) aba.focus();
  }
  abas.forEach(function(a, i){
    a.addEventListener('click', function(){ ativar(a, false); });
    a.addEventListener('keydown', function(e){
      var novo = {ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: abas.length - 1}[e.key];
      if (novo === undefined) return;
      e.preventDefault(); ativar(abas[(novo + abas.length) % abas.length], true);
    });
  });
  if (abas.length) ativar(abas[0], false);

  /* clique em uma barra */
  function ligar(){
    var faltam = 0;
    document.querySelectorAll('.plotly-graph-div').forEach(function(el){
      if (el.dataset.ligado) return;
      if (typeof el.on !== 'function') { faltam++; return; }
      el.dataset.ligado = '1';
      el.on('plotly_click', function(ev){
        var p = ev.points && ev.points[0];
        if (p && DADOS[el.id]) abrir(el.id, p.pointIndex);
      });
    });
    return faltam;
  }
  window.addEventListener('load', function(){
    if (!window.Plotly) { document.getElementById('sem-plotly').hidden = false; return; }
    var tentativas = 0;
    (function tentar(){ if (ligar() && ++tentativas < 20) setTimeout(tentar, 150); })();
  });
})();
"""

# (mart, texto da aba, o que uma linha é). A ordem é a dos arquivos em sql/marts/ (01 a 10).
TABELAS = [
    ("respostas_por_continente", "Continentes",
     "Uma linha por continente (o do país informado). 'sem_cadastro' é país que não está na tabela de países."),
    ("tratamento_por_genero", "Gênero",
     "Uma linha por grupo de gênero. Grupos com poucas respostas aparecem aqui, mesmo ficando fora do gráfico."),
    ("historico_familiar", "Histórico familiar",
     "Uma linha por resposta a 'tem histórico familiar de doença mental?'. Este mart não tem gráfico na página."),
    ("interferencia_trabalho", "Interferência no trabalho",
     "Uma linha por resposta a 'a condição interfere no seu trabalho?'. 'sem_resposta' são as respostas em branco."),
    ("apoio_empregador", "Apoio do empregador",
     "Uma linha por pergunta de apoio × resposta. O denominador é o total de respostas: 'Não sei' conta."),
    ("tamanho_empresa", "Tamanho da empresa",
     "Uma linha por faixa de número de funcionários, como as faixas vieram da pesquisa."),
    ("consequencias_percebidas", "Consequências",
     "Uma linha por tipo de saúde. Receio e disposição são perguntas diferentes: 'Sim' não quer dizer o mesmo."),
    ("ranking_paises", "Países", "Uma linha por país com 20 respostas ou mais."),
    ("faixa_etaria", "Faixa etária",
     "Uma linha por faixa de idade. 'sem_idade_valida' são as respostas com idade fora de 16 a 80."),
    ("kpis", "Indicadores gerais", "Uma única linha: os seis cartões do topo da página."),
]

ICONE_INICIO = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/>'
    '<path d="M10 20v-6h4v6"/></svg>'
)
ICONE_VOLTAR = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5"/><path d="m11 18-6-6 6-6"/></svg>'
)

# Tela de detalhe (escondida até clicar numa barra). Os textos são preenchidos pelo JS com os dados do JSON.
DETALHE = (
    '<section id="detalhe" aria-label="Detalhe do item" aria-live="polite">'
    '<div class="acoes"><button type="button" class="btn" id="voltar">'
    f"{ICONE_VOLTAR}Voltar</button>"
    f'<a class="btn" href="#topo" data-home>{ICONE_INICIO}Início</a></div>'
    '<p class="trilha">Início › <span id="det-faixa"></span>'
    '<span id="det-sep"> › <span id="det-pergunta"></span></span></p>'
    '<h2 id="det-rotulo" tabindex="-1"></h2>'
    '<div class="destaque"><div class="det-valor" id="det-valor"></div><p class="det-unidade" id="det-unidade"></p>'
    '<p class="det-extra" id="det-extra" hidden></p></div>'
    '<h3 class="det-tab-t">Todos os itens deste gráfico</h3>'
    '<table class="tabela"><thead><tr><th>Item</th><th>Valor</th></tr></thead><tbody id="det-linhas"></tbody></table>'
    '<p id="det-nota" hidden></p></section>'
)

INFORMACOES = [
    (
        "De onde vêm os números",
        ("Cada número vem de uma consulta em sql/marts/. Esta página não calcula nada: lê as tabelas prontas "
         "(marts) e desenha."),
    ),
    (
        "Amostra pequena fica de fora",
        (f"Grupos com menos de {painel.MIN_AMOSTRA} respostas não entram nos gráficos de percentual. "
         "A nota de cada gráfico diz quem ficou de fora e quantas pessoas eram."),
    ),
    (
        "O n e o denominador",
        ("O número de respostas (n) aparece no rótulo ou na dica de cada barra de percentual. "
         "Quando há \"Não sei\", ele conta no denominador."),
    ),
]


def _titulo(fig) -> tuple[str, str, str]:
    """Tira o título de dentro do gráfico e devolve (html, pergunta, unidade): o Plotly não quebra título
    comprido e, no celular, o corta. Antes do ' · ' fica a pergunta; depois, a unidade."""
    texto = fig.layout.title.text or ""
    fig.update_layout(title={"text": None}, margin={"t": 8})
    pergunta, _, unidade = texto.partition(" · ")
    sufixo = f' <span>· {escape(unidade)}</span>' if unidade else ""
    return f'<h3 class="titulo-grafico">{escape(pergunta)}{sufixo}</h3>', pergunta, unidade


def _pontos(fig) -> list[dict]:
    """O que o gráfico já desenha, item a item: rótulo, texto da barra e dica. Só copia; não calcula."""
    traco = fig.data[0]
    rotulos = traco.y if traco.orientation == "h" else traco.x
    textos = traco.text if traco.text is not None else [""] * len(rotulos)
    dicas = traco.customdata if traco.customdata is not None else [""] * len(rotulos)
    return [
        {"rotulo": str(r).replace("<br>", " · "), "valor": str(t), "detalhe": str(d)}
        for r, t, d in zip(rotulos, textos, dicas, strict=True)
    ]


def _celula(coluna: str, valor) -> tuple[str, str]:
    """(classe, texto) de uma célula da tabela. Só formata: pct_* com %, contagens com milhar, nulo vira —."""
    if isinstance(valor, str):
        return "", valor
    if coluna.startswith("pct_"):
        return "dir", painel.pct(valor)
    if pd.api.types.is_integer(valor) or coluna in ("respondentes", "ordem", "posicao"):
        return "dir", painel.inteiro(valor)
    return "dir", painel.decimal(valor)


def _tabela(df: pd.DataFrame) -> str:
    colunas = list(df.columns)
    ordenado = df
    for chave in ("posicao", "ordem"):  # ordenar é permitido; apoio_empregador (tem 'pergunta') fica como vem
        if chave in colunas and "pergunta" not in colunas:
            ordenado = df.sort_values(chave, kind="stable")
            break
    cabecalho = "".join(
        f'<th class="{"dir" if pd.api.types.is_numeric_dtype(df[c]) else ""}"><code>{escape(c)}</code></th>'
        for c in colunas
    )
    linhas = []
    for _, linha in ordenado.iterrows():
        celulas = []
        for c in colunas:
            classe, texto = _celula(c, linha[c])
            celulas.append(f'<td class="{classe}">{escape(texto)}</td>')
        linhas.append(f"<tr>{''.join(celulas)}</tr>")
    return (
        f'<div class="rolagem"><table class="grade"><thead><tr>{cabecalho}</tr></thead>'
        f'<tbody>{"".join(linhas)}</tbody></table></div>'
    )


def _abas(dados: dict) -> str:
    botoes, paineis = [], []
    for n, (mart, nome, descricao) in enumerate(TABELAS, start=1):
        df = dados[mart]
        ativa = n == 1
        botoes.append(
            f'<button type="button" role="tab" class="aba" id="aba-{mart}" aria-controls="painel-{mart}" '
            f'aria-selected="{"true" if ativa else "false"}" tabindex="{0 if ativa else -1}">'
            f"{escape(nome)}</button>"
        )
        total = len(df)
        paineis.append(
            f'<div role="tabpanel" class="painel-aba" id="painel-{mart}" aria-labelledby="aba-{mart}">'
            f'<div class="cab-tabela"><h3>{n:02d} · {escape(nome)}</h3><p>{escape(descricao)}</p>'
            f'<p class="origem">marts.{escape(mart)} · sql/marts/{n:02d}_{escape(mart)}.sql · '
            f'{painel.inteiro(total)} {"linha" if total == 1 else "linhas"}</p></div>{_tabela(df)}</div>'
        )
    lista = f'<div class="abas" role="tablist" aria-label="Tabelas dos indicadores">{"".join(botoes)}</div>'
    return lista + "".join(paineis)


def _tema(fig) -> None:
    """Só aparência: fundo transparente (o cartão da página dá a cor) e a mesma fonte da página."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONTE, "size": 12},
        hoverlabel={"font": {"family": FONTE}},
    )


def montar_html(dados: dict, agora: datetime | None = None) -> str:
    agora = agora or datetime.now()
    graficos = painel.montar_graficos(dados)
    lista_cartoes = painel.cartoes(dados["kpis"])
    respondentes = lista_cartoes[0][1]

    cartoes = "".join(
        f'<article class="cartao"><div class="valor">{escape(valor)}</div>'
        f'<div class="rotulo">{escape(rotulo)}</div></article>'
        for rotulo, valor in lista_cartoes
    )

    faixas = []
    detalhes = {}
    contador = 0
    for posicao, (ancora, _menu, titulo, descricao, ids) in enumerate(LAYOUT, start=1):
        caixas = []
        for id_ in ids:
            contador += 1
            g = graficos[id_]
            cabecalho, pergunta, unidade = _titulo(g.figura)
            _tema(g.figura)
            detalhes[f"g{contador:02d}"] = {
                "faixa": titulo, "pergunta": pergunta, "unidade": unidade, "nota": g.nota,
                "pontos": _pontos(g.figura),
            }
            corpo = g.figura.to_html(
                full_html=False,
                include_plotlyjs="cdn" if contador == 1 else False,
                div_id=f"g{contador:02d}",
                config={"displayModeBar": False, "responsive": True},
            )
            nota = f'<figcaption class="nota">{escape(g.nota)}</figcaption>' if g.nota else ""
            caixas.append(f'<figure class="grafico revela">{cabecalho}{corpo}{nota}</figure>')
        faixas.append(
            f'<section class="bloco" id="{ancora}"><div class="bloco-cab revela">'
            f'<span class="num">{posicao:02d}</span><h2>{escape(titulo)}</h2><p class="sub">{escape(descricao)}</p></div>'
            f'<div class="faixa" style="--n:{len(ids)}">{"".join(caixas)}</div></section>'
        )

    sobre = "".join(
        f'<div class="info revela"><h3>{escape(t)}</h3><p>{escape(p)}</p></div>' for t, p in INFORMACOES
    )
    menu = "".join(f'<a href="#{a}">{escape(m)}</a>' for a, m, *_ in LAYOUT)
    # "</" vira "<\/" para que nenhum texto feche o <script> sem querer
    dados_json = json.dumps(detalhes, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    data = agora.strftime("%d/%m/%Y %H:%M")

    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        "<title>Saúde mental na tecnologia · pesquisa OSMI 2014</title>"
        "<script>document.documentElement.className+=' js'</script>"
        f"<style>{CSS}</style></head><body>"
        '<header class="topo"><nav>'
        '<a class="marca" href="#topo" data-home><i></i><span>Saúde mental em tech</span></a>'
        f'<div class="menu"><a class="menu-home" href="#topo" data-home>{ICONE_INICIO}<span>Início</span></a>'
        f'<a href="#numeros">Números</a>{menu}<a href="#dados">Dados completos</a>'
        '<a href="#sobre">Sobre os dados</a></div>'
        "</nav></header>"
        f"{DETALHE}"
        '<section class="hero" id="topo"><div class="hero-in">'
        '<span class="selo">Pesquisa OSMI 2014</span>'
        "<h1>Saúde mental na tecnologia</h1>"
        f'<p class="lead">O que {escape(respondentes)} pessoas responderam sobre saúde mental e trabalho em '
        "tecnologia, com o tamanho da amostra e o denominador de cada número à vista.</p>"
        '<div class="chips"><span class="chip">Fonte: OSMI (Open Sourcing Mental Illness)</span>'
        f'<span class="chip">{escape(respondentes)} respostas</span>'
        '<span class="chip">Página gerada por relatorio.py</span></div></div></section>'
        '<main><section id="numeros" aria-label="Números gerais">'
        f'<div class="cartoes revela">{cartoes}</div></section>'
        f'<aside class="aviso revela" role="note"><b>Leia antes</b>{escape(painel.AVISO)}</aside>'
        '<p class="dica revela">Clique em uma barra de qualquer gráfico para ver o detalhe dela. O botão '
        "<b>Voltar</b> leva ao mesmo ponto da página, e <b>Início</b> ao topo.</p>"
        '<div class="aviso-rede" id="sem-plotly" hidden>Os gráficos precisam de internet para carregar a '
        "biblioteca Plotly. Conecte-se e recarregue a página.</div>"
        f'{"".join(faixas)}'
        '<section class="bloco" id="dados"><div class="bloco-cab revela"><span class="num">04</span>'
        "<h2>Dados completos</h2>"
        '<p class="sub">As tabelas inteiras dos dez indicadores, como estão no banco (só formatadas). '
        "Inclui o que não cabe nos gráficos.</p></div>"
        f'<div class="revela">{_abas(dados)}</div></section>'
        '<section class="bloco" id="sobre"><div class="bloco-cab revela"><span class="num">05</span>'
        "<h2>Sobre os dados</h2>"
        '<p class="sub">Como ler os gráficos desta página.</p></div>'
        f'<div class="sobre">{sobre}</div></section></main>'
        f"<footer><span>Dados de {escape(data)}</span>"
        "<span>Os números ficam congelados no dia da geração. Para atualizar: "
        "uv run python executar.py e uv run python relatorio.py.</span></footer>"
        f'<script type="application/json" id="dados-graficos">{dados_json}</script>'
        f"<script>{JS}</script></body></html>"
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
