"""Excel no desenho da WP do Repasse Folha: capa, razão, outro lado e encontro.

Os lançamentos entram como valor. Soma, diferença e status entram como fórmula.
Débito positivo, crédito negativo. A diferença é a soma dos dois lados.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

ABA_SALDOS = "WP-01 Saldos"
ABA_RAZAO = "WP-02 Razão"
ABA_SINQIA = "WP-03 Sinqia"
ABA_ENCONTRO = "WP-04 Encontro"

_FONTE = "Arial"
_NAVY = "1F3864"
_CINZA = "F2F2F2"
_CINZA_TEXTO = "595959"
_CINZA_BORDA = "BFBFBF"
_VERDE_FUNDO = "C6EFCE"
_VERDE_TEXTO = "006100"
_VERMELHO_FUNDO = "FFC7CE"
_VERMELHO_TEXTO = "9C0006"
_AMARELO = "FFF2CC"
_AZUL_INPUT = "0000FF"

_FMT_VALOR = '_-* #,##0.00_-;\\-* #,##0.00_-;_-* "-"??_-;_-@_-'
_FMT_DATA = "DD/MM/YYYY"
_FMT_DATA_HORA = "DD/MM/YYYY HH:MM"

_FINO = Side(style="thin", color=_CINZA_BORDA)
_MEDIO = Side(style="medium", color=_NAVY)
_DUPLO = Side(style="double", color=_NAVY)
_LINHA_TABELA = 11


def _fonte(tamanho=10, negrito=False, cor="000000", italico=False) -> Font:
    return Font(name=_FONTE, size=tamanho, bold=negrito, color=cor, italic=italico)


def _fundo(cor: str) -> PatternFill:
    return PatternFill("solid", fgColor=cor)


_TEXTO = _fonte()
_ROTULO = _fonte(9, True, _CINZA_TEXTO)
_SECAO = _fonte(11, True, _NAVY)
_CABECALHO = _fonte(10, True, "FFFFFF")
_INPUT = _fonte(10, False, _AZUL_INPUT)


def _q(aba: str) -> str:
    return "'" + aba.replace("'", "''") + "'"


def _faixa(ws: Worksheet, titulo: str, subtitulo: str, ultima_coluna: int) -> None:
    ws.row_dimensions[1].height = 8
    ws.row_dimensions[2].height = 26
    ws.row_dimensions[3].height = 18
    fim = get_column_letter(max(ultima_coluna, 3))
    for linha, texto, fonte in (
        (2, titulo, _fonte(15, True, "FFFFFF")),
        (3, subtitulo, _fonte(10, False, "D9E1F2")),
    ):
        for coluna in range(2, max(ultima_coluna, 3) + 1):
            ws.cell(linha, coluna).fill = _fundo(_NAVY)
        ws.merge_cells(f"B{linha}:{fim}{linha}")
        celula = ws.cell(linha, 2, texto)
        celula.font = fonte
        celula.alignment = Alignment(vertical="center", indent=1)
    ws.column_dimensions["A"].width = 2.5
    ws.sheet_view.showGridLines = False


def _secao(ws: Worksheet, linha: int, texto: str, ultima_coluna: int) -> None:
    celula = ws.cell(linha, 2, texto.upper())
    celula.font = _SECAO
    for coluna in range(2, ultima_coluna + 1):
        ws.cell(linha, coluna).border = Border(bottom=_MEDIO)
    ws.row_dimensions[linha].height = 20


def _par(ws, linha, coluna, rotulo, valor, formato=None, fonte=None, mesclar_ate=None, fundo=None):
    r = ws.cell(linha, coluna, rotulo)
    r.font = _ROTULO
    r.alignment = Alignment(vertical="center")
    r.border = Border(bottom=_FINO)
    v = ws.cell(linha, coluna + 1, valor)
    v.font = fonte or _fonte(10, True)
    v.alignment = Alignment(horizontal="left", vertical="center")
    if formato:
        v.number_format = formato
    ultima = mesclar_ate or coluna + 1
    for c in range(coluna + 1, ultima + 1):
        ws.cell(linha, c).border = Border(bottom=_FINO)
        if fundo:
            ws.cell(linha, c).fill = _fundo(fundo)
    if mesclar_ate and mesclar_ate > coluna + 1:
        ws.merge_cells(start_row=linha, start_column=coluna + 1, end_row=linha, end_column=mesclar_ate)
    return v


def _cabecalho(celula) -> None:
    celula.font = _CABECALHO
    celula.fill = _fundo(_NAVY)
    celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _status_cf(ws: Worksheet, faixa: str) -> None:
    ws.conditional_formatting.add(
        faixa,
        CellIsRule(
            operator="equal",
            formula=['"CONCILIADO"'],
            fill=_fundo(_VERDE_FUNDO),
            font=Font(name=_FONTE, bold=True, color=_VERDE_TEXTO),
        ),
    )
    ws.conditional_formatting.add(
        faixa,
        CellIsRule(
            operator="notEqual",
            formula=['"CONCILIADO"'],
            fill=_fundo(_VERMELHO_FUNDO),
            font=Font(name=_FONTE, bold=True, color=_VERMELHO_TEXTO),
        ),
    )


def _retrato(ws: Worksheet, paisagem=True) -> None:
    ws.page_setup.orientation = "landscape" if paisagem else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.sheet_view.view = "normal"
    ws.sheet_properties.tabColor = _NAVY


def _limpar(valor):
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except TypeError:
        pass
    if isinstance(valor, str):
        texto = valor.strip()
        return texto or None
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def _caminho_gravavel(caminho: Path) -> Path:
    return caminho


def _tabela(ws: Worksheet, nome: str, colunas: list[str], quadro: pd.DataFrame, monetarias: set[str]) -> None:
    for indice, titulo in enumerate(colunas, start=2):
        _cabecalho(ws.cell(_LINHA_TABELA, indice, titulo))
    for deslocamento, registro in enumerate(quadro.itertuples(index=False), start=1):
        for indice, valor in enumerate(registro, start=2):
            limpo = _limpar(valor)
            celula = ws.cell(_LINHA_TABELA + deslocamento, indice, limpo)
            celula.font = _TEXTO
            nome_coluna = colunas[indice - 2]
            if isinstance(limpo, datetime):
                celula.number_format = _FMT_DATA
            elif isinstance(limpo, date):
                celula.number_format = _FMT_DATA
            elif nome_coluna in monetarias and isinstance(limpo, (int, float)):
                celula.number_format = _FMT_VALOR
            elif isinstance(limpo, str) and nome_coluna in {
                "CT2_FILIAL", "CT2_DEBITO", "CT2_CREDIT", "CT2_LOTE", "CT2_DOC", "CONTA", "COSIF", "LOTE", "DOC",
            }:
                celula.number_format = "@"
    ultima = _LINHA_TABELA + max(len(quadro), 1)
    fim = get_column_letter(len(colunas) + 1)
    tab = Table(displayName=nome, ref=f"B{_LINHA_TABELA}:{fim}{ultima}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tab)
    ws.freeze_panes = f"B{_LINHA_TABELA + 1}"
    ws.row_dimensions[_LINHA_TABELA].height = 22
    linha_total = ultima + 2
    rotulo = ws.cell(linha_total, 2, "Total")
    rotulo.font = _fonte(10, True, _NAVY)
    for indice, titulo in enumerate(colunas, start=2):
        celula = ws.cell(linha_total, indice)
        celula.border = Border(top=_FINO, bottom=_DUPLO)
        if titulo in monetarias:
            celula.value = f"=SUBTOTAL(109,{nome}[{titulo}])"
            celula.number_format = _FMT_VALOR
            celula.font = _fonte(10, True, _NAVY)
    for indice, titulo in enumerate(colunas, start=2):
        amostra = [len(titulo) + 3]
        for item in quadro.iloc[:, indice - 2].head(200):
            if item is None or (isinstance(item, float) and pd.isna(item)):
                continue
            amostra.append(min(len(str(item).strip()), 40))
        ws.column_dimensions[get_column_letter(indice)].width = min(max(max(amostra) + 2, 12), 42)


def gravar(
    caminho: Path,
    nome: str,
    empresa: str,
    conta: str,
    descricao: str,
    contas_sinqia: str,
    tolerancia: float,
    inicio: date,
    fim: date,
    razao: pd.DataFrame,
    sinqia: pd.DataFrame,
    feito_por: str,
) -> None:
    wb = Workbook()
    capa = wb.active
    capa.title = ABA_SALDOS
    for nome_def, celula in (("DataInicial", "$I$5"), ("DataFinal", "$I$6"), ("Tolerancia", "$C$7")):
        wb.defined_names.add(DefinedName(nome_def, attr_text=f"{_q(ABA_SALDOS)}!{celula}"))

    _montar_capa(capa, nome, empresa, conta, descricao, contas_sinqia, tolerancia, inicio, fim, feito_por, len(razao), len(sinqia))
    _aba_razao(wb.create_sheet(ABA_RAZAO), nome, conta, razao)
    _aba_sinqia(wb.create_sheet(ABA_SINQIA), nome, contas_sinqia, sinqia)
    encontro = wb.create_sheet(ABA_ENCONTRO)
    _cabecalho_encontro(encontro, nome)
    _preencher_encontro(encontro)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb.calculation.fullCalcOnLoad = True
    wb.active = 0
    wb.save(_caminho_gravavel(caminho))


def _montar_capa(capa, nome, empresa, conta, descricao, contas_sinqia, tolerancia, inicio, fim, feito_por, linhas_razao, linhas_sinqia) -> None:
    ultima = 10
    _faixa(capa, "Conciliação Contábil  ·  WP-01 Saldos", nome, ultima)
    larguras = {"B": 18, "C": 34, "D": 28, "E": 18, "F": 16, "G": 18, "H": 16, "I": 18, "J": 16}
    for letra, largura in larguras.items():
        capa.column_dimensions[letra].width = largura

    _par(capa, 5, 2, "Empresa", empresa, mesclar_ate=4)
    _par(capa, 6, 2, "Nome WP", nome, mesclar_ate=6)
    tol = _par(capa, 7, 2, "Tolerância", tolerancia, _FMT_VALOR, fonte=_fonte(10, True, "0000FF"), fundo=_AMARELO)
    tol.alignment = Alignment(horizontal="left")
    capa.cell(7, 3).comment = Comment("Valor do YAML. Pode alterar aqui: as fórmulas recalculam.", "Conciliação")
    _par(
        capa, 8, 2, "Regra",
        "Diferença = Protheus + Sinqia. Débito positivo, crédito negativo.",
        mesclar_ate=6,
    )
    _par(capa, 5, 8, "Data inicial", inicio, _FMT_DATA, mesclar_ate=10)
    _par(capa, 6, 8, "Data final", fim, _FMT_DATA, mesclar_ate=10)
    _par(capa, 7, 8, "Feito por", feito_por or "", mesclar_ate=10, fonte=_INPUT, fundo=_AMARELO)
    _par(capa, 8, 8, "Gerado em", datetime.now().replace(microsecond=0), _FMT_DATA_HORA, mesclar_ate=10)

    for linha in (11, 12):
        for coluna in range(2, 11):
            capa.cell(linha, coluna).fill = _fundo(_CINZA)
    blocos = (
        (2, 3, "Linhas razão", linhas_razao, "0"),
        (4, 5, "Linhas Sinqia", linhas_sinqia, "0"),
        (6, 7, "Diferença do período", "=I17", _FMT_VALOR),
        (8, 10, "Status", '=IF(ABS(I20)<=Tolerancia,"CONCILIADO","COM DIFERENÇA")', "@"),
    )
    for inicio_col, fim_col, rotulo, valor, formato in blocos:
        if inicio_col != fim_col:
            capa.merge_cells(start_row=11, start_column=inicio_col, end_row=11, end_column=fim_col)
            capa.merge_cells(start_row=12, start_column=inicio_col, end_row=12, end_column=fim_col)
        rot = capa.cell(11, inicio_col, rotulo)
        rot.font = _fonte(8, True, _CINZA_TEXTO)
        rot.alignment = Alignment(horizontal="center")
        celula = capa.cell(12, inicio_col, valor)
        celula.font = _fonte(16, True, _NAVY)
        celula.number_format = formato
        celula.alignment = Alignment(horizontal="center", vertical="center")
    capa.row_dimensions[12].height = 28
    _status_cf(capa, "H12:J12")

    _secao(capa, 14, "Saldos das contas", ultima)
    cabecalhos = (
        (2, 2, "Origem"),
        (3, 3, "Conta"),
        (4, 4, "Descrição"),
        (5, 6, "CONTÁBIL"),
        (7, 8, "SINQIA"),
        (9, 10, "DIFERENÇA"),
    )
    for inicio_col, fim_col, texto in cabecalhos:
        if inicio_col != fim_col:
            capa.merge_cells(start_row=15, start_column=inicio_col, end_row=15, end_column=fim_col)
        celula = capa.cell(15, inicio_col, texto)
        _cabecalho(celula)
        for coluna in range(inicio_col, fim_col + 1):
            capa.cell(15, coluna).fill = _fundo(_NAVY)
            capa.cell(15, coluna).font = _CABECALHO
    capa.row_dimensions[15].height = 20

    capa.cell(17, 2, "Protheus").font = _fonte(10, True)
    capa.cell(17, 2).hyperlink = f"#{_q(ABA_RAZAO)}!A1"
    conta_celula = capa.cell(17, 3, conta)
    conta_celula.number_format = "@"
    conta_celula.font = _fonte(10)
    capa.cell(17, 4, descricao).font = _fonte(10)
    capa.merge_cells("E17:F17")
    capa["E17"] = "=SUM(tbl_razao[VALOR_SINAL])"
    capa.merge_cells("G17:H17")
    capa["G17"] = "=SUM(tbl_sinqia[VALOR])"
    capa.merge_cells("I17:J17")
    capa["I17"] = "=ROUND(E17+G17,2)"
    for celula in ("E17", "G17", "I17"):
        capa[celula].number_format = _FMT_VALOR
        capa[celula].font = _fonte(10, True, _NAVY)
        capa[celula].alignment = Alignment(horizontal="center")

    capa.cell(18, 2, "Sinqia").font = _fonte(10, True)
    capa.cell(18, 2).hyperlink = f"#{_q(ABA_SINQIA)}!A1"
    sinqia = capa.cell(18, 3, contas_sinqia)
    sinqia.number_format = "@"
    sinqia.font = _fonte(10)
    capa.merge_cells("D18:J18")
    capa["D18"] = "CT do Sinqia. O valor entra na coluna SINQIA da linha de cima."
    capa["D18"].font = _fonte(9, italico=True, cor=_CINZA_TEXTO)

    capa.cell(19, 2, "Composição").font = _fonte(10, True)
    capa.merge_cells("C19:H19")
    capa["C19"] = '=COUNTIF(tbl_encontro[STATUS],"DIVERGENTE")&" grupo(s) na aba Encontro"'
    capa["C19"].font = _fonte(10)
    capa.merge_cells("I19:J19")
    capa["I19"] = '=ROUND(SUMIF(tbl_encontro[STATUS],"DIVERGENTE",tbl_encontro[DIFERENCA]),2)'
    capa["I19"].number_format = _FMT_VALOR
    capa["I19"].font = _fonte(10, True, _NAVY)
    capa["I19"].alignment = Alignment(horizontal="center")

    capa.cell(20, 2, "Residual").font = _fonte(10, True)
    capa.merge_cells("C20:H20")
    capa["C20"] = "Diferença do período menos a composição do encontro"
    capa["C20"].font = _fonte(9, italico=True, cor=_CINZA_TEXTO)
    capa.merge_cells("I20:J20")
    capa["I20"] = "=ROUND(I17-I19,2)"
    capa["I20"].number_format = _FMT_VALOR
    capa["I20"].font = _fonte(10, True)
    capa["I20"].alignment = Alignment(horizontal="center")

    _secao(capa, 22, "Conclusão", ultima)
    capa.merge_cells("B23:J24")
    capa["B23"] = (
        '=IF(ABS(I20)<=Tolerancia,'
        '"O razão e o Sinqia fecham no período.",'
        '"A soma dos grupos não explica a diferença do período. Revisar as abas de razão e do Sinqia.")'
    )
    capa["B23"].font = _fonte(10)
    capa["B23"].alignment = Alignment(wrap_text=True, vertical="center")
    capa.row_dimensions[23].height = 20
    capa.row_dimensions[24].height = 20

    nota = capa.cell(28, 2, "Encontro por IRPJ e CSLL, como a WP-04. Filial 030101. Agência 19, instituição 1414, plano 3.")
    nota.font = _fonte(9, italico=True, cor=_CINZA_TEXTO)
    capa.merge_cells("B28:J28")
    capa.freeze_panes = "B15"
    capa.sheet_view.zoomScale = 110
    capa.page_setup.orientation = "portrait"
    capa.page_setup.paperSize = capa.PAPERSIZE_A4
    capa.page_setup.fitToWidth = 1
    capa.page_setup.fitToHeight = 1
    capa.sheet_properties.pageSetUpPr.fitToPage = True
    capa.sheet_view.view = "normal"
    capa.sheet_properties.tabColor = _NAVY
    capa.conditional_formatting.add(
        "I17:J17",
        FormulaRule(formula=["ABS(I17)>Tolerancia"], fill=_fundo(_AMARELO), font=_fonte(10, True, _NAVY)),
    )


def _aba_razao(ws: Worksheet, nome: str, conta: str, razao: pd.DataFrame) -> None:
    colunas = [
        "CT2_FILIAL", "CT2_DATA", "CT2_LOTE", "CT2_DOC", "CT2_DEBITO", "CT2_CREDIT",
        "CT2_VALOR", "CT2_HIST", "GRUPO", "VALOR_SINAL",
    ]
    quadro = razao.reindex(columns=colunas)
    _faixa(ws, ABA_RAZAO, nome, len(colunas) + 1)
    _par(ws, 5, 2, "Empresa", f"={_q(ABA_SALDOS)}!C5", mesclar_ate=4)
    _par(ws, 6, 2, "Conta", conta, mesclar_ate=4)
    _par(ws, 7, 2, "Período", "=DataInicial", _FMT_DATA)
    ws.cell(7, 4, "=DataFinal").number_format = _FMT_DATA
    ws.cell(7, 4).font = _fonte(10, True)
    _par(ws, 8, 2, "Linhas", len(quadro), "#,##0")
    total = _par(ws, 9, 2, "Total da conta", "=SUM(tbl_razao[VALOR_SINAL])", _FMT_VALOR, fonte=_fonte(11, True, _NAVY), mesclar_ate=4)
    total.alignment = Alignment(horizontal="left")
    nota = ws.cell(9, 6, "VALOR_SINAL positivo no débito e negativo no crédito. Filial 030101.")
    nota.font = _fonte(8, italico=True, cor=_CINZA_TEXTO)
    _tabela(ws, "tbl_razao", colunas, quadro, {"CT2_VALOR", "VALOR_SINAL"})
    _retrato(ws)


def _aba_sinqia(ws: Worksheet, nome: str, contas: str, sinqia: pd.DataFrame) -> None:
    colunas = [
        "CONTA", "COSIF", "NOME", "DATA", "LOTE", "DOC", "TP_LOTE", "TIPO",
        "VALOR_LANC", "HIST", "GRUPO", "VALOR",
    ]
    quadro = sinqia.reindex(columns=colunas)
    _faixa(ws, ABA_SINQIA, nome, len(colunas) + 1)
    _par(ws, 5, 2, "Empresa", f"={_q(ABA_SALDOS)}!C5", mesclar_ate=4)
    _par(ws, 6, 2, "Conta", contas, mesclar_ate=8)
    _par(ws, 7, 2, "Período", "=DataInicial", _FMT_DATA)
    ws.cell(7, 4, "=DataFinal").number_format = _FMT_DATA
    ws.cell(7, 4).font = _fonte(10, True)
    _par(ws, 8, 2, "Linhas", len(quadro), "#,##0")
    total = _par(ws, 9, 2, "Total da conta", "=SUM(tbl_sinqia[VALOR])", _FMT_VALOR, fonte=_fonte(11, True, _NAVY), mesclar_ate=4)
    total.alignment = Alignment(horizontal="left")
    nota = ws.cell(9, 6, "VALOR negativo no crédito. Agência 19, instituição 1414, plano 3.")
    nota.font = _fonte(8, italico=True, cor=_CINZA_TEXTO)
    _tabela(ws, "tbl_sinqia", colunas, quadro, {"VALOR_LANC", "VALOR"})
    _retrato(ws)


def _cabecalho_encontro(ws: Worksheet, nome: str) -> None:
    _faixa(ws, ABA_ENCONTRO, nome, 8)
    _par(ws, 5, 2, "Sinqia", "WP-03 Sinqia  ·  soma de VALOR por grupo", mesclar_ate=6)
    _par(ws, 6, 2, "Razão", "WP-02 Razão  ·  soma de VALOR_SINAL por grupo", mesclar_ate=6)
    _par(ws, 7, 2, "Regra", "Diferença = Protheus + Sinqia. Conciliado se passar dentro da tolerância.", mesclar_ate=5)
    ws.cell(7, 6, "Tolerância").font = _ROTULO
    tol = ws.cell(7, 7, "=Tolerancia")
    tol.number_format = _FMT_VALOR
    tol.font = _fonte(10, True)


def _preencher_encontro(ws: Worksheet) -> None:
    colunas = ["GRUPO", "CONTA", "PROTHEUS", "SINQIA", "DIFERENCA", "STATUS", "JUSTIFICATIVA"]
    grupos = (
        ("IRPJ", "35010201004  ·  8941030000010002"),
        ("CSLL", "35010101004  ·  8942030000010002"),
    )
    for indice, titulo in enumerate(colunas, start=2):
        _cabecalho(ws.cell(_LINHA_TABELA, indice, titulo))
    for deslocamento, (grupo, conta) in enumerate(grupos, start=1):
        excel = _LINHA_TABELA + deslocamento
        celula_grupo = ws.cell(excel, 2, grupo)
        celula_grupo.font = _TEXTO
        celula_conta = ws.cell(excel, 3, conta)
        celula_conta.font = _TEXTO
        protheus = ws.cell(excel, 4, f'=SUMIF(tbl_razao[GRUPO],B{excel},tbl_razao[VALOR_SINAL])')
        protheus.number_format = _FMT_VALOR
        protheus.font = _TEXTO
        sinqia = ws.cell(excel, 5, f'=SUMIF(tbl_sinqia[GRUPO],B{excel},tbl_sinqia[VALOR])')
        sinqia.number_format = _FMT_VALOR
        sinqia.font = _TEXTO
        diferenca = ws.cell(excel, 6, f"=ROUND(D{excel}+E{excel},2)")
        diferenca.number_format = _FMT_VALOR
        diferenca.font = _fonte(10, True)
        status = ws.cell(excel, 7, f'=IF(ABS(F{excel})<=Tolerancia,"CONCILIADO","DIVERGENTE")')
        status.font = _fonte(10, True)
        status.alignment = Alignment(horizontal="center")
        just = ws.cell(excel, 8, None)
        just.font = _INPUT
        just.fill = _fundo(_AMARELO)
    ultima = _LINHA_TABELA + len(grupos)
    tab = Table(displayName="tbl_encontro", ref=f"B{_LINHA_TABELA}:H{ultima}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tab)
    ws.freeze_panes = "B12"
    _status_cf(ws, f"G{_LINHA_TABELA + 1}:G{ultima}")
    ws.conditional_formatting.add(
        f"F{_LINHA_TABELA + 1}:F{ultima}",
        FormulaRule(formula=[f"ABS(F{_LINHA_TABELA + 1})>Tolerancia"], fill=_fundo(_AMARELO)),
    )
    larguras = {"B": 14, "C": 46, "D": 16, "E": 16, "F": 16, "G": 16, "H": 36}
    for letra, largura in larguras.items():
        ws.column_dimensions[letra].width = largura
    linha_total = ultima + 2
    ws.cell(linha_total, 2, "Total").font = _fonte(10, True, _NAVY)
    for coluna, titulo in ((4, "PROTHEUS"), (5, "SINQIA"), (6, "DIFERENCA")):
        celula = ws.cell(linha_total, coluna, f"=SUBTOTAL(109,tbl_encontro[{titulo}])")
        celula.number_format = _FMT_VALOR
        celula.font = _fonte(10, True, _NAVY)
        celula.border = Border(top=_FINO, bottom=_DUPLO)
    _retrato(ws)
