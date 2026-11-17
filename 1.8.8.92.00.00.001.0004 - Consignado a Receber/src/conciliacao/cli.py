"""Linha de comando da conciliação do Consignado a Receber."""

from __future__ import annotations

import argparse
import calendar
import os
import sys
from datetime import date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from conciliacao.caminhos import pasta_entrada, pasta_pipelines, pasta_saida, pasta_scripts, pasta_trabalho, raiz
from conciliacao.conexoes import criar_engine, ler
from conciliacao.encontro import cruzar
from conciliacao.erros import ErroConciliacao
from conciliacao.funcao import ler_funcao, titulos_da_movimentacao
from conciliacao.planilha import gravar
from conciliacao.regras import centavos
from conciliacao.seguranca import validar_sql
from conciliacao.sql_se5 import preparar_sql


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
    if not sys.stdin.isatty():
        raise ErroConciliacao("Informe --inicio e --fim (DD/MM/AAAA).")
    hoje = date.today()
    padrao_ini = hoje.replace(day=1)
    padrao_fim = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1])
    print("Informe o período da conciliação:")
    while True:
        bruto_ini = input(f"  Data inicial (DD/MM/AAAA) [Enter = {padrao_ini:%d/%m/%Y}]: ").strip()
        bruto_fim = input(f"  Data final   (DD/MM/AAAA) [Enter = {padrao_fim:%d/%m/%Y}]: ").strip()
        inicio = _data(bruto_ini) if bruto_ini else padrao_ini
        fim = _data(bruto_fim) if bruto_fim else padrao_fim
        if fim >= inicio:
            return inicio, fim
        print("  A data final é menor que a inicial. Tente de novo.")


def _carregar_env() -> None:
    for pasta in (pasta_trabalho(), raiz()):
        arquivo = pasta / ".env"
        if arquivo.is_file():
            load_dotenv(arquivo, override=False)
            return
    raise ErroConciliacao("Não achei o arquivo .env. Copie .env.example para .env e preencha as credenciais.")


def _pipeline(nome: str) -> dict:
    caminho = pasta_pipelines() / f"{nome}.yaml"
    if not caminho.is_file():
        raise ErroConciliacao(f"Não achei {caminho.name}.")
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, dict) or dados.get("id") != nome:
        raise ErroConciliacao(f"pipelines/{nome}.yaml está incompleto.")
    return dados


def _sql() -> tuple[str, Path]:
    caminho = pasta_scripts() / "oracle" / "protheus_se5_se1_consignado.sql"
    if not caminho.is_file():
        raise ErroConciliacao(f"Não achei {caminho.name}.")
    sql = caminho.read_text(encoding="utf-8")
    validar_sql(sql, caminho.name)
    return sql, caminho


def _achar_funcao(inicio: date, fim: date, explicito: str | None) -> Path:
    if explicito:
        caminho = Path(explicito).expanduser()
        if not caminho.is_file():
            raise ErroConciliacao(f"Não achei a movimentação do Função: {caminho}")
        return caminho
    pasta = pasta_entrada()
    marcas = (f"{inicio:%Y-%m}", f"{inicio:%m.%Y}", f"{inicio:%Y%m}")
    if inicio.year == fim.year and inicio.month == fim.month and pasta.is_dir():
        achados = [
            item
            for item in sorted(pasta.glob("*.xlsx"))
            if any(marca in item.name for marca in marcas) and not item.name.startswith("~$")
        ]
        if len(achados) == 1:
            return achados[0]
        if len(achados) > 1:
            nomes = ", ".join(item.name for item in achados)
            raise ErroConciliacao(f"Há mais de um Excel do Função para o mês em entrada/: {nomes}")
    raise ErroConciliacao(
        "Informe --funcao com o Excel da Movimentação Financeira. "
        f"Ou deixe um arquivo em {pasta} com {inicio:%Y-%m} no nome."
    )


def _br(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _destino(inicio: date, fim: date, pasta: str | None) -> Path:
    base = Path(pasta) if pasta else pasta_saida()
    pai = pasta_trabalho().resolve().parent.name.strip()
    if inicio.year == fim.year and inicio.month == fim.month:
        competencia = f"{inicio:%m.%Y}"
    else:
        competencia = f"{inicio:%m.%Y} a {fim:%m.%Y}"
    return base / f"{pai} - {competencia}.xlsx"


def _consultar(engine, sql: str, origem: str, inicio: date, fim: date, filial: str):
    params = {"data_ini": f"{inicio:%Y%m%d}", "data_fim": f"{fim:%Y%m%d}", "filial": filial}
    quadro = ler(engine, sql, params, origem, {"data_ini": 8, "data_fim": 8, "filial": 6})
    if quadro.empty:
        quadro = ler(engine, sql, params, origem, {"data_ini": 8, "data_fim": 8})
    return quadro


def executar(args) -> Path:
    inicio, fim = _pedir_periodo(args)
    _carregar_env()
    pipeline = _pipeline(args.pipeline)
    parametros = pipeline["parametros"]
    sql, caminho_sql = _sql()
    arquivo_funcao = _achar_funcao(inicio, fim, args.funcao)
    funcao = ler_funcao(arquivo_funcao)
    titulos = titulos_da_movimentacao(funcao)
    engine = criar_engine()
    bruto = _consultar(engine, sql, caminho_sql.name, inicio, fim, str(parametros["filial"]))
    sql_grade = preparar_sql(bruto, funcao, titulos)
    grade = cruzar(funcao.assign(CLASSE=funcao["MOVIMENTO"]), sql_grade)
    destino = _destino(inicio, fim, args.saida)

    total_funcao = centavos(funcao["VALOR"].sum() if not funcao.empty else 0)
    total_sql = centavos(sql_grade["VALOR"].sum() if not sql_grade.empty else 0)
    diferenca = centavos(total_funcao + total_sql)
    ref_f = float(parametros["referencia_funcao"])
    ref_s = float(parametros["referencia_sql"])
    ref_d = float(parametros["referencia_diferenca"])
    bateu = abs(total_funcao - ref_f) < 0.01 and abs(total_sql - ref_s) < 0.01 and abs(diferenca - ref_d) < 0.01

    print(f"\n{pipeline['nome']}")
    print(f"Pasta em uso: {pasta_trabalho()}")
    print(f"Excel: {destino}")
    print(f"Período {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")
    print(f"Natureza {parametros['natureza']}  filial {parametros['filial']}")
    print(f"  função    {len(funcao):>8,} linhas   {_br(total_funcao)}")
    print(f"  SQL       {len(sql_grade):>8,} linhas   {_br(total_sql)}")
    print(f"  diferença Função + SQL  {_br(diferenca)}")
    print(f"  referência              {_br(ref_d)}")
    print("  total bateu com a referência: " + ("sim" if bateu else "não"))
    gravar(
        destino,
        pipeline["nome"],
        pipeline.get("empresa", ""),
        str(parametros.get("conta_sinqia", "")),
        str(parametros.get("descricao", "")),
        str(parametros.get("natureza", "")),
        str(parametros.get("filial", "")),
        float(parametros.get("tolerancia", 0.01)),
        inicio,
        fim,
        funcao,
        sql_grade,
        grade,
        str(arquivo_funcao),
        os.getenv("CONCILIACAO_FEITO_POR", "").strip(),
        (ref_f, ref_s, ref_d),
    )
    print(f"  Arquivo {destino}")
    return destino


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="conciliacao", description="Concilia o Consignado a Receber.")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("listar", aliases=["list"], help="Mostra a conciliação e o script.")
    rodar = sub.add_parser("rodar", aliases=["run"], help="Roda a conciliação do mês.")
    rodar.add_argument("pipeline", nargs="?", default="consignado_a_receber")
    rodar.add_argument("--inicio", help="Data inicial DD/MM/AAAA.")
    rodar.add_argument("--fim", help="Data final DD/MM/AAAA.")
    rodar.add_argument("--funcao", help="Excel da Movimentação Financeira do Função.")
    rodar.add_argument("--saida", help="Pasta do Excel. O padrão é saida/.")
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        if args.comando in {"listar", "list"}:
            pipeline = _pipeline("consignado_a_receber")
            sql, caminho = _sql()
            print(pipeline["nome"])
            print(f"Script: {caminho}")
            print(f"Natureza {pipeline['parametros']['natureza']}  filial {pipeline['parametros']['filial']}")
            return
        if args.pipeline != "consignado_a_receber":
            raise ErroConciliacao("A conciliação disponível é consignado_a_receber.")
        executar(args)
    except ErroConciliacao as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)
