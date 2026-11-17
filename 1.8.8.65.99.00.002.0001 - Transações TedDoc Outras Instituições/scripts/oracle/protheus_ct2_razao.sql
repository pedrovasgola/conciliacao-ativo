-- @id: protheus_ct2_razao
-- @engine: oracle
-- @descricao: Razão CT2 do Protheus para a conta informada
-- @param: data_ini tipo=texto tamanho=8
-- @param: data_fim tipo=texto tamanho=8
-- @param: filial tipo=texto tamanho=6
-- @param: conta tipo=texto tamanho=20
-- @coluna.data: CT2_DATA
-- @coluna.valor: VALOR_SINAL

-- Razão da conta: toda linha em que a conta está no débito ou no crédito.
-- Sem filtro de contrapartida. VALOR_SINAL fica negativo quando a conta está no crédito.
-- Compara no tamanho do CHAR (conta 20, filial 6, data 8). Sem RTRIM na coluna, o índice vale.

SELECT
    CT2_FILIAL,
    TRUNC(TO_DATE(NULLIF(TRIM(CT2_DATA), ''), 'YYYYMMDD')) AS CT2_DATA,
    CT2_LOTE,
    CT2_DEBITO,
    CT2_CREDIT,
    CT2_VALOR,
    CT2_HIST,
    CT2_YDESDB,
    CT2_YDESCR,
    CT2_AT02DB AS CPF,
    CASE
        WHEN CT2_CREDIT = :conta THEN CT2_VALOR * -1
        ELSE CT2_VALOR
    END AS VALOR_SINAL
FROM CT2010
WHERE (CT2_DEBITO = :conta OR CT2_CREDIT = :conta)
  AND CT2_FILIAL = :filial
  AND CT2_DATA BETWEEN :data_ini AND :data_fim
  AND D_E_L_E_T_ = ' '
ORDER BY CT2_DATA, CT2_LOTE, CT2_DOC, CT2_LINHA, CT2_AT02DB
