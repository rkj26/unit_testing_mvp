# CLAUDE.md

All guidance for this repo lives in **[AGENTS.md](./AGENTS.md)**. Read it before making changes.
Folders that add rules of their own carry their own `AGENTS.md`; the nearest one wins.

This file exists because Claude Code auto-loads `CLAUDE.md` by name and will not find `AGENTS.md`
on its own. Keep the content in `AGENTS.md` — one source, not two that drift.

Shortest version: run `.venv/bin/python -m pytest -q` before claiming a change works, and remember that a
protocol run spends money while every notebook cell only reads what it wrote.
