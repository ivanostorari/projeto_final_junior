# Spec · Etapa 4 · Painel (`painel.py`, `app.py`, `relatorio.py`)

Quem lê: uma pessoa que quer entender o que a pesquisa mostra sobre saúde mental no trabalho em tecnologia,
**sem tirar conclusão que a amostra não sustenta**. Por isso a primeira coisa na tela são os números gerais com a
definição de cada um, e logo abaixo, "quem respondeu" (a amostra), antes de qualquer comparação.

O painel **não calcula nada**: só `SELECT * FROM marts.<nome>`, ordena, filtra linhas, corta com `head(n)`,
troca o nome de uma coluna por um rótulo, formata texto e desenha. Número novo na tela exige um `.sql` novo.

## Arquivos

- `painel.py`: leitura, formatação e gráficos. **Não importa Streamlit.**
- `app.py`: a página Streamlit, só arruma na tela o que o `painel.py` entrega.
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
