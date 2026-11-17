"""Lê a Movimentação Financeira e fica só com os códigos da conta."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from conciliacao.erros import ErroConciliacao
from conciliacao.regras import CODIGOS, centavos, codigo, empregador, norm, sinal

_NOMES = {
    "cod": ("COD_MOVIMENTO", "COD MOVIMENTO", "CÓD. MOVIMENTO", "COD_FIN", "COD.FIN", "CODIGO"),
    "mov": ("MOVIMENTO",),
    "valor": ("VALOR",),
    "orgao": ("EMPREGADOR", "ORGÃO", "ORGAO"),
    "titulo": ("TITULO", "TÍTULO"),
    "data": ("DT_MOV", "DT.MOV", "DT MOV"),
    "contrato": ("CONTRATO",),
    "tp": ("TP", "TP."),
}


def _cabecalho(quadro: pd.DataFrame) -> tuple[int, dict[str, str]]:
    for indice in range(min(8, len(quadro))):
        nomes = {norm(valor).upper(): str(coluna) for coluna, valor in quadro.iloc[indice].items() if norm(valor)}
        if "MOVIMENTO" not in nomes and "COD_MOVIMENTO" not in nomes and "CÓD. MOVIMENTO" not in nomes:
            continue
        mapa = {}
        for papel, opcoes in _NOMES.items():
            for opcao in opcoes:
                if opcao in nomes:
                    mapa[papel] = nomes[opcao]
                    break
        if "mov" in mapa and "valor" in mapa:
            return indice, mapa
    raise ErroConciliacao("Não achei as colunas MOVIMENTO e VALOR na movimentação do Função.")


def ler_funcao(caminho: Path) -> pd.DataFrame:
    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise ErroConciliacao(f"Não achei a movimentação do Função: {arquivo}")
    livro = pd.ExcelFile(arquivo)
    ultimo_erro = None
    candidatos = []
    for aba in livro.sheet_names:
        bruto = pd.read_excel(livro, sheet_name=aba, header=None, dtype=object)
        try:
            linha, mapa = _cabecalho(bruto)
        except ErroConciliacao as exc:
            ultimo_erro = exc
            continue
        quadro = bruto.iloc[linha + 1 :].copy()
        quadro.columns = [str(coluna) for coluna in bruto.columns]
        linhas = []
        for _, row in quadro.iterrows():
            movimento = norm(row[mapa["mov"]])
            valor_bruto = row[mapa["valor"]]
            if not movimento or valor_bruto is None or (isinstance(valor_bruto, float) and pd.isna(valor_bruto)):
                continue
            cod = codigo(row[mapa["cod"]]) if "cod" in mapa else ""
            if cod and cod not in CODIGOS:
                continue
            if not cod and movimento not in {
                "Baixa Empregador",
                "Refinanciamento",
                "Baixa Prejuízo",
                "Baixa Boleto Itaú",
                "Lib. Créd p/ Quit. Refin",
                "BAIXA BANCO SPB",
                "Estorno Baixa Boleto Itaú",
                "Estorno Baixa Empregador",
                "BX EMPREGADOR PRC ANTEC",
                "Baixa Boleto Santander",
            }:
                continue
            valor = sinal(cod or "101", centavos(valor_bruto))
            linhas.append(
                {
                    "DT_MOV": row[mapa["data"]] if "data" in mapa else None,
                    "CONTRATO": norm(row[mapa["contrato"]]) if "contrato" in mapa else "",
                    "ORGAO": empregador(row[mapa["orgao"]]) if "orgao" in mapa else "",
                    "COD_MOVIMENTO": cod,
                    "MOVIMENTO": movimento,
                    "VALOR": valor,
                    "TP": norm(row[mapa["tp"]]) if "tp" in mapa else "",
                    "TITULO": norm(row[mapa["titulo"]]) if "titulo" in mapa else "",
                }
            )
        if linhas:
            nome = aba.casefold().strip()
            peso = 0 if ("moviment" in nome or nome in {"função", "funcao", "mov_fin"}) else 1
            candidatos.append((peso, aba, linhas))
    if not candidatos:
        raise ultimo_erro or ErroConciliacao(f"{arquivo.name} não tem movimentação financeira.")
    candidatos.sort(key=lambda item: item[0])
    return pd.DataFrame(candidatos[0][2])


def titulos_da_movimentacao(funcao: pd.DataFrame) -> dict[str, set[str]]:
    mapa: dict[str, set[str]] = {}
    if "TITULO" not in funcao.columns:
        return mapa
    for _, row in funcao.iterrows():
        titulo = norm(row["TITULO"])
        if not titulo:
            continue
        mapa.setdefault(titulo, set()).add(norm(row["MOVIMENTO"]))
    return mapa
