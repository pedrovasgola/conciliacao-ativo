# Conciliação — Consignado a Receber

O robô lê a Movimentação Financeira do Função e o SE5010 com SE1010, e monta o Excel do mês. A conta não muda: no mês só mudam as datas e o arquivo do Função.

```
scripts/      SE5010 com SE1010
pipelines/    filial, natureza e a diferença de referência
entrada/      Excel da Movimentação Financeira do Função
saida/        Excel gerado
.env          usuário e senha do Oracle (não entra no git)
```

As dez classes são as da coluna MOVIMENTO. Não se agrupam. Códigos 004, 099, 100, 101, 102, 103, 108, 110, 400, 401 e 405. Os códigos 004, 400 e 401 entram negativos.

A classe da SE5 é o MOVIMENTO do título quando `E5_NUMERO` existe na coluna Titulo da movimentação. Sem esse título, REP fica Baixa Empregador e OP fica Estorno Itaú/baixa boleto itau. BANCO SENFF no beneficiário fica nessa classe de estorno. O valor da SE5 entra com o sinal trocado.

O encontro é por órgão e classe. Baixa Boleto Itaú anula Estorno Baixa Boleto Itaú no mesmo órgão. Baixa Empregador anula Estorno Baixa Empregador no mesmo órgão. Lib. Créd p/ Quit. Refin anula Refinanciamento e o par zera.

## Preparar

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env
```

Preencha o `.env`. O usuário do banco precisa ter apenas SELECT.

O Excel do Função entra em `entrada/`, com o mês no nome (`movimentacao-financeira-2026-10.xlsx`), ou no argumento `--funcao`.

## Rodar

```
rodar.bat
.venv\Scripts\python.exe -m conciliacao rodar consignado_a_receber --inicio 01/10/2026 --fim 31/10/2026
```

O Excel sai em `saida/`.
