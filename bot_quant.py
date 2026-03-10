name: Bot Quantitativo Diario

on:
  schedule:
    # Roda de hora em hora das 6h às 22h (BRT)
    # Equivalente a: 9h às 23h e 0h a 1h em UTC
    - cron: '0 0-1,9-23 * * *'
  workflow_dispatch: # Adiciona um botão no GitHub para você poder rodar manualmente quando quiser

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout do codigo
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Instalar Dependencias
        run: |
          pip install requests pandas

      - name: Rodar o Bot
        run: python bot_quant.py
