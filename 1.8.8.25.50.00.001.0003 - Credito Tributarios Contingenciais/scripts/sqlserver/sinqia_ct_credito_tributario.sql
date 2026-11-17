-- @id: sinqia_ct_credito_tributario
-- @engine: sqlserver
-- @param: data_ini tipo=inteiro
-- @param: data_fim tipo=inteiro
-- @param: instituicao tipo=inteiro
-- @param: agencia tipo=inteiro
-- @param: plano tipo=inteiro
-- @param: sinqia_irpj tipo=texto
-- @param: sinqia_csll tipo=texto

SELECT
    CAST(C.CT001_CT_CONTSM AS VARCHAR(20)) AS CONTA,
    CAST(C.CT001_CT_CONT AS VARCHAR(40)) AS COSIF,
    C.CT001_DS_NOMCT AS NOME,
    M.CT005_DT_MOVTO AS DATA,
    CAST(M.CT005_NR_LOTE AS VARCHAR(20)) AS LOTE,
    CAST(M.CT005_NR_DOCUMT AS VARCHAR(20)) AS DOC,
    M.CT005_TP_LOTE AS TP_LOTE,
    LTRIM(RTRIM(M.CT005_TP_MOVTO)) AS TIPO,
    M.CT005_VL_LANC AS VALOR_LANC,
    M.CT005_DS_HIST AS HIST
FROM SFINANCE_CT.dbo.CT005 M
INNER JOIN SFINANCE_CT.dbo.CT001 C
    ON M.CT005_SQ_CONTA = C.CT001_SQ_CONTA
WHERE M.CT005_NR_INST = :instituicao
  AND M.CT005_NR_AGEN = :agencia
  AND C.CT001_NR_PLANO = :plano
  AND M.CT005_DT_MOVTO BETWEEN :data_ini AND :data_fim
  AND M.CT005_NR_LOTE = 900
  AND (C.CT001_CT_CONTSM = :sinqia_irpj OR C.CT001_CT_CONTSM = :sinqia_csll)
  AND M.CT005_DS_HIST LIKE '%IMPLANTA%'
ORDER BY C.CT001_CT_CONTSM
