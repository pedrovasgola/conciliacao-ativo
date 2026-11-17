-- @id: sinqia_cc_razao
-- @engine: sqlserver
-- @descricao: Movimento de conta corrente na Sinqia
-- @param: data_ini tipo=inteiro
-- @param: data_fim tipo=inteiro
-- @param: conta tipo=texto
-- @param: instituicao tipo=inteiro
-- @coluna.data: DATA
-- @coluna.valor: VALOR

-- Cole aqui o SELECT que hoje alimenta a WP-04 (razão de conta corrente).
-- Esta conciliação usa o resultado só para explicar os dias que não fecharam.
-- Outra conciliação pode apontar este mesmo arquivo como lado da conta.
--
-- Colunas que o motor lê:
--   DATA   data do movimento
--   VALOR  débito menos crédito
-- As demais colunas aparecem na aba, sem entrar na fórmula.
--
-- Exemplo do formato (troque tabelas e filtros pelos da sua consulta):
--
-- SELECT
--     CC.CONTA_CONTABIL,
--     CC.DATA_MOVTO AS DATA,
--     CC.CONTRAPARTIDA,
--     CC.COD_PRODUTO,
--     CC.DESCRICAO_PRODUTO,
--     CC.COD_TRANSACAO,
--     CC.TRANSACAO,
--     CC.CONTA_CORRENTE,
--     CC.SEQUENCIA,
--     CC.DEBITO,
--     CC.CREDITO,
--     CC.DEBITO - CC.CREDITO AS VALOR,
--     CC.CC01_NR_CLIC
-- FROM <banco>.dbo.<tabela_cc> CC
-- WHERE CC.DATA_MOVTO BETWEEN :data_ini AND :data_fim
--   AND CC.CONTA_CONTABIL = :conta

SELECT
    CAST(NULL AS date) AS DATA,
    CAST(NULL AS decimal(18, 2)) AS VALOR
WHERE PREENCHER_ORIGEM = 1
