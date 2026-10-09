#!/bin/bash
# CrazyPro RFA — Atualizar para última versão
# Duplo clique para atualizar (o app reinicia sozinho)

cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   CRAZYPRO RFA — Atualizar              ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  Baixando atualizações do GitHub..."
echo ""

git pull origin claude/wizardly-carson-8C55J

echo ""
echo "  ✅ Atualização concluída!"
echo "  O app reinicia automaticamente em 2-3 segundos."
echo "  Dê um CMD+R no navegador para ver as novidades."
echo ""
read -p "  Pressione Enter para fechar esta janela..."
