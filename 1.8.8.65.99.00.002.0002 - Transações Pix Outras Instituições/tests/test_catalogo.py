from datetime import date
from pathlib import Path

import pytest
import yaml

from conciliacao.catalogo import (
    aplicar_conta_ct2,
    aplicar_conta_sinqia,
    carregar_pipelines,
    carregar_scripts,
    fonte_pronta,
    preparar_execucao,
)
from conciliacao.erros import ErroConciliacao
from conciliacao.extrair import montar_parametros
from conciliacao.seguranca import validar_sql


def _script(pasta: Path, nome: str, engine: str = "oracle") -> None:
    (pasta / f"{nome}.sql").write_text(
        f"""-- @id: {nome}
-- @engine: {engine}
-- @descricao: Base {nome}
-- @param: data_ini tipo=texto tamanho=8
-- @param: data_fim tipo=texto tamanho=8
-- @param: conta tipo=texto tamanho=20
-- @coluna.data: DATA
-- @coluna.valor: VALOR
SELECT DATA, VALOR
FROM LANC
WHERE DIA BETWEEN :data_ini AND :data_fim
  AND CONTA = :conta
""",
        encoding="utf-8",
    )


def _pipeline(pasta: Path, nome: str, fontes: list[dict], **extra) -> None:
    corpo = {
        "id": nome,
        "nome": f"Conciliacao {nome}",
        "empresa": "Banco Senff",
        "fontes": fontes,
        "conciliacao": {
            "esquerda": fontes[0].get("como", fontes[0]["script"]),
            "direita": fontes[1].get("como", fontes[1]["script"]),
            "operacao": "soma",
            "tolerancia": 0.01,
        },
    }
    corpo.update(extra)
    (pasta / f"{nome}.yaml").write_text(yaml.safe_dump(corpo, allow_unicode=True), encoding="utf-8")


def test_teddoc_reusa_tres_scripts_e_pula_cc_sem_select():
    scripts = carregar_scripts()
    pipelines = carregar_pipelines(scripts)
    pipeline = pipelines["teddoc_outras_instituicoes"]
    assert [fonte.script for fonte in pipeline.fontes] == [
        "protheus_ct2_razao",
        "sinqia_ct_razao",
        "sinqia_ct_balancete",
        "sinqia_cc_razao",
    ]
    assert pipeline.esquerda == "sinqia_ct_razao"
    assert pipeline.direita == "protheus_ct2_razao"
    assert pipeline.fonte("protheus_ct2_razao").parametros["filial"] == "030101"
    assert pipeline.fonte("protheus_ct2_razao").parametros["conta"] == "11030101040"
    assert "contra" not in pipeline.fonte("protheus_ct2_razao").parametros
    assert pipeline.fonte("sinqia_ct_razao").parametros["conta"] == "1886599000020002"
    assert pipeline.fonte("sinqia_ct_razao").parametros["instituicao"] == "1414"
    assert pipeline.fonte("sinqia_ct_razao").parametros["agencia"] == "19"
    assert pipeline.fonte("sinqia_ct_razao").parametros["plano"] == "3"
    assert pipeline.operacao == "soma"
    assert pipeline.detalhe == "sinqia_cc_razao"
    assert pipeline.fonte("sinqia_cc_razao").opcional
    validar_sql(scripts["protheus_ct2_razao"].sql, "protheus_ct2_razao.sql")
    validar_sql(scripts["sinqia_ct_razao"].sql, "sinqia_ct_razao.sql")
    ct2 = scripts["protheus_ct2_razao"].sql
    assert "CT2_DEBITO = :conta OR CT2_CREDIT = :conta" in ct2
    assert "WHEN CT2_CREDIT = :conta THEN CT2_VALOR * -1" in ct2
    assert ":contra" not in ct2
    assert scripts["protheus_ct2_razao"].coluna("valor") == "VALOR_SINAL"
    assert "TRUNC(TO_DATE" in ct2
    sinqia = scripts["sinqia_ct_razao"].sql
    assert "DATEFROMPARTS" in sinqia
    assert "LTRIM(RTRIM(M.CT005_TP_MOVTO)) = 'D'" in sinqia
    assert "LTRIM(RTRIM(M.CT005_TP_MOVTO)) = 'C'" in sinqia
    preparar_execucao(pipeline, scripts)
    assert not fonte_pronta(pipeline.fonte("sinqia_cc_razao"), scripts["sinqia_cc_razao"])
    assert aplicar_conta_ct2(pipeline, None) is pipeline
    trocada = aplicar_conta_ct2(pipeline, "11020202044")
    trocada = aplicar_conta_sinqia(trocada, "1886599000020099")
    assert trocada.fonte("protheus_ct2_razao").parametros["conta"] == "11020202044"
    assert trocada.fonte("sinqia_ct_razao").parametros["conta"] == "1886599000020099"
    assert trocada.fonte("sinqia_ct_balancete").parametros["conta"] == "1886599000020099"
    assert trocada.fonte("sinqia_cc_razao").parametros["conta"] == "1886599000020099"
    balancete = scripts["sinqia_ct_balancete"].sql
    assert "CT005_DT_MOVTO < :data_ini" in balancete
    assert "SALDO_ANTERIOR" in balancete
    validar_sql(balancete, "sinqia_ct_balancete.sql")


def test_outra_conciliacao_repete_os_scripts_e_soma_o_dela(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    pipelines_dir = tmp_path / "pipelines"
    scripts_dir.mkdir()
    pipelines_dir.mkdir()
    _script(scripts_dir, "base_a")
    _script(scripts_dir, "base_b")
    _script(scripts_dir, "base_extra", engine="sqlserver")
    fonte = lambda nome, conta: {"script": nome, "aba": nome, "parametros": {"conta": conta}}
    _pipeline(pipelines_dir, "conciliacao_x", [fonte("base_a", "1"), fonte("base_b", "2")])
    _pipeline(
        pipelines_dir,
        "conciliacao_t",
        [fonte("base_a", "1"), fonte("base_b", "2"), fonte("base_extra", "3")],
    )
    scripts = carregar_scripts(scripts_dir)
    pipelines = carregar_pipelines(scripts, pipelines_dir)
    ids_x = {fonte.script for fonte in pipelines["conciliacao_x"].fontes}
    ids_t = {fonte.script for fonte in pipelines["conciliacao_t"].fontes}
    assert ids_x == {"base_a", "base_b"}
    assert ids_t == ids_x | {"base_extra"}
    preparar_execucao(pipelines["conciliacao_t"], scripts)
    with pytest.raises(ErroConciliacao, match="--conta"):
        aplicar_conta_ct2(pipelines["conciliacao_t"], "11020202044")


def test_o_mesmo_script_em_duas_contas(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    pipelines_dir = tmp_path / "pipelines"
    scripts_dir.mkdir()
    pipelines_dir.mkdir()
    _script(scripts_dir, "razao")
    _script(scripts_dir, "outra")
    _pipeline(
        pipelines_dir,
        "duas_contas",
        [
            {"script": "razao", "como": "conta_um", "aba": "Conta 1", "parametros": {"conta": "111"}},
            {"script": "razao", "como": "conta_dois", "aba": "Conta 2", "parametros": {"conta": "222"}},
            {"script": "outra", "aba": "Apoio", "parametros": {"conta": "333"}},
        ],
    )
    scripts = carregar_scripts(scripts_dir)
    pipeline = carregar_pipelines(scripts, pipelines_dir)["duas_contas"]
    um = montar_parametros(scripts["razao"], pipeline.fonte("conta_um"), date(2026, 9, 1), date(2026, 9, 30))
    dois = montar_parametros(scripts["razao"], pipeline.fonte("conta_dois"), date(2026, 9, 1), date(2026, 9, 30))
    assert um["conta"] == "111"
    assert dois["conta"] == "222"
    assert um["data_ini"] == "20260901"
    assert um["data_fim"] == "20260930"


def test_filial_sem_aspas_e_recusada(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    pipelines_dir = tmp_path / "pipelines"
    scripts_dir.mkdir()
    pipelines_dir.mkdir()
    _script(scripts_dir, "base_a")
    _script(scripts_dir, "base_b")
    (pipelines_dir / "errado.yaml").write_text(
        """
id: errado
nome: Errado
empresa: Banco Senff
fontes:
  - script: base_a
    parametros:
      conta: 030101
  - script: base_b
    parametros:
      conta: "2"
conciliacao:
  esquerda: base_a
  direita: base_b
  operacao: soma
""",
        encoding="utf-8",
    )
    scripts = carregar_scripts(scripts_dir)
    with pytest.raises(ErroConciliacao, match="aspas"):
        carregar_pipelines(scripts, pipelines_dir)
