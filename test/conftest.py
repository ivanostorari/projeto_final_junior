"""Ajudantes dos testes: dado INVENTADO, em banco temporário.

Regra do projeto (specs/testes.md): nenhum teste abre saude_mental.duckdb nem lê raw/.
Tudo acontece em tmp_path, com poucas linhas escolhidas a dedo; cada linha tem
um comentário dizendo por que ela existe. O valor esperado sai da conta feita
sobre essa entrada, nunca de um número medido no dado real.
"""

import csv

import duckdb
import pytest

from pipeline import transformacao

COLUNAS_SURVEY = [
    "Timestamp", "Age", "Gender", "Country", "state", "self_employed", "family_history", "treatment",
    "work_interfere", "no_employees", "remote_work", "tech_company", "benefits", "care_options",
    "wellness_program", "seek_help", "anonymity", "leave", "mental_health_consequence",
    "phys_health_consequence", "coworkers", "supervisor", "mental_health_interview",
    "phys_health_interview", "mental_vs_physical", "obs_consequence", "comments",
]
COLUNAS_PAISES = ["name_short", "name_official", "ISO3", "continent", "UNregion"]
COLUNAS = {"respostas": COLUNAS_SURVEY, "paises": COLUNAS_PAISES}


def criar_raw(con, tabela: str, linhas: list[dict]) -> None:
    """Cria raw.<tabela> (tudo VARCHAR, como a ingestão) com as linhas dadas."""
    colunas = COLUNAS[tabela]
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    definicao = ", ".join(f'"{c}" VARCHAR' for c in colunas)
    con.execute(f"CREATE OR REPLACE TABLE raw.{tabela} ({definicao})")
    if linhas:
        marcas = ", ".join("?" for _ in colunas)
        con.executemany(f"INSERT INTO raw.{tabela} VALUES ({marcas})", [[l.get(c) for c in colunas] for l in linhas])


def resposta(**mudancas) -> dict:
    """Uma resposta-base (homem, EUA, 30 anos, tudo 'não'). Muda só o que importa em cada teste."""
    base = {
        "Timestamp": "2014-08-27 11:29:31", "Age": "30", "Gender": "Male", "Country": "United States",
        "state": "IL", "self_employed": "No", "family_history": "No", "treatment": "No",
        "work_interfere": None, "no_employees": "6-25", "remote_work": "No", "tech_company": "Yes",
        "benefits": "No", "care_options": "No", "wellness_program": "No", "seek_help": "No",
        "anonymity": "Don't know", "leave": "Don't know", "mental_health_consequence": "No",
        "phys_health_consequence": "No", "coworkers": "No", "supervisor": "No",
        "mental_health_interview": "No", "phys_health_interview": "No", "mental_vs_physical": "Don't know",
        "obs_consequence": "No", "comments": None,
    }
    base.update(mudancas)
    return base


def pais(nome: str, continente: str, regiao: str, iso3: str = "XXX") -> dict:
    return {"name_short": nome, "name_official": f"Republic of {nome}", "ISO3": iso3,
            "continent": continente, "UNregion": regiao}


PAISES = [
    pais("United States", "America", "Northern America", "USA"),
    pais("Canada", "America", "Northern America", "CAN"),
    pais("Bahamas", "America", "Caribbean", "BHS"),  # a pesquisa escreve 'Bahamas, The' (alias)
    pais("United Kingdom", "Europe", "Northern Europe", "GBR"),
    pais("Czechia", "Europe", "Eastern Europe", "CZE"),  # a pesquisa escreve 'Czech Republic' (alias)
    pais("Germany", "Europe", "Western Europe", "DEU"),
]

# Oito respostas escolhidas a dedo (só o que difere da resposta-base está escrito).
# A conta de cada indicador está nos testes de test_sql_marts.py.
RESPOSTAS = [
    # r1: Homem ('male' minúsculo), EUA, 25 anos, buscou tratamento, histórico familiar, interfere 'Often',
    # empresa de 1-5, benefícios Sim, receio Sim, falaria com o supervisor, falaria na entrevista (mental)
    resposta(Age="25", Gender="male", treatment="Yes", family_history="Yes", work_interfere="Often",
             no_employees="1-5", benefits="Yes", care_options="Yes", anonymity="Yes", leave="Very easy",
             mental_health_consequence="Yes", supervisor="Yes", mental_health_interview="Yes"),
    # r2: Mulher ('FEMALE ' com maiúsculas e espaço no fim), Reino Unido, 34 anos, tratamento, 'Sometimes'
    resposta(Age="34", Gender="FEMALE ", Country="United Kingdom", treatment="Yes", work_interfere="Sometimes",
             leave="Somewhat difficult", mental_health_consequence="Maybe", supervisor="Some of them",
             phys_health_interview="Maybe"),
    # r3: Homem ('Cis Man'), Canadá, 45 anos, empresa de 26-100, benefícios "Don't know", opções 'Not sure'
    resposta(Age="45", Gender="Cis Man", Country="Canada", no_employees="26-100", benefits="Don't know",
             care_options="Not sure", phys_health_interview="Yes"),
    # r4: gênero que não responde ('Nah'), 'Czech Republic' (alias -> Czechia), idade impossível (99999999999)
    resposta(Age="99999999999", Gender="Nah", Country="Czech Republic", family_history="Yes",
             work_interfere="Never", no_employees="100-500", benefits="Yes", care_options="Yes",
             seek_help="Yes", anonymity="No", leave="Somewhat easy", phys_health_consequence="Maybe",
             supervisor="Yes"),
    # r5: 'non-binary' (Outras identidades), Alemanha, 24 anos, tratamento, histórico, 'Rarely', 500-1000
    resposta(Age="24", Gender="non-binary", Country="Germany", treatment="Yes", family_history="Yes",
             work_interfere="Rarely", no_employees="500-1000", wellness_program="Yes",
             mental_health_consequence="Yes"),
    # r6: Mulher ('Female (trans)'), EUA, 35 anos, 'Sometimes', empresa de Mais de 1000, benefícios Sim
    resposta(Age="35", Gender="Female (trans)", work_interfere="Sometimes", no_employees="More than 1000",
             benefits="Yes", wellness_program="Yes", leave="Very easy"),
    # r7: Homem ('M'), EUA, idade negativa (-5), tratamento, empresa de 6-25 (a base)
    resposta(Age="-5", Gender="M", treatment="Yes"),
    # r8: Mulher ('woman'), 'Bahamas, The' (alias -> Bahamas), 17 anos, empresa de 1-5, benefícios Sim
    resposta(Age="17", Gender="woman", Country="Bahamas, The", no_employees="1-5", benefits="Yes",
             wellness_program="Yes", mental_health_consequence="Yes", supervisor="Yes"),
]


def popular_raw(con, respostas=None, paises=None) -> None:
    criar_raw(con, "respostas", RESPOSTAS if respostas is None else respostas)
    criar_raw(con, "paises", PAISES if paises is None else paises)


def escrever_csv(caminho, colunas: list[str], linhas: list[dict]) -> None:
    """Escreve um CSV de entrada (valor None vira campo vazio, que a ingestão lê como nulo)."""
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)


def respostas_do_pipeline() -> list[dict]:
    """As 8 respostas do conftest + 20 geradas (EUA, cada uma com seu horário), para o mart 08 (mínimo de 20 por país) não vir vazio."""
    return RESPOSTAS + [resposta(Timestamp=f"2015-01-01 00:00:{i:02d}") for i in range(20)]


def escrever_entradas(pasta, respostas=None, paises=None) -> None:
    """survey.csv e paises.csv INVENTADOS em `pasta` (nunca os de raw/)."""
    pasta.mkdir(parents=True, exist_ok=True)
    escrever_csv(pasta / "survey.csv", COLUNAS_SURVEY, respostas_do_pipeline() if respostas is None else respostas)
    escrever_csv(pasta / "paises.csv", COLUNAS_PAISES, PAISES if paises is None else paises)


@pytest.fixture
def con(tmp_path):
    conexao = duckdb.connect(str(tmp_path / "teste.duckdb"))
    yield conexao
    conexao.close()


@pytest.fixture
def refined(con):
    """Banco temporário com raw inventado já transformado em refined."""
    popular_raw(con)
    transformacao.transformar(con)
    return con
