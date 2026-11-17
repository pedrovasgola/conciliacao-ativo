"""Encontro por órgão e classe. Os pares se anulam no mesmo órgão."""

from __future__ import annotations

from collections import Counter, defaultdict

import pandas as pd

from conciliacao.regras import (
    BAIXA_EMPREGADOR,
    BAIXA_ITAU,
    CLASSES,
    ESTORNO_EMPREGADOR,
    ESTORNO_ITAU,
    ESTORNO_OP,
    LIB,
    REFIN,
    centavos,
    norm,
    zerou,
)

FAMILIA_ITAU = (BAIXA_ITAU, ESTORNO_ITAU, ESTORNO_OP)
FAMILIA_EMP = (BAIXA_EMPREGADOR, ESTORNO_EMPREGADOR)
FAMILIA_REFIN = (LIB, REFIN)


def _chave_orgao(nome: str) -> str:
    return norm(nome).casefold()


def _somar(quadro: pd.DataFrame) -> tuple[dict, dict[str, str]]:
    totais: dict[tuple[str, str], float] = defaultdict(float)
    nomes: dict[str, str] = {}
    if quadro is None or quadro.empty:
        return totais, nomes
    for _, row in quadro.iterrows():
        chave = _chave_orgao(row["ORGAO"])
        if not chave:
            chave = "(sem órgão)"
        classe = norm(row["CLASSE"])
        totais[(chave, classe)] = centavos(totais[(chave, classe)] + centavos(row["VALOR"]))
        nomes.setdefault(chave, norm(row["ORGAO"]) or "(sem órgão)")
    return totais, nomes


def _anular(valores: dict[str, float], baixa: str, estornos: tuple[str, ...]) -> dict[str, float]:
    """Consome baixa contra estorno, no mesmo órgão. Não casa baixa com baixa."""
    resto = {classe: centavos(valores.get(classe, 0.0)) for classe in (baixa, *estornos)}
    for estorno in estornos:
        a, b = resto[baixa], resto[estorno]
        if a == 0 or b == 0 or a * b > 0:
            continue
        miolo = centavos(min(abs(a), abs(b)))
        if a > 0:
            resto[baixa], resto[estorno] = centavos(a - miolo), centavos(b + miolo)
        else:
            resto[baixa], resto[estorno] = centavos(a + miolo), centavos(b - miolo)
    return resto


def cruzar(funcao: pd.DataFrame, sql: pd.DataFrame) -> pd.DataFrame:
    fsum, fnomes = _somar(funcao)
    ssum, snomes = _somar(sql)
    nomes = {**snomes, **fnomes}
    classes = [classe for classe in CLASSES if any(chave[1] == classe for chave in (*fsum, *ssum))]
    for extra in sorted({chave[1] for chave in (*fsum, *ssum)} - set(classes)):
        classes.append(extra)
    orgaos = sorted(nomes, key=lambda chave: nomes[chave].casefold())

    status: dict[tuple[str, str, str], str] = {}
    obs: dict[tuple[str, str, str], str] = {}

    def marcar(base: str, orgao: str, classe: str, nome: str, nota: str) -> None:
        status[(base, orgao, classe)] = nome
        if nota:
            obs[(base, orgao, classe)] = nota

    def valor(base: str, orgao: str, classe: str) -> float:
        origem = fsum if base == "FIN-FUNCAO" else ssum
        return centavos(origem.get((orgao, classe), 0.0))

    for orgao in orgaos:
        for classe in classes:
            if classe in FAMILIA_ITAU or classe in FAMILIA_EMP or classe in FAMILIA_REFIN:
                continue
            fv, sv = valor("FIN-FUNCAO", orgao, classe), valor("se5-se1", orgao, classe)
            if zerou(fv) and zerou(sv):
                continue
            if zerou(centavos(fv + sv)):
                if not zerou(fv):
                    marcar("FIN-FUNCAO", orgao, classe, "Conciliado", "Mesma classe nos dois lados")
                if not zerou(sv):
                    marcar("se5-se1", orgao, classe, "Conciliado", "Mesma classe nos dois lados")

    def fechar_par(baixa: str, estornos: tuple[str, ...], frase: str, so_se_zerar: bool = False) -> None:
        for orgao in orgaos:
            brutos = {}
            for classe in (baixa, *estornos):
                brutos[("FIN-FUNCAO", classe)] = valor("FIN-FUNCAO", orgao, classe)
                brutos[("se5-se1", classe)] = valor("se5-se1", orgao, classe)
            if all(zerou(item) for item in brutos.values()):
                continue
            if zerou(centavos(sum(brutos.values()))):
                for (base, classe), item in brutos.items():
                    if not zerou(item):
                        marcar(base, orgao, classe, "Conciliado", frase)
                continue
            if so_se_zerar:
                continue
            lado_f = {classe: brutos[("FIN-FUNCAO", classe)] for classe in (baixa, *estornos)}
            lado_s = {classe: brutos[("se5-se1", classe)] for classe in (baixa, *estornos)}
            resto_f = _anular(lado_f, baixa, estornos)
            resto_s = _anular(lado_s, baixa, estornos)
            baixa_fecha = zerou(centavos(resto_f[baixa] + resto_s[baixa]))
            for classe in estornos:
                for base, bruto, resto in (
                    ("FIN-FUNCAO", lado_f[classe], resto_f[classe]),
                    ("se5-se1", lado_s[classe], resto_s[classe]),
                ):
                    if zerou(bruto) or not zerou(resto):
                        continue
                    marcar(base, orgao, classe, "Conciliado", frase)
            for base, bruto, resto in (
                ("FIN-FUNCAO", lado_f[baixa], resto_f[baixa]),
                ("se5-se1", lado_s[baixa], resto_s[baixa]),
            ):
                if zerou(bruto):
                    continue
                if baixa_fecha:
                    marcar(base, orgao, baixa, "Conciliado", frase)
                    continue
                comido = centavos(abs(bruto) - abs(resto))
                if not zerou(comido):
                    marcar(
                        base,
                        orgao,
                        baixa,
                        "Em branco",
                        f"Anulou {comido:.2f} com o par do mesmo órgão; sobrou {resto:.2f}",
                    )

    fechar_par(BAIXA_ITAU, (ESTORNO_ITAU, ESTORNO_OP), "Baixa e estorno do Itaú do mesmo órgão se anularam")
    fechar_par(BAIXA_EMPREGADOR, (ESTORNO_EMPREGADOR,), "Baixa e estorno do empregador do mesmo órgão se anularam")
    fechar_par(LIB, (REFIN,), "Liberação e refinanciamento do mesmo órgão zeraram", so_se_zerar=True)

    for orgao in orgaos:
        for classe in classes:
            for base in ("FIN-FUNCAO", "se5-se1"):
                chave = (base, orgao, classe)
                if chave in status:
                    continue
                item = valor(base, orgao, classe)
                if zerou(item):
                    marcar(base, orgao, classe, "Zerado", "")
                else:
                    marcar(base, orgao, classe, "Em branco", "Tem valor e não achou par neste órgão")

    linhas = []
    for orgao in orgaos:
        for classe in classes:
            for base in ("se5-se1", "FIN-FUNCAO"):
                item = valor(base, orgao, classe)
                linhas.append(
                    {
                        "Base": base,
                        "Órgão": nomes[orgao],
                        "Classe": classe,
                        "Valor": item,
                        "Classificação": status[(base, orgao, classe)],
                        "Observação": obs.get((base, orgao, classe), ""),
                    }
                )
    return pd.DataFrame(linhas)


def resumo(grade: pd.DataFrame) -> pd.DataFrame:
    grupos = (
        grade.groupby(["Base", "Classe", "Classificação"], dropna=False)["Valor"]
        .agg(Orgaos="size", Valor="sum")
        .reset_index()
    )
    grupos["Valor"] = grupos["Valor"].map(centavos)
    ordem = {classe: indice for indice, classe in enumerate(CLASSES)}
    grupos["_o"] = grupos["Classe"].map(lambda classe: ordem.get(classe, 99))
    return grupos.sort_values(["_o", "Base", "Classificação"]).drop(columns="_o")


def contagem(grade: pd.DataFrame) -> Counter:
    return Counter(grade["Classificação"])
