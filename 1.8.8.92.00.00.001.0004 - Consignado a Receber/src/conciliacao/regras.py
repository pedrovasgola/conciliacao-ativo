"""Classes do MOVIMENTO e da SE5. As dez não se agrupam."""

from __future__ import annotations

import re
import unicodedata

CODIGOS = ("004", "099", "100", "101", "102", "103", "108", "110", "400", "401", "405")
CODIGOS_NEGATIVOS = {"004", "400", "401"}

BAIXA_EMPREGADOR = "Baixa Empregador"
ESTORNO_EMPREGADOR = "Estorno Baixa Empregador"
BAIXA_ITAU = "Baixa Boleto Itaú"
ESTORNO_ITAU = "Estorno Baixa Boleto Itaú"
LIB = "Lib. Créd p/ Quit. Refin"
REFIN = "Refinanciamento"
ESTORNO_OP = "Estorno Itaú/baixa boleto itau"

CLASSES = (
    BAIXA_EMPREGADOR,
    REFIN,
    "Baixa Prejuízo",
    BAIXA_ITAU,
    LIB,
    "BAIXA BANCO SPB",
    ESTORNO_ITAU,
    ESTORNO_EMPREGADOR,
    "BX EMPREGADOR PRC ANTEC",
    "Baixa Boleto Santander",
    ESTORNO_OP,
)

PARES = (
    (BAIXA_ITAU, ESTORNO_ITAU, ESTORNO_OP),
    (BAIXA_EMPREGADOR, ESTORNO_EMPREGADOR),
    (LIB, REFIN),
)


def norm(texto) -> str:
    if texto is None:
        return ""
    return " ".join(str(texto).replace("\xa0", " ").split())


def _chave(texto: str) -> str:
    base = unicodedata.normalize("NFKD", norm(texto))
    sem_acento = "".join(c for c in base if not unicodedata.combining(c))
    return sem_acento.casefold()


def codigo(valor) -> str:
    texto = norm(valor)
    if texto.endswith(".0") and texto[:-2].isdigit():
        texto = texto[:-2]
    if texto.isdigit():
        return texto.zfill(3)
    return texto


def sinal(cod: str, valor: float) -> float:
    absoluto = round(abs(float(valor)), 2)
    if codigo(cod) in CODIGOS_NEGATIVOS:
        return round(-absoluto, 2)
    return absoluto


def classe_movimento(nome: str) -> str:
    chave = _chave(nome)
    for classe in CLASSES:
        if _chave(classe) == chave:
            return classe
    return norm(nome)


def empregador(texto: str) -> str:
    nome = norm(texto)
    nome = re.sub(r"^\d+\s+", "", nome)
    return nome


def classe_se5(numero: str, tipo: str, benef: str, titulos: dict[str, set[str]]) -> tuple[str, str]:
    """Devolve (classe, origem). Título com um MOVIMENTO manda. Sem título, usa o tipo."""
    numero = norm(numero)
    movimentos = {classe_movimento(item) for item in titulos.get(numero, set()) if norm(item)}
    if len(movimentos) == 1:
        return next(iter(movimentos)), "titulo"
    tipo_n = norm(tipo).upper()
    benef_n = _chave(benef)
    if "banco senff" in benef_n or tipo_n == "OP":
        return ESTORNO_OP, "tipo"
    if tipo_n == "REP":
        return BAIXA_EMPREGADOR, "tipo"
    return ESTORNO_OP, "tipo"


def orgao_historico(hist: str) -> str:
    nome = norm(hist)
    nome = re.sub(r"\s+\d{2}[-/]\d{4}.*$", "", nome)
    nome = re.sub(r"\s*-\s*\d{2}/\d{4}.*$", "", nome)
    nome = re.sub(r"\s+complemento.*$", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\s+v\d+$", "", nome, flags=re.IGNORECASE)
    return norm(nome)


def centavos(valor) -> float:
    if valor is None or valor == "":
        return 0.0
    return round(float(valor) + 0.0, 2)


def zerou(valor: float) -> bool:
    return abs(centavos(valor)) < 0.005
