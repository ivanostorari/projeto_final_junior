# Spec · Etapa 2 · Transformação (`pipeline/transformacao.py`, `pipeline/dicionario.py`)

Lê de `raw`, escreve em `refined`. Nunca escreve em `raw`. Executar:
`uv run python -m pipeline.transformacao`.

Cada número abaixo foi **contado no banco antes de virar decisão**.

## O que a investigação encontrou

| Achado                                                                                              | Número                      |
|-----------------------------------------------------------------------------------------------------|-----------------------------|
| Respostas / países                                                                                  | 1.259 / 250                 |
| Linhas de `respostas` idênticas a outra                                                             | 0                           |
| Timestamps que se repetem (duas pessoas respondendo no mesmo segundo)                               | 13 timestamps               |
| Idades impossíveis: `-1726`, `-29`, `-1`, `5`, `8`, `11`, `329`, `99999999999`                      | 8 respostas                 |
| Idades dentro de 16 a 80 (mínima 18, máxima 72)                                                     | 1.251                       |
| Grafias diferentes de `Gender` (texto livre) / depois de minúscula e sem espaços nas pontas         | 49 / 41                     |
| Gênero após agrupar: Homem / Mulher / Outras identidades / Não informado                            | 990 / 251 / 14 / 4          |
| Nulos: `work_interfere` / `state` / `self_employed` / `comments`                                    | 264 / 515 / 18 / 1.095      |
| `work_interfere` nulo entre quem **não** buscou tratamento                                          | 260 dos 264                 |
| Respostas com estado dos EUA e país que não é os EUA (Letônia/NY, Israel/MD, Bahamas/IL, Bulgária/UT) | 4                           |
| Países da pesquisa / sem casar com `paises.name_short`: `Bahamas, The` e `Czech Republic`            | 48 / 2 respostas            |
| `paises.name_short` repetido                                                                        | 0                           |

## As decisões

### 1. Escopo e nomes
Entram as duas tabelas. As colunas ganham nome em português e `snake_case` (mapa literal em `TABELAS`).
Só uma coluna é descartada, a decisão 8.

### 2. Chave
`respostas` **não tem chave natural**: não há identificador (anônima) e o timestamp se repete 13 vezes. A chave é
`id_resposta` = posição da linha no arquivo (1 a 1.259), tirada do `rowid` que o banco guarda em `raw`.
Motivo: sem isso nenhuma linha pode ser apontada ("a resposta 802"). Fica escrito que **o id não identifica a
pessoa**, só a ordem do arquivo. `paises` tem chave `nome` (conferida: nenhuma repetição, senão para tudo).

### 3. Tipos
- `Timestamp` → `TIMESTAMP`, formato declarado `'%Y-%m-%d %H:%M:%S'` (`respondido_em`).
- `Age` → `idade_informada` `BIGINT` (precisa: `99999999999` não cabe em `INTEGER`) e `idade` `INTEGER`.
- Colunas só Sim/Não (`treatment`, `family_history`, `self_employed`, `remote_work`, `tech_company`,
  `obs_consequence`) → `BOOLEAN`. Motivo: `avg(tratamento::int)` é a conta do indicador; texto convida a erro.
- Demais respostas fechadas (três ou mais opções) ficam `VARCHAR` já em português, pelo mapa de
  `dicionario.py` (`Don't know` → `Não sei`, `Some of them` → `Alguns`...).

### 4. Valor que não está no dicionário **para tudo**
Cada coluna de resposta tem um mapa de valores permitidos. Valor fora do mapa, `Timestamp` que não converte ou
`Age` que não vira número: `sys.exit(1)` dizendo tabela, coluna, quantos e um exemplo. `TRY_CAST` só é usado
*antes*, para detectar. Motivo: um nulo fabricado pela conversão fica indistinguível, para sempre, de um nulo
verdadeiro da pesquisa.

### 5. Idade impossível: valor original fica, `idade` vira nulo
Fora de **16 a 80** (idade mínima de trabalho / limite plausível), `idade` é **nula** e o valor original
continua em `idade_informada`. São 8 respostas, e a mensagem final conta quantas foram. Motivo: dizer que
alguém tem 329 anos é erro de preenchimento, não fato; mas apagar a *resposta inteira* perderia 7 respostas
úteis sobre o resto. Esta é a **única** coluna em que o pipeline deixa um valor nulo por regra; a regra e o
limite estão numa constante (`IDADE_MINIMA`, `IDADE_MAXIMA`).

### 6. Gênero: texto livre agrupado em quatro categorias
`Gender` tem 49 grafias (`Male`, `male`, `M`, `Make`, `maile`, `Cis Male`, `queer/she/they`, `Nah`...). Agrupa-se
por `lower(trim(texto))` em **Homem / Mulher / Outras identidades / Não informado**, pelo mapa `GENERO` (41
chaves). Critério: só entra em Homem ou Mulher a resposta **inequívoca**, com erro de digitação óbvio incluído;
fora do binário ou ambígua vai para Outras identidades; texto que não responde (`Nah`, `All`, `p`) vai para Não
informado. Grafia que não está no mapa **para tudo**. Motivo: o agrupamento é uma decisão sobre pessoas e fica
escrita, completa e discutível, em um lugar só. *Limite:* "Outras identidades" tem 14 respostas, pouco para
qualquer percentual; o painel mostra o `n` ao lado.

### 7. Nulos
Nenhuma linha é apagada por ter nulo e nenhum nulo é preenchido (fora a decisão 5).
- `interferencia_trabalho` nula (264) **fica nula**; 260 dessas respostas são de quem não buscou tratamento,
  o que sugere "não se aplica", mas isso é hipótese e não está no dado. Os marts a chamam `sem_resposta`.
- `estado` nulo (515) é esperado (fora dos EUA). Quatro respostas têm estado dos EUA com país estrangeiro:
  **ficam como vieram**, nenhum indicador usa `estado`.

### 8. `comments` não passa para `refined`
Texto livre de 164 pessoas, que nenhum indicador usa e que pode conter detalhe pessoal. Continua em `raw`
(que nunca é alterada). Motivo: o que não é necessário não é espalhado para as camadas seguintes.

### 9. País
O nome da pesquisa é ligado a `paises` pelo nome. Dois não casavam e recebem o nome oficial do pacote
(`ALIAS_PAISES`): `Bahamas, The` → `Bahamas`, `Czech Republic` → `Czechia`. Depois disso **todo país da
pesquisa precisa existir em `refined.paises`**; se um não existir a transformação para (um país sem cadastro
sumiria do indicador por continente sem aviso).

### 10. Duplicatas
Linhas de `respostas` iguais em todas as 27 colunas de `raw`: há 0. Se houvesse, **seriam mantidas e
contadas** (sem chave natural não dá para saber se é repetição ou duas pessoas parecidas) e a mensagem diria
quantas. Em `paises`, nome repetido para tudo.

### 11. Reexecução e transação
`CREATE OR REPLACE`. Tudo numa transação: se algo falhar, `refined` continua como estava.

## Saída

Antes → depois por tabela, linhas idênticas, nulos mantidos, idades zeradas, e a contagem por gênero.

## Critérios de aceite

- `refined.respostas` 1.259 → 1.259 linhas; `refined.paises` 250 → 250.
- `idade` nula em exatamente 8 linhas; `idade_informada` ainda tem `99999999999`.
- Gênero: Homem 990 · Mulher 251 · Outras identidades 14 · Não informado 4.
- Nenhuma coluna `comments` em `refined`.
- Nulos que ficam: `interferencia_trabalho` 264, `estado` 515, `autonomo` 18, `idade` 8.
- Se `raw.respostas` ganhar a grafia de gênero `"xyz"`, a transformação para e cita `xyz`.
- Todo país de `refined.respostas` existe em `refined.paises`.
