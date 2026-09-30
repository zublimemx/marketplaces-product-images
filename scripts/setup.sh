#!/usr/bin/env bash
# Prepara el entorno (Codex cloud, Claude Code o local): dependencias y carpetas locales ignoradas por git.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -r requirements.txt 2>/dev/null || python3 -m pip install --break-system-packages -r requirements.txt
mkdir -p insumos trabajo
[ -f .env ] || cp .env.example .env
python3 scripts/validar.py
