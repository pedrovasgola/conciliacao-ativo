-- @id: protheus_se5_se1_consignado
-- @engine: oracle
-- @descricao: Baixas SE5010 com SE1010 do Consignado a Receber
-- @param: data_ini tipo=texto tamanho=8
-- @param: data_fim tipo=texto tamanho=8
-- @param: filial tipo=texto tamanho=6

-- Natureza 1010079. Sem baixa ENF. O sinal da grade é aplicado no Python.

SELECT
    E5.E5_DATA,
    E5.E5_VALOR,
    E5.E5_NATUREZ,
    E5.E5_VENCTO,
    E5.E5_DOCUMEN,
    E5.E5_BENEF,
    E5.E5_NUMERO,
    E5.E5_TIPO,
    E5.E5_MOTBX,
    E1.E1_TIPO,
    E1.E1_CLIENTE,
    E1.E1_NOMCLI,
    E1.E1_HIST,
    E1.E1_BAIXA
FROM SE5010 E5
JOIN SE1010 E1
    ON E1.E1_FILIAL = E5.E5_FILIAL
   AND E1.E1_PREFIXO = E5.E5_PREFIXO
   AND E1.E1_NUM = E5.E5_NUMERO
   AND E1.E1_PARCELA = E5.E5_PARCELA
   AND E1.E1_TIPO = E5.E5_TIPO
   AND E1.D_E_L_E_T_ = ' '
WHERE E5.D_E_L_E_T_ = ' '
  AND E5.E5_FILIAL = :filial
  AND TRIM(E5.E5_NATUREZ) = '1010079'
  AND E5.E5_DATA BETWEEN :data_ini AND :data_fim
  AND NVL(TRIM(E5.E5_MOTBX), ' ') <> 'ENF'
ORDER BY E5.E5_DATA, E5.E5_NUMERO, E5.E5_TIPO
