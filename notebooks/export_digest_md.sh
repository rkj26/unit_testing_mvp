#!/usr/bin/env bash
# Render the executed digest as Markdown for reading on GitHub: no code, no printed logs, figures and
# tables kept. Run from the repo root after executing notebooks/results_full_digest.ipynb.
set -euo pipefail
cd "$(dirname "$0")/.."

tmp=$(mktemp -d)
# Printed lines are setup logs; the figures, tables and the findings text are display outputs.
jq '.cells |= map(if .cell_type == "code" then .outputs |= map(select(.output_type != "stream")) else . end)' \
  notebooks/results_full_digest.ipynb > "$tmp/digest.ipynb"
.venv/bin/python -m jupyter nbconvert --to markdown --no-input "$tmp/digest.ipynb" \
  --output-dir notebooks --output results_full_digest
rm -rf "$tmp"

# The "Setup" section describes code cells this rendering does not have, and pandas' <style> block
# is noise outside Jupyter.
awk '/^## Setup/{skip=1; next} /^## /{skip=0} /<style scoped>/{style=1} !skip && !style{print} /<\/style>/{style=0}' \
  notebooks/results_full_digest.md > "notebooks/results_full_digest.md.tmp"
sed "s/ The code cells are collapsed\.//" notebooks/results_full_digest.md.tmp > notebooks/results_full_digest.md  # no cells here
rm notebooks/results_full_digest.md.tmp
echo "wrote notebooks/results_full_digest.md"
