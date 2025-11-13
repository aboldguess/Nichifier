#!/usr/bin/env bash
# scripts/setup_environment.sh
# =============================
# Mini-README: Automates creation of a Python virtual environment, upgrades pip, and
# installs Nichifier dependencies on Unix-like systems.

set -euo pipefail

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

cat <<'EOF'
Environment ready. Activate with 'source .venv/bin/activate' then run:
  python nichifier_platform_server.py --init-db
  python nichifier_platform_server.py --promote-user you@example.com --role admin
  python nichifier_platform_server.py --reload
EOF
