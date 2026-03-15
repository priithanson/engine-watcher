name: Engine Watcher

on:
  workflow_dispatch:
  schedule:
    - cron: '0 8,20 * * *'

jobs:
  check-engines:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install playwright
          playwright install --with-deps chromium

      - name: Run watcher
        run: python watcher.py
