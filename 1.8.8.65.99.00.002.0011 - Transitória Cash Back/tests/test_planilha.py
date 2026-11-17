from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from conciliacao.catalogo import carregar_pipelines, carregar_scripts
from conciliacao.conciliar import conciliar
from conciliacao.planilha import ABA_CONCILIACAO, ABA_EXECUCAO, ABA_SALDOS, gravar


def _gerar(tmp_path: Path):
    scripts = carregar_scripts()
    pipeline = carregar_pipelines(scripts)["teddoc_outras_instituicoes"]
    protheus = pd.DataFrame(
        {
            "CT2_FILIAL": ["030101", "030101"],
            "CT2_DATA": [datetime(2026, 9, 1), datetime(2026, 9, 2)],
            "CT2_DEBITO": ["11030101063", "11010201025"],
            "CT2_CREDIT": ["11010201025", "11030101063"],
            "CT2_YDESDB": ["TRANSACOES TED/DOC", "CONTA SPB"],
            "CT2_YDESCR": ["CONTA SPB", "TRANSACOES TED/DOC"],
            "VALOR_SINAL": [-100.0, 40.0],
        }
    )
    sinqia = pd.DataFrame(
        {
            "CT001_CT_CONT": ["1886599000020011", "1886599000020011"],
            "CT001_DS_NOMCT": [
                "Transacoes Ted/Doc Outras Instituicoes",
                "Transacoes Ted/Doc Outras Instituicoes",
            ],
            "DATA": [datetime(2026, 9, 1), datetime(2026, 9, 2)],
            "VALOR": [100.0, -40.0],
        }
    )
    balancete = pd.DataFrame(
        {
            "CONTA": ["1886599000020011"],
            "NOME": ["Transacoes Ted/Doc Outras Instituicoes"],
            "SALDO_ANTERIOR": [1500.25],
            "SALDO_ATUAL": [1560.25],
        }
    )
    extratos = {
        "protheus_ct2_razao": protheus,
        "sinqia_ct_razao": sinqia,
        "sinqia_ct_balancete": balancete,
        "sinqia_cc_razao": pd.DataFrame(),
    }
    resultado = conciliar(
        sinqia,
        protheus,
        "DATA",
        "VALOR",
        "CT2_DATA",
        "VALOR_SINAL",
        "WP-03 Sinqia CT",
        "WP-02 Protheus",
        "soma",
        0.01,
    )
    caminho = tmp_path / "teddoc.xlsx"
    gravar(
        caminho,
        pipeline,
        scripts,
        extratos,
        resultado,
        None,
        date(2026, 9, 1),
        date(2026, 9, 30),
        "dev",
    )
    return load_workbook(caminho)


def test_excel_abre_pela_capa_e_calcula_saldos_por_formula(tmp_path: Path):
    wb = _gerar(tmp_path)
    assert wb.sheetnames[0] == ABA_SALDOS
    assert "WP-02 Protheus" in wb.sheetnames
    assert "WP-03 Sinqia CT" in wb.sheetnames
    assert ABA_CONCILIACAO in wb.sheetnames
    assert ABA_EXECUCAO in wb.sheetnames
    assert "WP-04 Sinqia CC" not in wb.sheetnames
    assert "Composição" not in wb.sheetnames

    capa = wb[ABA_SALDOS]
    assert capa["C5"].value == "Banco Senff"
    assert capa["C17"].value == "1886599000020011"
    assert "TRANSACOES TED/DOC OUTRAS" in capa["D17"].value
    assert capa["E17"].value == 1500.25
    assert capa["C18"].value == "11030101063"
    assert capa["D18"].value == "TRANSACOES TED/DOC"
    assert capa["G18"].value == 0
    assert capa["F17"].value == "=E17+SUM(tbl_sinqia_ct_razao[VALOR])"
    assert capa["H18"].value == "=G18+SUM(tbl_protheus_ct2_razao[VALOR_SINAL])"
    assert capa["I17"].value == "=ROUND(F17+H18,2)"
    assert capa["K17"].value == "=ROUND(I17-J17,2)"

    conc = wb[ABA_CONCILIACAO]
    assert conc["B9"].value == "DATA"
    assert "SUMIFS(tbl_sinqia_ct_razao[VALOR],tbl_sinqia_ct_razao[DATA],$B10)" in conc["C10"].value
    assert "SUMIFS(tbl_protheus_ct2_razao[VALOR_SINAL],tbl_protheus_ct2_razao[CT2_DATA],$B10)" in conc["D10"].value
    assert conc["F10"].value == '=IF(ABS(E10)<=Tolerancia,"CONCILIADO","DIFERENÇA")'

    def _dia(valor):
        return valor.date() if isinstance(valor, datetime) else valor

    assert _dia(wb["WP-02 Protheus"]["C12"].value) == date(2026, 9, 1)
    assert _dia(conc["B10"].value) == date(2026, 9, 1)
    assert conc["B10"].number_format == "DD/MM/YYYY"
