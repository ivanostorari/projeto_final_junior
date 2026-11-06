# Spec · Etapa 5 · Testes (`test/`)

Rodar: `uv run pytest --cov`. Mínimo de cobertura: 95% (`fail_under` no `pyproject.toml`); o CI (`.github/workflows/ci.yml`) roda os mesmos comandos a cada pull request e a cada push na `main`.

## Regra do projeto

**Nenhum teste abre `saude_mental.duckdb` nem lê `raw/`.** Motivo: um teste que depende do dado real passa ou falha
conforme o dado, não conforme o código; e só funcionaria depois de rodar o pipeline inteiro. Todo teste constrói o
próprio banco temporário (`tmp_path`) com **dados inventados**, pequenos, em que cada linha existe por um motivo
escrito no `conftest.py`. Além disso, por ser dado sobre saúde mental: **nenhum texto de resposta real** aparece
nos testes.

## Os dados inventados (`test/conftest.py`)

Oito respostas (`r1`..`r8`) e seis países. Cada resposta cobre um caso de borda do dado real:

- gênero escrito de formas diferentes (`male`, `FEMALE ` com maiúsculas e espaço no fim, `Cis Man`, `Female (trans)`,
  `M`, `woman`) e três que não são Homem/Mulher (`non-binary`, `Nah`);
- idade impossível (`99999999999`, `-5`) e idade-limite válida (`17`);
- país escrito diferente da tabela de países (`Czech Republic`, `Bahamas, The`);
- resposta sem valor em `work_interfere` (nulo), e valores com apóstrofo (`Don't know`);
- respostas que fazem cada faixa de tamanho de empresa aparecer.

Os valores esperados dos marts foram **calculados à mão** sobre essas oito linhas, nunca copiados do resultado do código.
O ranking de países (mart 08) exige 20 respostas por país, então tem teste próprio com respostas **geradas**
(EUA 20, Reino Unido 20, Canadá 20, Alemanha 19: a Alemanha fica de fora por **uma** resposta).

## O que cada arquivo de teste garante

| Arquivo                | Garante                                                                                       |
|------------------------|-----------------------------------------------------------------------------------------------|
| `test_db.py`           | `gravar()` troca a tabela inteira e devolve a contagem do banco; caminhos não dependem da pasta atual |
| `test_ingestao.py`     | `NA` vira nulo só na pesquisa (não em países); tudo entra como texto; arquivo faltando para antes de gravar |
| `test_transformacao.py`| tipos, idade fora de 16..80 vira nulo (e o original fica), gênero agrupado, valor fora do dicionário para tudo, país sem cadastro para tudo, `comments` fora, rollback |
| `test_marts.py`        | o executor: nome da tabela vem do arquivo, apagar `.sql` apaga o mart, erro de SQL e mart vazio param tudo |
| `test_sql_marts.py`    | os `.sql` **reais** sobre os dados inventados: valores à mão, `JOIN` sem multiplicar linhas, limite de 20 no ranking e empate |
| `test_painel.py`       | formato brasileiro, grupo com menos de 20 respostas fora do gráfico (nota diz quem), receio × disposição em barras separadas, leitura somente leitura, nenhum cálculo no código |
| `test_relatorio.py`    | HTML idêntico para os mesmos dados e a mesma data, ids fixos, rodapé com data                 |
| `test_app.py`          | a página Streamlit abre sem exceção, mostra erro legível sem banco, botão recarrega           |
| `test_executar.py`     | apaga o banco, roda as três etapas na ordem, uma falha impede as seguintes                    |
| `test_ver_marts.py`    | imprime os dez marts (ou só os pedidos), mart inexistente e banco ausente saem com código 1   |
| `test_conferir.py`     | a lógica de `conferir.py` (compara com o esperado, arredonda float, sai com 1 se divergir) sobre um banco inventado |

## Fora do pytest: `conferir.py`

`uv run python conferir.py` abre o banco **real** (somente leitura) e confere 31 números: os da tela, as somas
cruzadas e os valores de seis erros comuns ("média de médias" etc.), que têm de continuar diferentes do certo.
Fica fora de `test/` de propósito: a regra deste projeto é que teste do pytest não abre o banco real, e aqui abrir
o banco é o objetivo. Os números esperados são os do README (seção "Números da tela").

## Limites assumidos

- Os testes não provam que o dado real está certo; quem confere o dado real são as conferências cruzadas da spec
  dos marts (por exemplo, `sum(respondentes)` igual em seis marts, e o recálculo por um segundo caminho em pandas), feitas rodando o pipeline.
- O **visual** do painel não é testado por teste automático: foi conferido uma vez, abrindo o `relatorio.html` num
  navegador (Chromium sem tela) e olhando a imagem. Não foi conferido em celular nem em outros navegadores.
