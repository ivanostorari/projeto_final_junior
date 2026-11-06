"""Gera raw/paises.csv a partir da tabela de países do pacote country_converter (GPL-3.0).

Roda UMA vez, por quem mantém o projeto (precisa do grupo de dependências dev). O
resultado, raw/paises.csv, fica versionado: quem só quer rodar o pipeline não precisa
deste script nem do pacote.

    uv run python preparar_paises.py

Decisões, cada uma com o motivo:

1. FICAM só 5 colunas: name_short, name_official, ISO3, continent, UNregion.
   Motivo: são as que algum indicador usa (nome para ligar, continente e região para
   agrupar); as outras 48 colunas do pacote são classificações de modelos econômicos
   (EXIO, MESSAGE, REMIND...), de blocos (G20, OCDE, UE) e códigos que nada aqui usa.
   OCDE e UE ficaram de fora também porque, no pacote, país que não é membro vem em
   branco: preencher "não" seria decidir que branco quer dizer não.
2. A coluna ISO2 FICA DE FORA. Dois achados ao inspecionar o arquivo do pacote:
   (a) para o Reino Unido, ISO2 vale "^GB$|^UK$", uma expressão regular e não um código;
   (b) para a Namíbia, ISO2 vale "NA", igual ao marcador de nulo da pesquisa, e qualquer
       leitura com na_values=["NA"] a transformaria em nulo sem avisar.
   Motivo: uma coluna que não é usada e que tem duas armadilhas não entra. A ligação com a
   pesquisa é pelo nome do país (name_short).
3. Nulo é gravado como campo vazio, nunca como "NA".
"""

from pathlib import Path

import country_converter as coco
import pandas as pd

COLUNAS = ["name_short", "name_official", "ISO3", "continent", "UNregion"]
SAIDA = Path(__file__).resolve().parent / "raw" / "paises.csv"


def main() -> None:
    origem = Path(coco.__file__).resolve().parent / "country_data.tsv"
    # keep_default_na=False: sem isto o pandas leria o "NA" da Namíbia como nulo.
    df = pd.read_csv(origem, sep="\t", dtype=str, keep_default_na=False, na_values=[""])
    df = df[df["obsolete"].isna()][COLUNAS]  # fora os países que deixaram de existir (Zanzibar etc.)
    df.to_csv(SAIDA, index=False, lineterminator="\n")
    print(f"✓ {SAIDA.name}  {len(df)} países  (country_converter {coco.__version__}, licença GPL-3.0)")


if __name__ == "__main__":
    main()
