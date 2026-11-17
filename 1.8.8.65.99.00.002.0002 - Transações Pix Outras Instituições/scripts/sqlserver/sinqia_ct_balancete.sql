-- @id: sinqia_ct_balancete
-- @engine: sqlserver
-- @descricao: Saldo anterior da conta na Sinqia
-- @param: data_ini tipo=inteiro
-- @param: data_fim tipo=inteiro
-- @param: conta tipo=texto
-- @param: instituicao tipo=inteiro
-- @param: agencia tipo=inteiro
-- @param: plano tipo=inteiro
-- @coluna.valor: SALDO_ATUAL

-- Balancete de uma conta. Saldo anterior = débito − crédito antes da data inicial.
-- No mês cheio (dia 01 ao último dia) é o mesmo saldo do balancete por AM_MOVTO.
-- Conta analítica: só o lançamento dela. Conta sintética: soma os filhos.

WITH alvo AS (
    SELECT c.CT001_SQ_CONTA AS sq_conta
    FROM SFINANCE_CT.dbo.CT001 AS c
    WHERE c.CT001_NR_PLANO = :plano
      AND c.CT001_CT_CONTSM = :conta
),
arvore AS (
    SELECT a.sq_conta, 0 AS profundidade
    FROM alvo AS a

    UNION ALL

    SELECT
        f.CT001_SQ_CONTA,
        p.profundidade + 1
    FROM arvore AS p
    INNER JOIN SFINANCE_CT.dbo.CT001 AS f
        ON f.CT001_SQ_CNTSUP = p.sq_conta
       AND f.CT001_NR_PLANO = :plano
    WHERE f.CT001_SQ_CNTSUP IS NOT NULL
      AND f.CT001_SQ_CNTSUP <> 0
      AND f.CT001_SQ_CONTA <> p.sq_conta
      AND p.profundidade < 32
),
movimento AS (
    SELECT
        SUM(
            CASE
                WHEN l.CT005_DT_MOVTO < :data_ini AND LTRIM(RTRIM(l.CT005_TP_MOVTO)) = 'D' THEN l.CT005_VL_LANC
                WHEN l.CT005_DT_MOVTO < :data_ini AND LTRIM(RTRIM(l.CT005_TP_MOVTO)) = 'C' THEN -l.CT005_VL_LANC
                ELSE 0
            END
        ) AS saldo_anterior,
        SUM(
            CASE
                WHEN l.CT005_DT_MOVTO >= :data_ini AND LTRIM(RTRIM(l.CT005_TP_MOVTO)) = 'D' THEN l.CT005_VL_LANC
                ELSE 0
            END
        ) AS debito,
        SUM(
            CASE
                WHEN l.CT005_DT_MOVTO >= :data_ini AND LTRIM(RTRIM(l.CT005_TP_MOVTO)) = 'C' THEN l.CT005_VL_LANC
                ELSE 0
            END
        ) AS credito
    FROM SFINANCE_CT.dbo.CT005 AS l WITH (NOLOCK)
    INNER JOIN arvore AS a
        ON a.sq_conta = l.CT005_SQ_CONTA
    WHERE l.CT005_NR_INST = :instituicao
      AND l.CT005_NR_AGEN = :agencia
      AND l.CT005_DT_MOVTO <= :data_fim
)
SELECT
    c.CT001_CT_CONTSM AS CONTA,
    c.CT001_DS_NOMCT AS NOME,
    c.CT001_GR_CONT AS GRAU,
    CASE c.CT001_ID_ANLSIN
        WHEN 10 THEN 'sintetica'
        WHEN 0 THEN 'analitica'
        WHEN 20 THEN 'analitica'
        ELSE CONVERT(varchar(20), c.CT001_ID_ANLSIN)
    END AS TIPO,
    CAST(ISNULL(m.saldo_anterior, 0) AS decimal(24, 2)) AS SALDO_ANTERIOR,
    CAST(ISNULL(m.debito, 0) AS decimal(24, 2)) AS DEBITO,
    CAST(ISNULL(m.credito, 0) AS decimal(24, 2)) AS CREDITO,
    CAST(ISNULL(m.debito, 0) - ISNULL(m.credito, 0) AS decimal(24, 2)) AS MOVIMENTO,
    CAST(ISNULL(m.saldo_anterior, 0) + ISNULL(m.debito, 0) - ISNULL(m.credito, 0) AS decimal(24, 2)) AS SALDO_ATUAL
FROM alvo
INNER JOIN SFINANCE_CT.dbo.CT001 AS c
    ON c.CT001_SQ_CONTA = alvo.sq_conta
   AND c.CT001_NR_PLANO = :plano
CROSS JOIN movimento AS m
OPTION (MAXRECURSION 32)
