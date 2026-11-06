# Spec · Etapa 3 · Marts em SQL (`sql/marts/*.sql` e `pipeline/marts.py`)

Lê de `refined`, escreve em `marts`. Cada indicador do projeto é **um arquivo `.sql`**
de onde ele sai. O Python só executa os arquivos: nenhuma regra de negócio mora nele.

## Cuidado de leitura (vale para todos os indicadores)

A pesquisa é uma **amostra de quem quis responder**, divulgada por canais de tecnologia (66,5% das respostas vêm
da América, 59,7% dos EUA). Os percentuais descrevem **as pessoas que responderam**, e nunca dizem quantos
profissionais de tecnologia têm um transtorno ou buscam tratamento. Nenhum indicador prova causa: "quem diz
ter benefícios busca mais tratamento" é uma associação na amostra.

## Palavras fechadas (uma definição só, no projeto inteiro)

| Palavra                 | Quer dizer                                                                 | Em SQL                                   |
|-------------------------|----------------------------------------------------------------------------|------------------------------------------|
| **Respondente**         | Uma linha de `respostas` (uma pessoa que respondeu).                        | `count(*)`                               |
| **Buscou tratamento**   | Respondeu **Sim** a "Have you sought treatment for a mental health condition?" | `tratamento`                         |
| **Histórico familiar**  | Respondeu **Sim** a "Do you have a family history of mental illness?"       | `historico_familiar`                     |
| **Tem benefícios**      | Respondeu **Sim** a "Does your employer provide mental health benefits?" (`Não sei` fica no denominador) | `beneficios = 'Sim'` |
| **Receio de consequência** | Respondeu **Sim** a "...discussing a mental health issue with your employer would have negative consequences?" | `consequencia_saude_mental = 'Sim'` |
| **Disposição na entrevista** | Respondeu **Sim** a "Would you bring up a mental health issue with a potential employer in an interview?" | `falaria_entrevista_mental = 'Sim'` |
| **Falaria com o supervisor** | Respondeu **Sim** a "Would you be willing to discuss a mental health issue with your direct supervisor(s)?" | `falaria_supervisor = 'Sim'` |
| **Percentual**          | Sempre de 0 a 100, uma casa, e o **denominador é o grupo da linha** (ou todas as respostas, quando a coluna diz `pct_das_respostas`). | `round(100.0 * count(*) FILTER (...) / count(*), 1)` |

Atenção: "Sim" **não significa a mesma coisa** em perguntas diferentes (receio × disposição). Por isso o mart 07 tem
colunas separadas, e o nome da coluna carrega a pergunta (`pct_receio_sim`, `pct_entrevista_sim`).

## O grão das tabelas (e para onde o JOIN cresce)

| Tabela      | Grão                                              | Chave                  |
|-------------|---------------------------------------------------|------------------------|
| `respostas` | uma pessoa que respondeu                          | `id_resposta` (ordem no arquivo; não identifica ninguém) |
| `paises`    | um país                                           | `nome`                 |

| JOIN                       | Coluna do `ON`   | Linhas            | Resultado                                                    |
|----------------------------|------------------|-------------------|--------------------------------------------------------------|
| respostas ⋈ paises         | `pais = nome`    | 1.259 → 1.259 (`LEFT`) | N:1, uma resposta continua sendo uma linha; 0 sem cadastro |
| respostas ⋈ paises **por região** (armadilha) | `continente = continente` | **multiplica** | cada resposta cruzaria com todos os países do mesmo continente |

A armadilha: ligar pelo continente em vez do nome devolve **67.313 linhas** (53 vezes as 1.259 respostas; pela região
da ONU, 9.819) e nenhum erro. O `ON` é sempre o nome do país, a chave única, e o teste confere que o `JOIN` não mudou a contagem.

## Os 10 indicadores (um arquivo cada)

| Arquivo                          | Pergunta                                                         | Grão                              | Técnica                     | Linhas |
|----------------------------------|------------------------------------------------------------------|-----------------------------------|-----------------------------|--------|
| `01_respostas_por_continente`    | De onde vêm as respostas?                                        | um continente                     | `LEFT JOIN`, janela         | 5      |
| `02_tratamento_por_genero`       | Quem busca tratamento muda com o gênero?                         | um grupo de gênero                | `FILTER`                    | 4      |
| `03_historico_familiar`          | Histórico familiar muda a busca por tratamento?                  | Sim ou Não                        | `FILTER`                    | 2      |
| `04_interferencia_trabalho`      | A condição interfere no trabalho, e com que frequência?          | uma resposta                      | `coalesce`, janela          | 5      |
| `05_apoio_empregador`            | O que as pessoas sabem do apoio do empregador?                   | pergunta × resposta               | CTE com `UNION ALL`, janela | 15     |
| `06_tamanho_empresa`             | Empresa maior oferece mais benefícios e licença?                 | uma faixa de tamanho              | `CASE`, `FILTER`            | 6      |
| `07_consequencias_percebidas`    | Falar de saúde mental assusta mais que falar de saúde física?    | um tipo de saúde                  | CTE com `UNION ALL`         | 2      |
| `08_ranking_paises`              | Em que países mais se diz ter benefícios?                        | um país com 20+ respostas         | CTE, `HAVING`, `rank()`     | 7      |
| `09_faixa_etaria`                | A busca por tratamento muda com a idade?                         | uma faixa de idade                | `CASE`                      | 5      |
| `10_kpis`                        | O retrato geral                                                  | a pesquisa inteira                | `FILTER`                    | 1      |

Regras para todos os arquivos: o **grão na primeira linha**, como comentário; o grão de cada CTE dentro dela;
a pergunta junto; um único `SELECT` por arquivo. Total: **52 linhas**.

Decisões de indicador:
- **`HAVING >= 20` no ranking (08).** País com 8 respostas no topo é sorteio. O corte é uma escolha (20 mantém Austrália com 21 e tira a França, com 13); abaixo dele o percentual não é comparável.
- **`sem_resposta` em vez de nulo (04).** As 264 respostas sem valor aparecem como linha própria, para o total fechar em 1.259.
- **Faixa `sem_idade_valida` (09).** As 8 idades impossíveis ficam visíveis, e não somem do total.
- **Gênero com poucas respostas (02).** Mostra-se o `n`; "Outras identidades" tem 14 e "Não informado" tem 4: percentual de 4 pessoas (100%) não é conclusão.

## Números de conferência (medidos, e conferidos por um segundo caminho: pandas direto no CSV)

- Mart 10: **1.259** respondentes · **50,6%** buscaram tratamento · **39,1%** histórico familiar · **37,9%** dizem ter benefícios · **23,2%** receiam consequência · **41,0%** falariam com o supervisor.
- Mart 01: América 837 (66,5%), Europa 361, Oceania 29, Ásia 24, África 8.
- Mart 02: Homem 990 (45,4%), Mulher 251 (68,9%), Outras identidades 14 (78,6%), Não informado 4.
- Mart 03: com histórico familiar, 74,2% buscaram tratamento; sem, 35,5%.
- Mart 05: `beneficios` Sim 477 · Não 374 · Não sei 408; quem diz Sim busca tratamento em 63,9%, quem diz Não sei, em 37,0%.
- Mart 06: benefícios sobem de 11,7% (1–5 funcionários) para 64,9% (mais de 1.000).
- Mart 07: receio de consequência: saúde mental 23,2% × saúde física 4,8%; disposição na entrevista: 3,5% × 16,0%.
- Mart 08: EUA em 1º (53,0%), Reino Unido em último (10,8%); Alemanha e Irlanda empatam em 5º (11,1%).

**Dois marts, dois caminhos para o mesmo número** (a conferência que vira teste de qualidade):
`sum(respondentes)` dos marts 01, 02, 03, 04, 06 e 09 dá 1.259 em todos, e cada pergunta do mart 05 também soma 1.259.

## O que o executor (`pipeline/marts.py`) faz

1. Lê `sql/marts/*.sql` em ordem alfabética. Nome da tabela = nome do arquivo sem extensão e sem o prefixo `NN_`.
   Executa `CREATE TABLE marts.<nome> AS <arquivo>`; tira espaços e **um** ponto e vírgula do final e mais nada.
2. O schema `marts` é apagado e recriado a cada execução (um mart cujo arquivo foi apagado não pode continuar existindo).
3. Tudo numa transação: se qualquer passo falhar, `marts` volta ao que era.
4. Erros que param tudo (`sys.exit(1)`): falta tabela em `refined`; pasta vazia; arquivo sem prefixo `NN_`; dois
   arquivos com o mesmo nome de tabela; erro de SQL (mostra o arquivo); **mart com zero linhas**.
5. Saída: `✓ marts.<nome>  N linhas`, contagem do banco, milhar com ponto, e o total.

## Critérios de aceite

- Dez marts, **52 linhas** (5 + 4 + 2 + 5 + 15 + 6 + 2 + 7 + 5 + 1).
- Apagar um `.sql` e rodar de novo faz o mart sumir; arquivo com erro de sintaxe para tudo, com o nome do arquivo.
- Rodar duas vezes imprime a mesma coisa.
