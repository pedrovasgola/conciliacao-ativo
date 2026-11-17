"""Excel da conciliação, no mesmo desenho do robô do Repasse Folha."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

AZUL = "1F4E79"
AZUL_CLARO = "D6E3F0"
CINZA = "F2F2F2"
VERDE = "E2EFDA"
AMARELO = "FFF2CC"
LARANJA = "FCE4D6"
BRANCO = "FFFFFF"
FINO = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
MOEDA = '#,##0.00'
DATA = "DD/MM/YYYY HH:MM"


def _cabecalho(aba, titulos: list[str]) -> None:
    for coluna, titulo in enumerate(titulos, start=1):
        celula = aba.cell(1, coluna, titulo)
        celula.font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
        celula.fill = PatternFill("solid", fgColor=AZUL)
        celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    aba.row_dimensions[1].height = 30
    aba.auto_filter.ref = f"A1:{get_column_letter(len(titulos))}1"
    aba.freeze_panes = "A2"
    aba.page_setup.orientation = "landscape"
    aba.page_setup.fitToPage = True
    aba.page_setup.fitToWidth = 1
    aba.page_setup.fitToHeight = 0
    aba.page_setup.paperSize = aba.PAPERSIZE_A4
    aba.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6, header=0.2, footer=0.2)
    aba.sheet_properties.pageSetUpPr.fitToPage = True
    aba.print_title_rows = "1:1"
    aba.oddHeader.left.text = aba.title
    aba.oddFooter.right.text = "Página &P de &N"
    aba.sheet_view.showGridLines = False


def _larguras(aba, larguras: list[float]) -> None:
    for indice, largura in enumerate(larguras, start=1):
        aba.column_dimensions[get_column_letter(indice)].width = largura


def _moeda(celula, valor) -> None:
    celula.value = round(float(valor or 0), 2)
    celula.number_format = MOEDA
    celula.alignment = Alignment(horizontal="right")


def _cor_status(status: str) -> str:
    if status == "Conciliado":
        return VERDE
    if status == "Compensado":
        return AMARELO
    if status == "Em branco":
        return LARANJA
    return CINZA


def gravar(
    destino: Path,
    nome: str,
    empresa: str,
    conta_sinqia: str,
    descricao: str,
    natureza: str,
    filial: str,
    tolerancia: float,
    inicio: date,
    fim: date,
    funcao: pd.DataFrame,
    sql: pd.DataFrame,
    grade: pd.DataFrame,
    origem_funcao: str,
    feito_por: str,
    referencia: tuple[float, float, float],
) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    livro = Workbook()
    agora = datetime.now()
    total_funcao = round(float(funcao["VALOR"].sum()) if not funcao.empty else 0.0, 2)
    total_sql = round(float(sql["VALOR"].sum()) if not sql.empty else 0.0, 2)
    diferenca = round(total_funcao + total_sql, 2)
    ref_f, ref_s, ref_d = referencia
    bateu = abs(total_funcao - ref_f) < 0.01 and abs(total_sql - ref_s) < 0.01 and abs(diferenca - ref_d) < 0.01

    capa = livro.active
    capa.title = "Regras"
    _cabecalho(capa, ["Campo", "Valor"])
    _larguras(capa, [36, 88])
    linhas = [
        ("Conciliação", nome),
        ("Empresa", empresa),
        ("Conta Sinqia", conta_sinqia),
        ("Descrição", descricao),
        ("Natureza SE5", natureza),
        ("Filial", filial),
        ("Período", f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"),
        ("Arquivo do Função", origem_funcao),
        ("Feito por", feito_por),
        ("Gerado em", agora),
        ("Tolerância", tolerancia),
        ("Função", total_funcao),
        ("SQL na grade", total_sql),
        ("Diferença Função + SQL", diferenca),
        ("Referência Função", ref_f),
        ("Referência SQL", ref_s),
        ("Referência da diferença", ref_d),
        ("Total bateu com a referência", "Sim" if bateu else "Não"),
        (
            "Classe da SE5",
            "Se E5_NUMERO existe como Titulo na movimentação, a classe é o MOVIMENTO desse título. "
            "Se não existe, REP é Baixa Empregador e OP é Estorno Itaú/baixa boleto itau. "
            "BANCO SENFF no beneficiário fica nessa classe de estorno.",
        ),
        (
            "Pares",
            "Baixa Boleto Itaú anula Estorno Baixa Boleto Itaú no mesmo órgão. "
            "Baixa Empregador anula Estorno Baixa Empregador no mesmo órgão. "
            "Lib. Créd p/ Quit. Refin anula Refinanciamento e o par zera.",
        ),
        ("Sinal do SQL", "O valor entra na grade com o sinal trocado (−E5_VALOR). Sem baixa ENF."),
        ("Códigos negativos", "004, 400 e 401."),
    ]
    for linha, (campo, valor) in enumerate(linhas, start=2):
        capa.cell(linha, 1, campo).font = Font(bold=True, name="Calibri")
        celula = capa.cell(linha, 2, valor)
        celula.alignment = Alignment(wrap_text=True, vertical="center")
        if isinstance(valor, float):
            _moeda(celula, valor)
        if isinstance(valor, datetime):
            celula.number_format = DATA
        capa.cell(linha, 1).fill = PatternFill("solid", fgColor=AZUL_CLARO)
        capa.cell(linha, 1).border = FINO
        celula.border = FINO
    capa.row_dimensions[19].height = 48
    capa.row_dimensions[20].height = 48
    capa.page_setup.orientation = "landscape"
    capa.page_setup.fitToPage = True
    capa.page_setup.fitToWidth = 1
    capa.page_setup.fitToHeight = 1
    capa.freeze_panes = "A2"
    capa.print_title_rows = "1:1"
    capa.sheet_view.showGridLines = False

    aba = livro.create_sheet("Grade")
    colunas = ["Base", "Órgão", "Classe", "Valor", "Classificação", "Observação"]
    _cabecalho(aba, colunas)
    _larguras(aba, [16, 36, 36, 18, 18, 62])
    for linha, row in enumerate(grade.itertuples(index=False), start=2):
        aba.cell(linha, 1, row.Base).border = FINO
        aba.cell(linha, 2, row[1]).border = FINO
        aba.cell(linha, 3, row.Classe).border = FINO
        valor = aba.cell(linha, 4)
        _moeda(valor, row.Valor)
        valor.border = FINO
        status = aba.cell(linha, 5, row[4])
        status.border = FINO
        status.fill = PatternFill("solid", fgColor=_cor_status(row[4]))
        nota = aba.cell(linha, 6, row[5])
        nota.border = FINO
        if linha % 2 == 0 and row[4] == "Zerado":
            for coluna in range(1, 5):
                if aba.cell(linha, coluna).fill.fgColor is None or coluna != 5:
                    pass
    aba.auto_filter.ref = f"A1:F{max(2, len(grade) + 1)}"
    aba.page_setup.orientation = "landscape"
    aba.oddHeader.left.text = "Grade"

    totais = livro.create_sheet("Totais por classe")
    _cabecalho(totais, ["Classe", "Linhas Função", "Função", "Linhas SQL", "SQL", "Diferença"])
    _larguras(totais, [36, 16, 18, 14, 18, 18])
    classes = list(dict.fromkeys(grade["Classe"]))
    for linha, classe in enumerate(classes, start=2):
        totais.cell(linha, 1, classe).border = FINO
        ff = funcao[funcao["MOVIMENTO"] == classe] if not funcao.empty else funcao
        ss = sql[sql["CLASSE"] == classe] if not sql.empty else sql
        totais.cell(linha, 2, 0 if ff.empty else len(ff)).border = FINO
        vf = totais.cell(linha, 3)
        _moeda(vf, 0 if ff.empty else ff["VALOR"].sum())
        vf.border = FINO
        totais.cell(linha, 4, 0 if ss.empty else len(ss)).border = FINO
        vs = totais.cell(linha, 5)
        _moeda(vs, 0 if ss.empty else ss["VALOR"].sum())
        vs.border = FINO
        dif = totais.cell(linha, 6, f"=C{linha}+E{linha}")
        dif.number_format = MOEDA
        dif.border = FINO
        dif.font = Font(bold=True)
    rodape = len(classes) + 2
    totais.cell(rodape, 1, "Total").font = Font(bold=True, color="FFFFFF")
    totais.cell(rodape, 1).fill = PatternFill("solid", fgColor=AZUL)
    for coluna, formula in (
        (2, f"=SUM(B2:B{rodape - 1})"),
        (3, f"=SUM(C2:C{rodape - 1})"),
        (4, f"=SUM(D2:D{rodape - 1})"),
        (5, f"=SUM(E2:E{rodape - 1})"),
        (6, f"=C{rodape}+E{rodape}"),
    ):
        celula = totais.cell(rodape, coluna, formula)
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor=AZUL)
        celula.border = FINO
        if coluna != 2 and coluna != 4:
            celula.number_format = MOEDA
    totais.auto_filter.ref = f"A1:F{rodape}"
    totais.page_setup.orientation = "landscape"
    totais.page_setup.fitToPage = True
    totais.page_setup.fitToWidth = 1
    totais.page_setup.fitToHeight = 1
    totais.freeze_panes = "A2"
    totais.print_title_rows = "1:1"
    totais.sheet_view.showGridLines = False

    _detalhe(livro, "Função", funcao, ["DT_MOV", "CONTRATO", "ORGAO", "COD_MOVIMENTO", "MOVIMENTO", "VALOR", "TP", "TITULO"])
    _detalhe(
        livro,
        "SQL",
        sql,
        [
            "E5_DATA",
            "E5_NUMERO",
            "E1_TIPO",
            "E5_BENEF",
            "E1_HIST",
            "E5_MOTBX",
            "E5_VALOR",
            "ORGAO",
            "CLASSE",
            "ORIGEM_CLASSE",
            "VALOR",
        ],
    )
    livro.save(destino)


def _detalhe(livro: Workbook, titulo: str, quadro: pd.DataFrame, colunas: list[str]) -> None:
    aba = livro.create_sheet(titulo)
    presentes = [coluna for coluna in colunas if coluna in quadro.columns]
    _cabecalho(aba, presentes)
    for linha, row in enumerate(quadro.itertuples(index=False), start=2):
        dados = row._asdict() if hasattr(row, "_asdict") else None
        for coluna, nome in enumerate(presentes, start=1):
            valor = quadro.iloc[linha - 2][nome]
            if pd.isna(valor):
                valor = None
            celula = aba.cell(linha, coluna, valor)
            celula.border = FINO
            if nome in {"VALOR", "E5_VALOR"} and valor is not None:
                celula.number_format = MOEDA
            if nome in {"DT_MOV", "E5_DATA", "E5_VENCTO", "E1_BAIXA"} and valor is not None:
                celula.number_format = "DD/MM/YYYY"
            if linha % 2 == 0:
                if nome not in {"VALOR", "E5_VALOR"}:
                    celula.fill = PatternFill("solid", fgColor=CINZA)
    if quadro.empty:
        aba.cell(2, 1, "Sem movimento")
    ultima = max(2, len(quadro) + 1)
    aba.auto_filter.ref = f"A1:{get_column_letter(max(1, len(presentes)))}{ultima}"
    for indice, nome in enumerate(presentes, start=1):
        aba.column_dimensions[get_column_letter(indice)].width = 22 if nome not in {"E1_HIST", "ORGAO", "MOVIMENTO", "CLASSE"} else 36
    aba.page_setup.orientation = "landscape"
    aba.page_setup.fitToPage = True
    aba.page_setup.fitToWidth = 1
    aba.page_setup.fitToHeight = 0
    aba.freeze_panes = "A2"
    aba.print_title_rows = "1:1"
    aba.sheet_view.showGridLines = False
    aba.oddHeader.left.text = titulo
