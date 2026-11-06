# Spec · Etapa 4 · Painel (`painel.py`, `app.py`, `relatorio.py`)

Quem lê: uma pessoa que quer entender o que a pesquisa mostra sobre saúde mental no trabalho em tecnologia,
**sem tirar conclusão que a amostra não sustenta**. Por isso a primeira coisa na tela são os números gerais com a
definição de cada um, e logo abaixo, "quem respondeu" (a amostra), antes de qualquer comparação.

O painel **não calcula nada**: só `SELECT * FROM marts.<nome>`, ordena, filtra linhas, corta com `head(n)`,
troca o nome de uma coluna por um rótulo, formata texto e desenha. Número novo na tela exige um `.sql` novo.

## Arquivos

- `painel.py`: leitura, formatação e gráficos. **Não importa Streamlit.**
- `app.py`: a página Streamlit, só arruma na tela o que o `painel.py` entrega.
  Exceção única, para a publicação online: se `saude_mental.duckdb` não existe, `app.py` chama `orquestrador.rodar()` uma vez (cache de recurso) e, se falhar, mostra a etapa que falhou e para. Não calcula nada; só prepara o banco.
- `relatorio.py`: gera `relatorio.html`, o mesmo painel congelado em um arquivo.

## Decisões

1. **Leitura.** `ler()` abre `saude_mental.duckdb` com `read_only=True`, lê os dez marts e **fecha a conexão** antes
   de devolver. Motivo: conexão aberta segura o arquivo e o `pipeline.marts` não consegue gravar com o painel de pé.
2. **Nenhum cálculo.** Proibido: `groupby`, `sum`, `mean`, `merge`, `pivot`, conta entre colunas. Permitido: ordenar,
   filtrar, `head(n)`, buscar uma linha, renomear, formatar.
3. **Formato.** Milhar com ponto, decimal com vírgula, sempre, sem depender do locale. Nulo vira `—`, nunca `nan`.
4. **Um gráfico por pergunta**, uma cor só, unidade no título; barras começam no zero; percentuais vão até 100.
5. **Amostra pequena não entra no gráfico de taxa.** Grupo com menos de **20** respostas (`MIN_AMOSTRA`) fica fora
   dos gráficos de percentual, e a nota diz quais e quantas pessoas eram. Motivo: "100% de 4 pessoas" não é resultado.
   O dado continua no mart.
6. **O n sempre aparece.** Rótulo ou dica de cada barra de percentual traz o número de respostas por trás.
7. **Cartões** (mart 10), cada rótulo com a definição fechada: Respondentes · Buscaram tratamento · Histórico familiar
   · Dizem que o empregador oferece benefícios · Receiam consequência ao falar de saúde mental com o empregador ·
   Falariam com o supervisor.
8. **Sem conclusão pronta.** Nenhuma nota diz "isso mostra que...". As notas dizem o que está medido, o denominador
   e o limite ("associação na amostra, não causa").
9. **Layout**, de cima para baixo: seis cartões; faixa 2 (quem responde): continente, gênero, idade; faixa 3 (o
   empregador): apoio, tamanho da empresa, países; faixa 4 (falar abertamente): interferência no trabalho,
   receio × disposição. Oito gráficos.
10. **Relatório HTML.** Mesmas funções de gráfico; `div_id` fixo (`g01`...); rodapé com data e hora de geração.
    A página é só apresentação e não muda nenhum número: cabeçalho com menu, seis cartões, aviso da amostra, as três
    faixas de gráficos e a seção "Sobre os dados". Layout fluido (grade que se reorganiza em computador, tablet e
    celular), tema claro e escuro conforme o sistema, sem biblioteca de CSS e com poucas linhas de JS (animação de
    entrada e item ativo do menu). O título de cada gráfico sai de dentro do Plotly e vai para a página, porque o
    Plotly não quebra título comprido e o corta no celular. Sem internet o Plotly não carrega: a página avisa.
    Os textos de apoio dizem o que está medido, nunca o que o resultado "prova" (decisão 8).
    **Dados completos:** no fim da página, uma aba para cada um dos dez marts (inclusive `historico_familiar`, que não
    tem gráfico), com a tabela inteira, como está no banco: nome real das colunas, percentuais com `%` e vírgula,
    milhar com ponto, nulo como `—`, e a origem (`sql/marts/NN_nome.sql`). Só formata e ordena; não calcula.
    **Detalhe por clique:** clicar numa barra abre a tela de detalhe daquele item (rótulo, valor, a dica do gráfico
    e a lista de todos os itens do gráfico, com o clicado destacado). A tela tem **Voltar** (volta ao mesmo ponto da
    página; o botão voltar do navegador e a tecla Esc fazem o mesmo) e **Início** (volta ao topo); o menu também
    tem **Início**. Os dados dessa tela são cópia do que o gráfico já desenha, guardados num JSON dentro da página:
    nenhum número novo, nenhum cálculo.
11. **Erro.** Sem `saude_mental.duckdb`, ou faltando qualquer mart: mensagem com o comando e para.
12. **Aviso fixo na página** sobre a amostra e sobre o que o painel não é (diagnóstico). O texto está em
    `painel.AVISO` e aparece no app e no relatório.

## Critérios de aceite

- Os seis cartões mostram: **1.259 · 50,6% · 39,1% · 37,9% · 23,2% · 41,0%**.
- Gênero: só Homem (45,4%) e Mulher (68,9%) no gráfico; a nota cita Outras identidades (14) e Não informado (4).
- País: EUA em cima (53,0%), Reino Unido embaixo (10,8%), sete barras.
- Busca por `groupby`, `.sum(`, `.mean(`, `.merge(` em `painel.py`, `app.py` e `relatorio.py` não encontra nada.
- Com o painel de pé, `uv run python -m pipeline.marts` roda sem erro de lock.
- `relatorio.html` abre com dois cliques, sem Python, e tem menos de 200 KB.
- No relatório, a seção **Dados completos** tem dez abas, e cada tabela tem exatamente as linhas do mart.
- No relatório, clicar numa barra abre o detalhe; **Voltar** devolve a página à mesma posição de rolagem e **Início** leva ao topo.
- No relatório, nenhum rótulo é cortado e a página não rola para o lado em 1440, 900 e 390 pixels de largura, nos temas claro e escuro.
