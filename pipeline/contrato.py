"""Contrato dos CSVs de entrada: confere o arquivo ANTES de gravar qualquer coisa. Spec: specs/operacao.md.

Só usa a biblioteca padrão (csv, hashlib): a conferência não depende do que a ingestão faz depois.
Devolve verificações e a contagem de linhas de dados de cada arquivo (usada na conciliação com raw).
"""

import csv
import hashlib
from collections import Counter
from pathlib import Path

from pipeline.qualidade import AVISO, ERRO, Verificacao

SURVEY = [
    "Timestamp", "Age", "Gender", "Country", "state", "self_employed", "family_history", "treatment",
    "work_interfere", "no_employees", "remote_work", "tech_company", "benefits", "care_options",
    "wellness_program", "seek_help", "anonymity", "leave", "mental_health_consequence",
    "phys_health_consequence", "coworkers", "supervisor", "mental_health_interview",
    "phys_health_interview", "mental_vs_physical", "obs_consequence", "comments",
]
PAISES = ["name_short", "name_official", "ISO3", "continent", "UNregion"]

# arquivo -> (colunas obrigatórias, coluna-chave que não pode repetir ou None)
CONTRATOS = {"survey.csv": (SURVEY, None), "paises.csv": (PAISES, "name_short")}


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _v(arquivo, dimensao, regra, severidade, observado, esperado, ok=None, detalhe="") -> Verificacao:
    aprovou = (observado == esperado) if ok is None else ok
    return Verificacao("origem", dimensao, f"{arquivo}: {regra}", severidade, bool(aprovou),
                       str(observado), str(esperado), detalhe)


def _ler(caminho: Path) -> list[list[str]]:
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return [linha for linha in csv.reader(arquivo) if linha]  # linha em branco é ignorada (como na ingestão)


def verificar_arquivo(pasta: Path, arquivo: str) -> tuple[list[Verificacao], int | None]:
    colunas, chave = CONTRATOS[arquivo]
    caminho = pasta / arquivo
    if not caminho.is_file():
        return [_v(arquivo, "esquema", "arquivo existe", ERRO, "ausente", "presente")], None
    try:
        linhas = _ler(caminho)
    except UnicodeDecodeError:
        return [_v(arquivo, "esquema", "codificação UTF-8 legível", ERRO, "inválida", "UTF-8")], None
    if len(linhas) < 2:
        return [_v(arquivo, "completude", "cabeçalho e pelo menos 1 linha de dados", ERRO,
                   f"{len(linhas)} linha(s)", ">= 2")], max(len(linhas) - 1, 0)

    cabecalho, dados = linhas[0], linhas[1:]
    faltando = [c for c in colunas if c not in cabecalho]
    sobrando = [c for c in cabecalho if c not in colunas]
    repetidas = [c for c, n in Counter(cabecalho).items() if n > 1]
    tamanho_errado = sum(1 for linha in dados if len(linha) != len(cabecalho))
    iguais = len(dados) - len(set(map(tuple, dados)))
    resultado = [
        _v(arquivo, "esquema", "tem todas as colunas obrigatórias", ERRO, len(faltando), 0,
           detalhe="faltam: " + ", ".join(faltando) if faltando else ""),
        _v(arquivo, "esquema", "não tem colunas além das esperadas", AVISO, len(sobrando), 0,
           detalhe="sobram: " + ", ".join(sobrando) if sobrando else ""),
        _v(arquivo, "esquema", "nomes de coluna não se repetem", ERRO, len(repetidas), 0,
           detalhe="repetidas: " + ", ".join(repetidas) if repetidas else ""),
        _v(arquivo, "esquema", "toda linha tem o mesmo número de campos do cabeçalho", ERRO, tamanho_errado, 0),
        _v(arquivo, "unicidade", "sem linhas 100% repetidas", AVISO, iguais, 0),
    ]
    if chave and chave in cabecalho:
        posicao = cabecalho.index(chave)
        valores = [linha[posicao] for linha in dados if len(linha) > posicao]
        resultado.append(_v(arquivo, "unicidade", f"{chave} não se repete", ERRO,
                            len(valores) - len(set(valores)), 0))
    return resultado, len(dados)


def verificar(pasta: Path) -> tuple[list[Verificacao], dict[str, int | None]]:
    """Confere todos os CSVs. Devolve (verificações, {arquivo: linhas de dados ou None})."""
    verificacoes, contagem = [], {}
    for arquivo in CONTRATOS:
        achados, linhas = verificar_arquivo(pasta, arquivo)
        verificacoes += achados
        contagem[arquivo] = linhas
    return verificacoes, contagem
