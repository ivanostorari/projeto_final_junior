# Origem dos dados desta pasta

Nada nesta pasta foi alterado pelo projeto: a camada `raw` é a cópia do que chegou.

## `survey.csv`

- **O que é:** Mental Health in Tech Survey 2014, 1.259 respostas (1.260 linhas com o cabeçalho), 27 colunas.
- **Autoria e crédito:** Open Sourcing Mental Illness (OSMI), <https://www.osmihelp.org/research.html>
  (link "Get raw data" da pesquisa de 2014).
- **Licença:** Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0), conforme a página de pesquisa
  da OSMI. Quem reutiliza o **dado** precisa dar o crédito acima e manter a mesma licença em obras derivadas do dado.
- **De onde esta cópia veio:** do espelho `alvin-98/mental-health-survey-2014` no GitHub (o site da OSMI não estava
  acessível no ambiente em que o projeto foi construído). O espelho não declara licença nem origem.
- **SHA-256 do arquivo:** `3c4e3e16917f74b5e219ba01caecd09f9dc464c4848becdd018c9442d627abb4`
  (confira com `sha256sum raw/survey.csv`).
- **Conferência contra o original (06/11/2026):** o arquivo é idêntico ao `mental-heath-in-tech-2014.csv` do depósito
  oficial da OSMI no Figshare (https://figshare.com/articles/dataset/OSMI_Mental_Health_in_Tech_Survey/5579458): tamanho 303.684 bytes e MD5 `6e7bf171a9f00f5ec306e897bceaecb1`
  (conferir com `md5sum raw/survey.csv`). O MD5 é o que a API do Figshare lista para o arquivo.
- **Observação sobre a licença:** o depósito no Figshare declara CC BY 4.0; a página de pesquisa da OSMI indica CC BY-SA 3.0
  para a pesquisa de 2014. O projeto segue a mais restritiva (CC BY-SA 3.0).
- **Data de obtenção:** o arquivo entrou no repositório em 06/11/2026 (commit `2ab0e92`) e foi conferido contra o original em 06/11/2026.
- **Condições de uso e redistribuição (CC BY-SA 3.0):** pode copiar, redistribuir e adaptar, inclusive para fins comerciais, desde que dê o crédito à OSMI,
  indique se houve mudanças e mantenha a mesma licença (CC BY-SA 3.0) em obras derivadas do dado. As camadas `refined` e `marts`, e as tabelas mostradas
  no relatório, são derivadas e seguem essa regra. Isto não é aconselhamento jurídico.
- **Aviso:** é dado sobre saúde mental, anonimizado pela OSMI. Não tente identificar pessoas.

## `paises.csv`

- **O que é:** 250 países com nome, nome oficial, código ISO3, continente e região da ONU.
- **Origem:** tabela de países do pacote Python `country_converter` 1.3.2, licença **GPL-3.0** (Konstantin Stadler), gerada por `preparar_paises.py`
  (o script também registra por que a coluna ISO2 ficou de fora).
- **SHA-256 do arquivo:** `8074a42f612527a0474b8f7ef9c72c9f8e034262e98e144618068906f5dca6f3` (250 países, 251 linhas com o cabeçalho).
- **Data de obtenção:** gerado a partir do pacote 1.3.2 e versionado em 06/11/2026 (commit `2ab0e92`).
- **Licença do arquivo:** o `country_converter` é GPL-3.0 (conferido no repositório do pacote e nos metadados da versão 1.3.2); o `paises.csv` é um extrato
  da tabela `country_data.tsv` dele e, por prudência, deve ser tratado como GPL-3.0, **à parte** do código do projeto (MIT). O pacote não é importado pelo
  pipeline, só pelo `preparar_paises.py`, que roda uma vez. Isto não é aconselhamento jurídico; se for preciso uma licença mais simples, a tabela pode ser
  trocada por uma fonte de domínio público.
