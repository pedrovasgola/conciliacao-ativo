-- @id: protheus_ct2_credito_tributario
-- @engine: oracle
-- @param: data_ini tipo=texto tamanho=8
-- @param: data_fim tipo=texto tamanho=8
-- @param: filial tipo=texto tamanho=6
-- @param: conta tipo=texto tamanho=20
-- @param: contra_irpj tipo=texto tamanho=20
-- @param: contra_csll tipo=texto tamanho=20

SELECT
    CT2_FILIAL,
    TRUNC(TO_DATE(NULLIF(TRIM(CT2_DATA), ''), 'YYYYMMDD')) AS CT2_DATA,
    CT2_LOTE,
    CT2_DOC,
    CT2_DEBITO,
    CT2_CREDIT,
    CT2_VALOR,
    CT2_HIST
FROM CT2010
WHERE CT2_FILIAL = :filial
  AND CT2_DATA BETWEEN :data_ini AND :data_fim
  AND D_E_L_E_T_ = ' '
  AND CT2_DEBITO = :conta
  AND (CT2_CREDIT = :contra_irpj OR CT2_CREDIT = :contra_csll)
  AND TRIM(CT2_LOTE) = 'M00001'
  AND TRIM(CT2_DOC) = '000005'
ORDER BY CT2_DATA, CT2_CREDIT
