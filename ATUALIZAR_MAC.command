#!/bin/bash
# ExifBoost Pro — Atualizar para última versão
# Duplo clique para atualizar (o app reinicia sozinho)

cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   EXIFBOOST PRO — Atualizar             ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

if [ ! -d .git ]; then
  echo "  Esta cópia foi instalada por ZIP e não se atualiza sozinha."
  echo "  Baixe o ZIP novo em:"
  echo "  https://github.com/romuloarantes-crazypro/crazypro-rfa/archive/refs/heads/main.zip"
  echo "  e substitua a pasta. Seus modelos salvos não se perdem: ficam fora desta pasta."
  echo ""
  read -p "  Pressione Enter para fechar esta janela..."
  exit 0
fi

echo "  Baixando atualizações do GitHub..."
echo ""

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if git pull --ff-only origin "$BRANCH"; then
  echo ""
  echo "  ✅ Atualização concluída!"
  echo "  O app reinicia automaticamente em 2-3 segundos."
  echo "  Dê um CMD+R no navegador para ver as novidades."
else
  echo ""
  echo "  ⚠️  Não foi possível atualizar. Leia a mensagem acima."
  echo "  Se aparecer 'local changes', me mande o texto para eu ajudar."
fi
echo ""
read -p "  Pressione Enter para fechar esta janela..."
