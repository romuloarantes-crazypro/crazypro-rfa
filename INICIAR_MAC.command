#!/bin/bash
# ExifBoost Pro — Iniciar no Mac
# Duplo clique para abrir

# Vai para a pasta do script
cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   EXIFBOOST PRO — RFA Marketing Digital ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Verifica Python
if ! command -v python3 &>/dev/null; then
  echo "  [ERRO] Python 3 não encontrado."
  echo "  Instale em https://www.python.org/downloads/ e abra este arquivo de novo."
  open https://www.python.org/downloads/ 2>/dev/null
  read -p "  Pressione Enter para fechar..."
  exit 1
fi

# Ambiente próprio do app (.venv): evita conflito com o Python do sistema
PY=python3
if [ ! -x ".venv/bin/python" ]; then
  echo "  Preparando o ambiente (só na primeira vez, pode levar 1 minuto)..."
  python3 -m venv .venv 2>/dev/null
fi
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; fi

echo "  Verificando dependências..."
if ! "$PY" -m pip install -q --disable-pip-version-check -r requirements.txt; then
  echo ""
  echo "  [ERRO] Não foi possível instalar as dependências."
  echo "  Verifique a conexão com a internet e abra este arquivo de novo."
  read -p "  Pressione Enter para fechar..."
  exit 1
fi
echo "  OK"

# Puxa as últimas atualizações (só se esta pasta veio do Git)
echo "  Buscando atualizações..."
if [ -d .git ] && command -v git &>/dev/null; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  git pull --ff-only origin "$BRANCH" --quiet 2>/dev/null && echo "  OK" || echo "  (sem atualização — usando a versão local)"
else
  echo "  (instalação por ZIP — para atualizar, baixe o ZIP novo)"
fi

# Abre o navegador após 2 segundos
(sleep 2 && open http://127.0.0.1:8080) &

echo ""
echo "  App iniciando em: http://127.0.0.1:8080"
echo "  Para parar: feche esta janela ou pressione CTRL+C"
echo ""

# Inicia o app (acessível só neste computador; reinicia sozinho quando os arquivos mudam)
export PORT=8080
"$PY" -c "
import sys, os
sys.path.insert(0, os.getcwd())
from app import app
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=True)
"
