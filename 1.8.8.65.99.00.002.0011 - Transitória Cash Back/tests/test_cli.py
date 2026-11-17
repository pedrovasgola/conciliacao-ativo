from datetime import date

from conciliacao.catalogo import carregar_pipelines, carregar_scripts
from conciliacao.cli import _destino, _parser, main


def test_listar_mostra_scripts_e_pipeline(capsys):
    try:
        main(["listar"])
    except SystemExit as exc:
        assert exc.code == 0
    texto = capsys.readouterr().out
    assert "protheus_ct2_razao" in texto
    assert "sinqia_ct_razao" in texto
    assert "sinqia_ct_balancete" in texto
    assert "sinqia_cc_razao" in texto
    assert "teddoc_outras_instituicoes" in texto
    assert "pronto" in texto
    assert "falta colar o SELECT" in texto


def test_rodar_aceita_conta_ct2():
    args = _parser().parse_args(
        [
            "rodar",
            "teddoc_outras_instituicoes",
            "--inicio",
            "01/09/2026",
            "--fim",
            "30/09/2026",
            "--conta",
            "11020202044",
        ]
    )
    assert args.conta == "11020202044"


def test_rodar_aceita_conta_sinqia():
    args = _parser().parse_args(
        [
            "rodar",
            "teddoc_outras_instituicoes",
            "--inicio",
            "01/09/2026",
            "--fim",
            "30/09/2026",
            "--conta",
            "11030101063",
            "--conta-sinqia",
            "1886599000020011",
        ]
    )
    assert args.conta == "11030101063"
    assert args.conta_sinqia == "1886599000020011"


def test_nome_do_arquivo_e_conta_nome_e_anomes(monkeypatch, tmp_path):
    pasta = tmp_path / "1.8.8.65.99.00.002.0002 - Transações Pix Outras Instituições" / "conciliacao"
    pasta.mkdir(parents=True)
    monkeypatch.setenv("CONCILIACAO_RAIZ", str(pasta))
    pipeline = carregar_pipelines(carregar_scripts())["teddoc_outras_instituicoes"]
    destino = _destino(pipeline, date(2026, 9, 1), date(2026, 9, 30), None)
    assert destino.name == (
        "1.8.8.65.99.00.002.0002 - Transações Pix Outras Instituições - 09.2026.xlsx"
    )
    assert destino.parent == pasta / "saida"
