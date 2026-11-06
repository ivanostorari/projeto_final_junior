# Spec · Operação: orquestrador, rastreabilidade, logs e qualidade

Escrita ANTES do código (como as outras specs). Cobre `executar.py`, `pipeline/orquestrador.py`,
`pipeline/execucao.py`, `pipeline/contrato.py` e `pipeline/qualidade.py`.

## Problema

As três etapas (ingestão, transformação, marts) funcionavam, mas:

- ninguém sabia dizer **qual execução** gerou o banco, com **quais arquivos** (hash), em quanto tempo
  e quantas linhas entraram e saíram de cada camada;
- não havia relação registrada entre cada mart e as tabelas de que ele depende;
- a saída era só texto no terminal, sem log estruturado;
- as regras de qualidade estavam espalhadas dentro das etapas (e a SQL dos marts não era conferida
  depois de rodar);
- `executar.py` apagava o banco antes de começar: uma falha no meio deixava o projeto **sem banco**.

## Decisões

1. **Um orquestrador** (`orquestrador.rodar`) roda: pré-condições → ingestão → conciliação do raw →
   transformação → qualidade da Silver → marts → qualidade da Gold. `executar.py` só chama e traduz o
   resultado em código de saída (0 ok, 1 falha).
2. **Dependência e parada.** Cada etapa depende da anterior. Se uma falha, as seguintes ficam com status
   `nao_executada` (registradas, não omitidas). Uma falha de qualidade com severidade `erro` conta como
   falha da etapa.
3. **Reexecução segura.** O banco novo é construído em `<banco>.novo`. Só se **tudo** der certo ele
   substitui o banco anterior (`os.replace`). Se algo falhar, o banco anterior continua intacto e o
   arquivo temporário é apagado. Rodar duas vezes seguidas dá os mesmos dados (idempotência).
4. **Bloqueio da Gold.** Se a qualidade da Silver (ou a conciliação raw → refined) tiver falha `erro`,
   os marts **nem são criados**. Se a qualidade da Gold falhar, o schema `marts` é apagado do banco
   novo, e como o banco novo também não substitui o anterior, nada ruim é publicado.
5. **Contrato dos CSVs** (antes de gravar qualquer coisa): existe, é UTF-8, tem linhas de dados,
   tem exatamente as colunas esperadas (faltar = erro, sobrar = aviso), nomes de coluna não repetidos,
   toda linha com o mesmo número de campos do cabeçalho, linhas 100% repetidas (aviso) e chave de
   `paises.csv` (`name_short`) sem repetição (erro).

## Severidades

| Severidade | Efeito |
|---|---|
| `erro` | Falha a verificação ⇒ a execução para (a Gold não é publicada). |
| `aviso` | Falha a verificação ⇒ registrada e mostrada, a execução continua. |
| `informacao` | Só mede e registra (nunca falha). |

## Regras de qualidade (camada · dimensão · regra · severidade se falhar)

**Origem (contrato dos CSVs)** — ver decisão 5 (dimensões: esquema, completude, unicidade).

**Silver (`refined`)**

| Dimensão | Regra | Sev. |
|---|---|---|
| Esquema | colunas e tipos de `refined.respostas` e `refined.paises` iguais ao definido em `transformacao.TABELAS` | erro |
| Privacidade/domínio | a coluna de comentários livres não existe em `refined` | erro |
| Completude | `id_resposta`, `respondido_em` e `genero` sem nulos | erro |
| Completude | `pais` sem nulos | aviso |
| Completude | `idade` nula em no máximo 5% das linhas | aviso |
| Unicidade | `id_resposta` único; `paises.nome` único; `paises.iso3` único | erro |
| Validade | `idade` entre 16 e 80 quando existe | erro |
| Validade | `genero` ∈ {Homem, Mulher, Outras identidades, Não informado} | erro |
| Domínio | cada coluna categórica só tem valores do dicionário (`dicionario.MAPAS`) | erro |
| Consistência | `idade` nula ou igual a `idade_informada` | erro |
| Consistência | `respondido_em` não está no futuro | erro |
| Integridade | todo `respostas.pais` existe em `paises.nome` | aviso |
| Informação | nº de respostas, de idades anuladas e de países sem cadastro | info |

**Conciliação entre camadas**

| Regra | Sev. |
|---|---|
| linhas de cada CSV = linhas da tabela correspondente em `raw` | erro |
| `raw.respostas` = `refined.respostas` e `raw.paises` = `refined.paises` (nenhuma linha some) | erro |
| soma de `respondentes` de cada mart que particiona as respostas (01, 02, 03, 04, 06, 09) = `refined.respostas` | erro |

**Gold (`marts`)**

| Dimensão | Regra | Sev. |
|---|---|---|
| Completude | cada arquivo `.sql` tem sua tabela, e a tabela tem pelo menos 1 linha | erro |
| Validade | toda coluna `pct_*` fica entre 0 e 100; toda coluna `respondentes` é ≥ 0 | erro |

## Rastreabilidade

Cada execução tem `execucao_id` no formato `AAAAMMDDTHHMMSSZ-xxxxxxxx` (UTC + 8 hex aleatórios).

Registrado em **dois lugares**:

1. **Schema `controle` no próprio banco** (descreve a execução que gerou *aquele* banco):
   `execucoes`, `etapas`, `arquivos_origem`, `linhagem_marts`, `qualidade`.
2. **Arquivos em `logs/`** (histórico entre execuções; a pasta não vai para o Git):
   - `logs/pipeline.jsonl`: um evento JSON por linha, acumulando todas as execuções;
   - `logs/execucoes/<execucao_id>/execucao.json`: o resumo completo da execução;
   - `logs/execucoes/<execucao_id>/qualidade.json`: o relatório de qualidade da execução.

Conteúdo do resumo: versão do pipeline (lida do `pyproject.toml`), início, fim, duração, status;
por arquivo de origem: SHA-256, bytes e linhas; por etapa: status, duração e as contagens
**recebidas / processadas / rejeitadas / publicadas**; por mart: tabelas `refined` de que depende
(extraídas do próprio `.sql`) e nº de linhas; todas as verificações de qualidade.

Contagens por etapa:

| Etapa | recebidas | processadas | rejeitadas | publicadas |
|---|---|---|---|---|
| ingestão | linhas dos CSVs | linhas gravadas em `raw` | recebidas − processadas | linhas em `raw` |
| transformação | linhas de `raw` | linhas de `refined` | raw − refined | linhas de `refined` |
| marts | linhas de `refined.respostas` | nº de marts criados | 0 (mart sem linhas é erro e para tudo) | soma das linhas dos marts |
| conciliação e qualidade | linhas da camada conferida | iguais às recebidas quando aprovada | 0 | iguais às recebidas |

## Logs estruturados

Cada linha de `pipeline.jsonl` tem: `ts` (UTC, ISO 8601), `execucao_id`, `evento`, `nivel`
(`info`, `aviso`, `erro`) e campos próprios. Eventos: `execucao_inicio`, `etapa_inicio`, `etapa_fim`
(com `duracao_s`, contagens e `status`), `verificacao_falhou`, `execucao_fim`.
Em falha, `etapa_fim` leva `erro_tipo` e `erro_mensagem` (cortada em 300 caracteres) e o nome da etapa.

**Nunca entram no log:** respostas individuais, comentários livres, valores de linhas. Só nomes de
arquivo/tabela/regra, contagens e tempos. (Mensagens de erro do DuckDB podem citar um valor que não
converteu; por isso são cortadas e a coluna de comentários nem chega a `refined`.)

## Fora de escopo

Orquestrador externo (Airflow etc.), execução incremental, alertas por e-mail, histórico dentro do banco
(o banco é descartável; o histórico fica em `logs/`).

## Testes (inventados, em `tmp_path`, sem abrir o banco do projeto)

- contrato: arquivo ausente, vazio, só cabeçalho, coluna faltando/sobrando/repetida, linha com campos a
  mais, linhas repetidas, chave repetida, encoding inválido;
- qualidade: cada regra passa no dado bom e falha no dado ruim montado de propósito;
- integração: pipeline completo com CSVs inventados e os `.sql` reais (Bronze → Silver → Gold, contagens
  conferidas à mão), idempotência (duas execuções, mesmo conteúdo dos marts), simulação de falha no meio
  (banco anterior intacto e sem arquivo temporário sobrando), bloqueio da Gold por falha de qualidade,
  arquivos vazios/incompletos/inválidos/duplicados, rastreabilidade (`controle`, `execucao.json`,
  `pipeline.jsonl` sem dado pessoal);
- `executar.py`: código de saída 0/1.
