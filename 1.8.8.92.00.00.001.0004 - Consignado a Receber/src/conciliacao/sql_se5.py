"""Monta a grade da SE5: classe pelo título, senão pelo tipo, e sinal trocado."""

from __future__ import annotations

import pandas as pd

from conciliacao.erros import ErroConciliacao
from conciliacao.regras import centavos, classe_se5, norm, orgao_historico

COLUNAS = (
    "E5_DATA",
    "E5_VALOR",
    "E5_NATUREZ",
    "E5_VENCTO",
    "E5_DOCUMEN",
    "E5_BENEF",
    "E5_NUMERO",
    "E5_TIPO",
    "E5_MOTBX",
    "E1_TIPO",
    "E1_CLIENTE",
    "E1_NOMCLI",
    "E1_HIST",
    "E1_BAIXA",
)


def _orgaos_do_titulo(funcao: pd.DataFrame) -> dict[str, set[str]]:
    mapa: dict[str, set[str]] = {}
    if funcao is None or funcao.empty or "TITULO" not in funcao.columns:
        return mapa
    for _, row in funcao.iterrows():
        titulo = norm(row["TITULO"])
        orgao = norm(row["ORGAO"])
        if titulo and orgao:
            mapa.setdefault(titulo, set()).add(orgao)
    return mapa


def preparar_sql(bruto: pd.DataFrame, funcao: pd.DataFrame, titulos: dict[str, set[str]]) -> pd.DataFrame:
    faltam = [coluna for coluna in ("E5_VALOR", "E5_NUMERO", "E1_TIPO", "E5_BENEF", "E1_HIST") if coluna not in bruto.columns]
    if faltam:
        raise ErroConciliacao("O SQL não devolveu as colunas " + ", ".join(faltam) + ".")
    orgaos = _orgaos_do_titulo(funcao)
    linhas = []
    for _, row in bruto.iterrows():
        numero = norm(row["E5_NUMERO"])
        tipo = norm(row["E1_TIPO"])
        benef = norm(row["E5_BENEF"])
        classe, origem = classe_se5(numero, tipo, benef, titulos)
        do_titulo = orgaos.get(numero, set())
        if len(do_titulo) == 1:
            orgao = next(iter(do_titulo))
        elif tipo.upper() == "REP":
            orgao = orgao_historico(norm(row["E1_HIST"])) or benef or norm(row.get("E1_NOMCLI", ""))
        else:
            orgao = benef or norm(row.get("E1_NOMCLI", "")) or orgao_historico(norm(row["E1_HIST"]))
        linhas.append(
            {
                "E5_DATA": row["E5_DATA"],
                "E5_VALOR": centavos(row["E5_VALOR"]),
                "E5_NATUREZ": norm(row["E5_NATUREZ"]),
                "E5_VENCTO": row.get("E5_VENCTO"),
                "E5_DOCUMEN": norm(row.get("E5_DOCUMEN", "")),
                "E5_BENEF": benef,
                "E5_NUMERO": numero,
                "E5_TIPO": norm(row.get("E5_TIPO", "")),
                "E5_MOTBX": norm(row.get("E5_MOTBX", "")),
                "E1_TIPO": tipo,
                "E1_CLIENTE": norm(row.get("E1_CLIENTE", "")),
                "E1_NOMCLI": norm(row.get("E1_NOMCLI", "")),
                "E1_HIST": norm(row["E1_HIST"]),
                "E1_BAIXA": row.get("E1_BAIXA"),
                "ORGAO": orgao or "(sem órgão)",
                "CLASSE": classe,
                "ORIGEM_CLASSE": origem,
                "VALOR": centavos(-centavos(row["E5_VALOR"])),
            }
        )
    return pd.DataFrame(linhas)
