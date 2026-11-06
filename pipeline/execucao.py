"""Registro de uma execução do pipeline: identidade, etapas, arquivos, linhagem, qualidade e logs.

Spec: specs/operacao.md. Este módulo só REGISTRA; quem decide o que rodar e quando parar é o
orquestrador. Dois destinos: o schema `controle` do próprio banco (descreve a execução que gerou aquele
banco) e a pasta logs/ (histórico: pipeline.jsonl + execucao.json e qualidade.json por execução).
Nenhum registro carrega valor de linha da pesquisa: só nomes, contagens e tempos.
"""

import json
import secrets
import tomllib
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from pipeline import db, qualidade

LIMITE_MENSAGEM = 300
CONTAGENS = ("recebidas", "processadas", "rejeitadas", "publicadas")


def versao_pipeline() -> str:
    try:
        return tomllib.loads((db.RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "desconhecida"


def agora() -> datetime:
    return datetime.now(UTC)


def _iso(momento: datetime) -> str:
    return momento.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Execucao:
    def __init__(self, pasta_logs: Path | None = None):
        self.pasta_logs = Path(pasta_logs or db.PASTA_LOGS)
        self.iniciada = agora()
        self.id = f"{self.iniciada:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
        self.versao = versao_pipeline()
        self.status = "em_andamento"
        self.finalizada = None
        self.duracao_s = None
        self.banco_publicado = False
        self.etapas: list[dict] = []
        self.arquivos: list[dict] = []
        self.linhagem: list[dict] = []
        self.verificacoes: list[qualidade.Verificacao] = []
        self._inicio = perf_counter()
        self.aviso_log: str | None = None
        self.log("execucao_inicio", versao_pipeline=self.versao)

    # ---- logs estruturados (uma linha JSON por evento) ----
    def log(self, evento: str, nivel: str = "info", **campos) -> None:
        linha = {"ts": _iso(agora()), "execucao_id": self.id, "evento": evento, "nivel": nivel, **campos}
        try:
            self.pasta_logs.mkdir(parents=True, exist_ok=True)
            with (self.pasta_logs / "pipeline.jsonl").open("a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
        except OSError as erro:
            self.aviso_log = f"não foi possível gravar o log em {self.pasta_logs}: {type(erro).__name__}"

    # ---- etapas ----
    @contextmanager
    def etapa(self, nome: str):
        registro = {"ordem": len(self.etapas) + 1, "etapa": nome, "status": "em_andamento",
                    "iniciada_em": _iso(agora()), "duracao_s": None, **dict.fromkeys(CONTAGENS)}
        self.etapas.append(registro)
        self.log("etapa_inicio", etapa=nome)
        inicio = perf_counter()
        try:
            yield registro
        except BaseException as erro:
            registro["status"] = "falhou"
            registro["erro_tipo"] = type(erro).__name__
            registro["erro_mensagem"] = str(erro)[:LIMITE_MENSAGEM]
            raise
        else:
            registro["status"] = "ok"
        finally:
            registro["duracao_s"] = round(perf_counter() - inicio, 3)
            self.log("etapa_fim", "info" if registro["status"] == "ok" else "erro",
                     **{k: v for k, v in registro.items() if k not in ("ordem", "iniciada_em")})

    def pular(self, nome: str) -> None:
        self.etapas.append({"ordem": len(self.etapas) + 1, "etapa": nome, "status": "nao_executada",
                            "iniciada_em": None, "duracao_s": None, **dict.fromkeys(CONTAGENS)})
        self.log("etapa_fim", "aviso", etapa=nome, status="nao_executada")

    # ---- fatos coletados ----
    def registrar_verificacoes(self, verificacoes) -> None:
        self.verificacoes += list(verificacoes)
        for v in qualidade.falhas(verificacoes):
            self.log("verificacao_falhou", "erro" if v.severidade == qualidade.ERRO else "aviso",
                     camada=v.camada, dimensao=v.dimensao, regra=v.regra, severidade=v.severidade,
                     observado=v.observado, esperado=v.esperado)

    def finalizar(self, status: str, banco_publicado: bool) -> None:
        self.status, self.banco_publicado = status, banco_publicado
        self.finalizada = agora()
        self.duracao_s = round(perf_counter() - self._inicio, 3)

    # ---- saídas ----
    def resumo(self) -> dict:
        return {
            "execucao_id": self.id,
            "versao_pipeline": self.versao,
            "status": self.status,
            "banco_publicado": self.banco_publicado,
            "iniciada_em": _iso(self.iniciada),
            "finalizada_em": _iso(self.finalizada) if self.finalizada else None,
            "duracao_s": self.duracao_s,
            "arquivos_origem": self.arquivos,
            "etapas": self.etapas,
            "linhagem": self.linhagem,
            "qualidade": qualidade.resumo(self.verificacoes),
        }

    def gravar_arquivos(self) -> Path | None:
        """Grava execucao.json e qualidade.json da execução e o evento final do log."""
        self.log("execucao_fim", "info" if self.status == "ok" else "erro", status=self.status,
                 duracao_s=self.duracao_s, banco_publicado=self.banco_publicado)
        pasta = self.pasta_logs / "execucoes" / self.id
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / "execucao.json").write_text(
                json.dumps(self.resumo(), ensure_ascii=False, indent=2), encoding="utf-8")
            (pasta / "qualidade.json").write_text(
                json.dumps(qualidade.relatorio(self.verificacoes), ensure_ascii=False, indent=2),
                encoding="utf-8")
        except OSError as erro:
            self.aviso_log = f"não foi possível gravar o relatório em {pasta}: {type(erro).__name__}"
            return None
        return pasta

    def gravar_controle(self, con) -> None:
        """Cria o schema `controle` no banco com o que se sabe desta execução."""
        con.execute("CREATE SCHEMA IF NOT EXISTS controle")
        con.execute("CREATE OR REPLACE TABLE controle.execucoes (execucao_id VARCHAR, versao_pipeline VARCHAR, "
                    "status VARCHAR, iniciada_em VARCHAR, finalizada_em VARCHAR, duracao_s DOUBLE)")
        con.execute("INSERT INTO controle.execucoes VALUES (?, ?, ?, ?, ?, ?)",
                    [self.id, self.versao, self.status, _iso(self.iniciada),
                     _iso(self.finalizada) if self.finalizada else None, self.duracao_s])
        con.execute("CREATE OR REPLACE TABLE controle.etapas (execucao_id VARCHAR, ordem INTEGER, etapa VARCHAR, "
                    "status VARCHAR, duracao_s DOUBLE, recebidas BIGINT, processadas BIGINT, "
                    "rejeitadas BIGINT, publicadas BIGINT)")
        con.executemany("INSERT INTO controle.etapas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [[self.id, e["ordem"], e["etapa"], e["status"], e["duracao_s"],
                          *(e[c] for c in CONTAGENS)] for e in self.etapas])
        con.execute("CREATE OR REPLACE TABLE controle.arquivos_origem (execucao_id VARCHAR, arquivo VARCHAR, "
                    "sha256 VARCHAR, bytes BIGINT, linhas BIGINT)")
        con.executemany("INSERT INTO controle.arquivos_origem VALUES (?, ?, ?, ?, ?)",
                        [[self.id, a["arquivo"], a["sha256"], a["bytes"], a["linhas"]] for a in self.arquivos])
        con.execute("CREATE OR REPLACE TABLE controle.linhagem (execucao_id VARCHAR, destino VARCHAR, "
                    "origem VARCHAR)")
        con.executemany("INSERT INTO controle.linhagem VALUES (?, ?, ?)",
                        [[self.id, x["destino"], x["origem"]] for x in self.linhagem])
        con.execute("CREATE OR REPLACE TABLE controle.qualidade (execucao_id VARCHAR, camada VARCHAR, "
                    "dimensao VARCHAR, regra VARCHAR, severidade VARCHAR, aprovada BOOLEAN, "
                    "observado VARCHAR, esperado VARCHAR)")
        con.executemany("INSERT INTO controle.qualidade VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [[self.id, v.camada, v.dimensao, v.regra, v.severidade, v.ok, v.observado, v.esperado]
                         for v in self.verificacoes])
