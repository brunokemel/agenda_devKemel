#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install --break-system-packages -r requirements.txt
python3 -m PyInstaller --noconfirm --clean agenda.spec

echo
echo "Executavel gerado em: dist/AgendaOneNote"
echo "No Windows, execute o mesmo comando apos instalar Python:"
echo "  pip install -r requirements.txt"
echo "  pyinstaller --noconfirm agenda.spec"
