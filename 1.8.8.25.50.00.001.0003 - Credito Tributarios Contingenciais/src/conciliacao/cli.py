"""Linha de comando da conciliação do crédito tributário."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from conciliacao.caminhos import pasta_pipelines, pasta_saida, pasta_scripts, pasta_trabalho, raiz
from conciliacao.conexoes import criar_engine, ler
from conciliacao.erros import ErroConciliacao
from conciliacao.planilha import gravar


def _data(texto: str) -> date:
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except ValueError as exc:
        raise ErroConciliacao(f"Data inválida '{texto}'. Use DD/MM/AAAA.") from exc


def _pedir_periodo(args) -> tuple[date, date]:
    if args.inicio or args.fim:
        if not (args.inicio and args.fim):
            raise ErroConciliacao("Informe --inicio e --fim juntos, no formato DD/MM/AAAA.")
        inicio, fim = _data(args.inicio), _data(args.fim)
        if fim < inicio:
            raise ErroConciliacao("A data final é menor que a inicial.")
        return inicio, fim
    raise ErroConciliacao("Informe --inicio e --fim, no formato DD/MM/AAAA.")


def _carregar_env() -> None:
    load_dotenv(raiz() / ".env")


def _pipeline(nome: str) -> dict:
    caminho = pasta_pipelines() / f"{nome}.yaml"
    if not caminho.is_file():
        raise ErroConciliacao(f"Não achei o pipeline {caminho}.")
    with caminho.open(encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def _sql(nome: str) -> tuple[str, Path]:
    for pasta in (pasta_scripts() / "oracle", pasta_scripts() / "sqlserver"):
        caminho = pasta / nome
        if caminho.is_file():
            return caminho.read_text(encoding="utf-8"), caminho
    raise ErroConciliacao(f"Não achei o script {nome}.")


def _br(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _destino(inicio: date, fim: date) -> Path:
    pai = pasta_trabalho().resolve().parent.name.strip()
    if inicio.year == fim.year and inicio.month == fim.month:
        competencia = f"{inicio:%m.%Y}"
    else:
        competencia = f"{inicio:%m.%Y} a {fim:%m.%Y}"
    return pasta_saida() / f"{pai} - {competencia}.xlsx"


def _numero(valor) -> float:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return 0.0
    return round(float(valor), 2)


def _texto(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def _data_sinqia(valor) -> date | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(int(valor)) if isinstance(valor, float) else str(valor).strip()
    return datetime.strptime(texto[:8], "%Y%m%d").date()


def _preparar_protheus(quadro: pd.DataFrame, contra_irpj: str, conta: str) -> pd.DataFrame:
    if quadro.empty:
        raise ErroConciliacao("O CT2010 não devolveu o lançamento de outubro.")
    saida = quadro.copy()
    for coluna in saida.columns:
        if saida[coluna].dtype == object:
            saida[coluna] = saida[coluna].map(_texto)
    credito = saida["CT2_CREDIT"].map(_texto)
    debito = saida["CT2_DEBITO"].map(_texto)
    saida["GRUPO"] = credito.map(lambda item: "IRPJ" if item == contra_irpj else "CSLL")
    saida["VALOR_SINAL"] = [
        _numero(valor) if _texto(lado) == conta else -_numero(valor)
        for valor, lado in zip(saida["CT2_VALOR"], debito, strict=True)
    ]
    saida["CT2_VALOR"] = saida["CT2_VALOR"].map(_numero)
    return saida


def _preparar_sinqia(quadro: pd.DataFrame, sinqia_irpj: str) -> pd.DataFrame:
    if quadro.empty:
        raise ErroConciliacao("O CT005 não devolveu a implantação de 30/10/2026.")
    saida = quadro.copy()
    for coluna in saida.columns:
        if saida[coluna].dtype == object:
            saida[coluna] = saida[coluna].map(_texto)
    saida["CONTA"] = saida["CONTA"].map(_texto)
    saida["DATA"] = saida["DATA"].map(_data_sinqia)
    saida["GRUPO"] = saida["CONTA"].map(lambda item: "IRPJ" if item == sinqia_irpj else "CSLL")
    saida["VALOR"] = [
        -_numero(valor) if _texto(tipo) == "C" else _numero(valor)
        for valor, tipo in zip(saida["VALOR_LANC"], saida["TIPO"], strict=True)
    ]
    saida["VALOR_LANC"] = saida["VALOR_LANC"].map(_numero)
    saida["LOTE"] = saida["LOTE"].map(lambda item: _texto(int(item)) if str(item).replace(".", "", 1).isdigit() else _texto(item))
    saida["DOC"] = saida["DOC"].map(lambda item: _texto(int(float(item))) if str(item).strip() not in {"", "None"} else "0")
    return saida


def executar(args) -> Path:
    inicio, fim = _pedir_periodo(args)
    _carregar_env()
    pipeline = _pipeline(args.pipeline)
    p = pipeline["parametros"]
    sql_protheus, caminho_protheus = _sql("protheus_ct2_credito_tributario.sql")
    sql_sinqia, caminho_sinqia = _sql("sinqia_ct_credito_tributario.sql")

    oracle = criar_engine("oracle")
    protheus = ler(
        oracle,
        sql_protheus,
        {
            "data_ini": f"{inicio:%Y%m%d}",
            "data_fim": f"{fim:%Y%m%d}",
            "filial": str(p["filial"]),
            "conta": str(p["conta"]),
            "contra_irpj": str(p["contra_irpj"]),
            "contra_csll": str(p["contra_csll"]),
        },
        caminho_protheus.name,
        {"data_ini": 8, "data_fim": 8, "filial": 6, "conta": 20, "contra_irpj": 20, "contra_csll": 20},
    )
    sqlserver = criar_engine("sqlserver")
    sinqia = ler(
        sqlserver,
        sql_sinqia,
        {
            "data_ini": int(f"{inicio:%Y%m%d}"),
            "data_fim": int(f"{fim:%Y%m%d}"),
            "instituicao": int(p["instituicao"]),
            "agencia": int(p["agencia"]),
            "plano": int(p["plano"]),
            "sinqia_irpj": str(p["sinqia_irpj"]),
            "sinqia_csll": str(p["sinqia_csll"]),
        },
        caminho_sinqia.name,
    )
    razao = _preparar_protheus(protheus, str(p["contra_irpj"]), str(p["conta"]))
    movimento = _preparar_sinqia(sinqia, str(p["sinqia_irpj"]))
    total_protheus = round(float(razao["VALOR_SINAL"].sum()), 2)
    total_sinqia = round(float(movimento["VALOR"].sum()), 2)
    diferenca = round(total_protheus + total_sinqia, 2)
    if abs(diferenca) > float(p["tolerancia"]):
        raise ErroConciliacao(
            f"A diferença não zerou: Protheus {_br(total_protheus)}, Sinqia {_br(total_sinqia)}, diferença {_br(diferenca)}."
        )
    if len(razao) != 2 or len(movimento) != 2:
        raise ErroConciliacao(
            f"Esperava 2 linhas de cada lado e vieram {len(razao)} do Protheus e {len(movimento)} do Sinqia."
        )

    destino = _destino(inicio, fim)
    if "09.2026" in destino.name:
        raise ErroConciliacao("Setembro já está gravado e não entra nesta rodada.")
    gravar(
        destino,
        str(pipeline["nome"]),
        str(pipeline["empresa"]),
        str(p["conta"]),
        str(p["descricao"]),
        f"{p['sinqia_irpj']} / {p['sinqia_csll']}",
        float(p["tolerancia"]),
        inicio,
        fim,
        razao,
        movimento,
        os.getenv("CONCILIACAO_FEITO_POR", "").strip(),
    )
    print(f"Protheus {_br(total_protheus)}")
    print(f"Sinqia {_br(total_sinqia)}")
    print(f"Diferença {_br(diferenca)}")
    print(destino)
    return destino


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="conciliacao")
    sub = parser.add_subparsers(dest="comando", required=True)
    rodar = sub.add_parser("rodar")
    rodar.add_argument("pipeline")
    rodar.add_argument("--inicio")
    rodar.add_argument("--fim")
    args = parser.parse_args(argv)
    try:
        if args.comando == "rodar":
            executar(args)
    except ErroConciliacao as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
