#!/bin/bash
# Schritt 1: Keys rotieren (VORHER!)
#   https://build.nvidia.com/ → neuer API Key
#   https://www.heypiggy.com → neues Passwort
# Schritt 2: .env mit NEUEN Keys befüllen
# Schritt 3: Dieses Script ausführen
set -euo pipefail
cd /tmp
rm -rf a2a-mirror a2a-clean
git clone --mirror https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy a2a-mirror
cd a2a-mirror
bfg --delete-files .env --no-blob-protection
cd /tmp
git clone a2a-mirror a2a-clean
cd a2a-clean
git remote set-url origin git@github.com:OpenSIN-AI/A2A-SIN-Worker-heypiggy.git
git push --force origin main
echo "DONE. cd ~/dev/A2A-SIN-Worker-heypiggy && git pull origin main"
