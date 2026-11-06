# Spec · Etapa 1 · Ingestão (`pipeline/db.py`, `pipeline/ingestao.py`)

Lê os CSV de `raw/` e grava o schema `raw` do `saude_mental.duckdb`. Não converte,
não corrige, não descarta. Executar: `uv run python -m pipeline.ingestao`.

## De onde vem o dado

| Arquivo (`raw/`) | Tabela     | Fonte                                                                                   | Licença            |
|------------------|------------|-----------------------------------------------------------------------------------------|--------------------|
| `survey.csv`     | `respostas`| Pesquisa **Mental Health in Tech Survey 2014**, da OSMI (Open Sourcing Mental Illness), 1.259 respostas de pessoas que trabalham com tecnologia | CC BY-SA 3.0 Unported para a pesquisa de 2014 (conferido em osmihelp.org/research.html) |
| `paises.csv`     | `paises`   | Tabela de países do pacote Python `country_converter` 1.3.2, gerada por `preparar_paises.py` | GPL-3.0 (do pacote) |

`survey.csv` está **byte a byte como foi baixado** (SHA-256 `3c4e3e16…db4`, 1.259 linhas + cabeçalho,
27 colunas). A cópia usada veio de um espelho no GitHub (`alvin-98/mental-health-survey-2014`), que
não declara licença nem origem; a fonte original é a OSMI. A cópia foi conferida em 06/11/2026 contra o depósito
oficial da OSMI no Figshare (mesmo tamanho e mesmo MD5); detalhes em `raw/ORIGEM.md` e no README.

## O que a pesquisa é (e não é)

- **Uma linha de `respostas` = uma pessoa que respondeu ao questionário** (anônimo, sem identificador;
  de 27/08/2014 a 01/02/2016).
- É uma **amostra de quem quis responder**, divulgada por canais de tecnologia. **Não mede quantas pessoas de
  tecnologia têm um transtorno**: mede o que *estas* pessoas contaram. Todo percentual do projeto é "% das
  pessoas que responderam", nunca "% dos profissionais de tecnologia".
- Não há coluna de profissão: **não dá para separar cientistas de dados** das demais pessoas de tecnologia.
  O projeto fala de "pessoas de tecnologia", e o README diz isso logo no início.
- `paises` é a tabela de apoio: uma linha por país, com continente e região da ONU. Liga com `respostas`
  pelo **nome do país**.

## Decisões

1. **Escopo e nomes.** Dois arquivos, duas tabelas, mapa literal `ARQUIVOS`. Nomes de tabela em português;
   nomes de coluna ficam os originais (inglês) até a etapa 2.
2. **Nada de conversão aqui.** Tudo entra como texto. Motivo: `Age` tem `99999999999` e `-1726`; se a
   leitura inferisse número, isso passaria sem ninguém ver. A decisão sobre esses valores é da etapa 2.
3. **Marcador de nulo é por arquivo.** `survey.csv` usa `NA` (herança do R), e `NA` mais campo vazio viram
   nulo (são 264 em `work_interfere`, 515 em `state`, 18 em `self_employed`). `paises.csv` só tem campo vazio como
   nulo. Motivo: a regra de um arquivo não pode vazar para o outro. (Foi por isso que `ISO2` ficou fora de
   `paises.csv`: a Namíbia tem ISO2 igual a `NA`, e o Reino Unido tem `^GB$|^UK$`, uma expressão regular.)
4. **Reexecução.** `CREATE OR REPLACE`. Rodar duas vezes dá o mesmo banco.
5. **Saída.** Uma linha por tabela com a contagem **lida do banco**, milhar com ponto, e o total.
6. **Erro.** Faltou arquivo: lista quais, diz a pasta, sai com código 1 **antes de gravar qualquer coisa**.
7. **Sem identificador próprio.** Não se inventa `id` em `raw`. A ordem das linhas fica guardada pelo banco
   (`rowid`) e a etapa 2 a usa.

## Números de conferência

| Tabela        | Linhas |
|---------------|--------|
| `respostas`   | 1.259  |
| `paises`      | 250    |
| **Total**     | 1.509  |

## Critérios de aceite

- `uv run python executar.py` imprime `raw.respostas 1.259` e `raw.paises 250`.
- `raw.respostas` tem 27 colunas, todas `VARCHAR`; `Age` contém o texto `99999999999`.
- `raw.paises` contém a Namíbia (sem ISO2) e o Reino Unido com `GBR`.
- Remover `raw/paises.csv` e rodar: lista o arquivo faltando, sai com código 1, não cria tabela nenhuma.
- Rodar duas vezes: mesmas contagens.
