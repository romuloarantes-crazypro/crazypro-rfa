#!/bin/bash
# CrazyPro RFA — Iniciar no Mac
# Duplo clique para abrir

# Vai para a pasta do script
cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   CRAZYPRO RFA — RFA Marketing Digital  ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Verifica Python
if ! command -v python3 &>/dev/null; then
  echo "  [ERRO] Python3 não encontrado."
  echo "  Instale via: brew install python"
  read -p "  Pressione Enter para fechar..."
  exit 1
fi

# Instala dependências se necessário (silencioso)
echo "  Verificando dependências..."
pip3 install flask pillow piexif requests openpyxl werkzeug -q 2>/dev/null
echo "  OK"

# Puxa últimas atualizações
echo "  Buscando atualizações..."
git pull origin claude/wizardly-carson-8C55J --quiet 2>/dev/null && echo "  OK" || echo "  (sem conexão — usando versão local)"

# Abre o navegador após 2 segundos
(sleep 2 && open http://127.0.0.1:8080) &

echo ""
echo "  App iniciando em: http://127.0.0.1:8080"
echo "  Auto-reload ativado — mudanças aplicadas automaticamente."
echo "  Para parar: feche esta janela ou pressione CTRL+C"
echo ""

# Inicia Flask com auto-reload
export PORT=8080
export FLASK_ENV=development
python3 -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath('app.py')))
from app import app
app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=True)
"
