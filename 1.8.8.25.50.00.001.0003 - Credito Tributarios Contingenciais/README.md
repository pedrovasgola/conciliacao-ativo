# Crédito tributário

O robô lê o CT2010 e o CT do Sinqia e monta o Excel do mês.

```
rodar.bat
.venv\Scripts\python.exe -m conciliacao rodar credito_tributario --inicio 01/10/2026 --fim 31/10/2026
```

O Excel sai em `saida/`.
