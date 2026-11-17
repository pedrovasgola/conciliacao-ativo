from conciliacao.encontro import cruzar
from conciliacao.regras import classe_se5, codigo, sinal
from conciliacao.seguranca import validar_sql
from conciliacao.erros import ErroConciliacao
import pandas as pd
import pytest


def test_sinal_dos_codigos_negativos():
    assert sinal("4", 10) == -10
    assert sinal("400", -3.5) == -3.5
    assert sinal("401", 2) == -2
    assert sinal("101", -8) == 8
    assert codigo("99") == "099"


def test_classe_pelo_titulo_e_pelo_tipo():
    titulos = {"S00598082": {"Baixa Empregador"}, "T1": {"Baixa Boleto Itaú", "Refinanciamento"}}
    assert classe_se5("S00598082", "OP", "OUTRO", titulos) == ("Baixa Empregador", "titulo")
    assert classe_se5("NAOTEM", "REP", "TRIBUNAL", titulos) == ("Baixa Empregador", "tipo")
    assert classe_se5("NAOTEM", "OP", "BANCO SENFF", titulos)[0] == "Estorno Itaú/baixa boleto itau"
    assert classe_se5("T1", "OP", "BANCO SENFF", titulos)[1] == "tipo"


def test_par_empregador_anula_estorno_e_sobra():
    funcao = pd.DataFrame(
        [
            {"ORGAO": "PREF PIRAQUARA", "CLASSE": "Baixa Empregador", "VALOR": 179347.74},
            {"ORGAO": "PREF PIRAQUARA", "CLASSE": "Estorno Baixa Empregador", "VALOR": -133816.60},
            {"ORGAO": "PREF SÃO JOSE", "CLASSE": "Baixa Empregador", "VALOR": 100.0},
        ]
    )
    sql = pd.DataFrame(
        [
            {"ORGAO": "PREF PIRAQUARA", "CLASSE": "Baixa Empregador", "VALOR": -179347.74},
            {"ORGAO": "PREF SÃO JOSE", "CLASSE": "Baixa Empregador", "VALOR": -40.0},
        ]
    )
    grade = cruzar(funcao, sql)
    pira_estorno = grade[
        (grade["Órgão"] == "PREF PIRAQUARA")
        & (grade["Classe"] == "Estorno Baixa Empregador")
        & (grade["Base"] == "FIN-FUNCAO")
    ].iloc[0]
    pira_baixa = grade[
        (grade["Órgão"] == "PREF PIRAQUARA")
        & (grade["Classe"] == "Baixa Empregador")
        & (grade["Base"] == "FIN-FUNCAO")
    ].iloc[0]
    jose = grade[(grade["Órgão"] == "PREF SÃO JOSE") & (grade["Classe"] == "Baixa Empregador")]
    assert pira_estorno["Classificação"] == "Conciliado"
    assert pira_baixa["Classificação"] == "Em branco"
    assert set(jose["Classificação"]) == {"Em branco"}


def test_lib_e_refin_zeram_juntos():
    funcao = pd.DataFrame(
        [
            {"ORGAO": "PREF FOZ", "CLASSE": "Lib. Créd p/ Quit. Refin", "VALOR": -50.0},
            {"ORGAO": "PREF FOZ", "CLASSE": "Refinanciamento", "VALOR": 50.0},
            {"ORGAO": "INSS", "CLASSE": "Lib. Créd p/ Quit. Refin", "VALOR": -10.0},
            {"ORGAO": "INSS", "CLASSE": "Refinanciamento", "VALOR": 4.0},
        ]
    )
    sql = pd.DataFrame(columns=["ORGAO", "CLASSE", "VALOR"])
    grade = cruzar(funcao, sql)
    foz = grade[(grade["Órgão"] == "PREF FOZ") & (grade["Base"] == "FIN-FUNCAO")]
    inss = grade[(grade["Órgão"] == "INSS") & (grade["Base"] == "FIN-FUNCAO") & (grade["Valor"] != 0)]
    assert set(foz.loc[foz["Valor"] != 0, "Classificação"]) == {"Conciliado"}
    assert set(inss["Classificação"]) == {"Em branco"}


def test_sql_so_select():
    validar_sql("SELECT 1 FROM SE5010 WHERE D_E_L_E_T_ = ' '", "ok.sql")
    with pytest.raises(ErroConciliacao):
        validar_sql("DELETE FROM SE5010", "ruim.sql")
