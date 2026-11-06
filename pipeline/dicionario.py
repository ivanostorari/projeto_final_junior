"""Dicionário de valores da pesquisa: o que cada resposta em inglês vira em português.

Cada mapa é ao mesmo tempo TRADUÇÃO e LISTA DE VALORES PERMITIDOS: um valor que não
está no mapa para a transformação (spec: specs/transformacao.md, decisão 4). Assim uma
resposta nova, ou um erro de digitação, nunca vira nulo nem passa em silêncio.

Este arquivo só tem dados. Nenhuma regra de cálculo mora aqui.
"""

SIM_NAO = {"Yes": "Sim", "No": "Não"}
BOOLEANO = {"Yes": True, "No": False}  # colunas só Sim/Não viram BOOLEAN (nulo continua nulo)

SIM_NAO_NAO_SEI = {"Yes": "Sim", "No": "Não", "Don't know": "Não sei"}
SIM_NAO_TALVEZ = {"Yes": "Sim", "No": "Não", "Maybe": "Talvez"}
SIM_NAO_ALGUNS = {"Yes": "Sim", "No": "Não", "Some of them": "Alguns"}

# coluna original -> mapa. Colunas Sim/Não puras ficam em COLUNAS_BOOLEANAS.
MAPAS = {
    "work_interfere": {"Never": "Nunca", "Rarely": "Raramente", "Sometimes": "Às vezes", "Often": "Frequentemente"},
    "no_employees": {
        "1-5": "1-5", "6-25": "6-25", "26-100": "26-100", "100-500": "100-500",
        "500-1000": "500-1000", "More than 1000": "Mais de 1000",
    },
    "benefits": SIM_NAO_NAO_SEI,
    "care_options": {"Yes": "Sim", "No": "Não", "Not sure": "Não tenho certeza"},
    "wellness_program": SIM_NAO_NAO_SEI,
    "seek_help": SIM_NAO_NAO_SEI,
    "anonymity": SIM_NAO_NAO_SEI,
    "leave": {
        "Very easy": "Muito fácil", "Somewhat easy": "Um pouco fácil",
        "Somewhat difficult": "Um pouco difícil", "Very difficult": "Muito difícil", "Don't know": "Não sei",
    },
    "mental_health_consequence": SIM_NAO_TALVEZ,
    "phys_health_consequence": SIM_NAO_TALVEZ,
    "coworkers": SIM_NAO_ALGUNS,
    "supervisor": SIM_NAO_ALGUNS,
    "mental_health_interview": SIM_NAO_TALVEZ,
    "phys_health_interview": SIM_NAO_TALVEZ,
    "mental_vs_physical": SIM_NAO_NAO_SEI,
}

COLUNAS_BOOLEANAS = [
    "self_employed", "family_history", "treatment", "remote_work", "tech_company", "obs_consequence",
]

# País escrito de um jeito na pesquisa e de outro em paises (nome_curto). Só estes dois não casavam.
ALIAS_PAISES = {"Bahamas, The": "Bahamas", "Czech Republic": "Czechia"}

HOMEM, MULHER, OUTRAS, NAO_INFORMADO = "Homem", "Mulher", "Outras identidades", "Não informado"

# Gênero: texto livre na pesquisa (49 grafias). Chave = lower(trim(texto)).
# Critério: só entra em Homem ou Mulher a resposta INEQUÍVOCA, incluindo erro de digitação óbvio
# ("make", "maile", "femake"). Quem se descreveu fora do binário, ou de forma ambígua
# ("male-ish", "something kinda male?"), fica em Outras identidades. Texto que não responde
# a pergunta ("nah", "all", "p") fica em Não informado. Mulheres trans entram em Mulher porque
# responderam "female"/"woman"; a grafia original continua em raw.respostas.
GENERO = {
    # Homem
    "male": HOMEM, "m": HOMEM, "man": HOMEM, "make": HOMEM, "mal": HOMEM, "maile": HOMEM, "msle": HOMEM,
    "mail": HOMEM, "malr": HOMEM, "cis male": HOMEM, "cis man": HOMEM, "male (cis)": HOMEM,
    # Mulher
    "female": MULHER, "f": MULHER, "woman": MULHER, "femail": MULHER, "femake": MULHER,
    "cis female": MULHER, "female (cis)": MULHER, "cis-female/femme": MULHER,
    "female (trans)": MULHER, "trans woman": MULHER, "trans-female": MULHER,
    # Outras identidades (fora do binário ou ambíguas)
    "non-binary": OUTRAS, "enby": OUTRAS, "genderqueer": OUTRAS, "androgyne": OUTRAS, "agender": OUTRAS,
    "fluid": OUTRAS, "neuter": OUTRAS, "queer": OUTRAS, "queer/she/they": OUTRAS, "male-ish": OUTRAS,
    "guy (-ish) ^_^": OUTRAS, "something kinda male?": OUTRAS,
    "ostensibly male, unsure what that really means": OUTRAS, "male leaning androgynous": OUTRAS,
    # Não informado (não é resposta à pergunta)
    "nah": NAO_INFORMADO, "all": NAO_INFORMADO, "a little about you": NAO_INFORMADO, "p": NAO_INFORMADO,
}

IDADE_MINIMA, IDADE_MAXIMA = 16, 80
