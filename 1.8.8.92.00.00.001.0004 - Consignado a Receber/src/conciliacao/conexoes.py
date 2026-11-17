"""Conexão de leitura no Oracle. A senha fica só no .env."""

from __future__ import annotations

import os
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from conciliacao.erros import ErroConciliacao
from conciliacao.seguranca import redigir, validar_sql


def _env(nome: str, padrao: str | None = None) -> str:
    valor = os.getenv(nome) or padrao
    if valor is None or not str(valor).strip():
        raise ErroConciliacao(f"Variável {nome} não está no .env.")
    return str(valor).strip().strip('"')


def criar_engine() -> Engine:
    try:
        url = (
            f"oracle+oracledb://{quote_plus(_env('ORA_USER'))}:{quote_plus(_env('ORA_PASS'))}"
            f"@{_env('ORA_HOST')}:{_env('ORA_PORT', '1521')}/?service_name={_env('ORA_SERVICE')}"
        )
        return create_engine(url, pool_pre_ping=True)
    except ErroConciliacao:
        raise
    except Exception as exc:
        raise ErroConciliacao(f"Não foi possível abrir o Oracle: {redigir(str(exc))}") from None


def _preencher_char(params: dict, tamanhos: dict[str, int] | None) -> dict:
    if not tamanhos:
        return params
    preenchido = dict(params)
    for nome, tamanho in tamanhos.items():
        valor = preenchido.get(nome)
        if valor is None:
            continue
        texto = str(valor)
        if len(texto) > tamanho:
            raise ErroConciliacao(
                f"Parâmetro {nome} tem {len(texto)} caracteres e a coluna tem {tamanho}."
            )
        preenchido[nome] = texto.ljust(tamanho)
    return preenchido


def ler(engine: Engine, sql: str, params: dict, origem: str, tamanhos: dict[str, int] | None = None) -> pd.DataFrame:
    validar_sql(sql, origem)
    params = _preencher_char(params, tamanhos)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn, params=params)
    except ErroConciliacao:
        raise
    except Exception as exc:
        raise ErroConciliacao(f"{origem}: falha ao ler o banco. {redigir(str(exc))}") from None
    df.columns = [str(coluna).strip().upper() for coluna in df.columns]
    return df
