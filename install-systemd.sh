#!/bin/bash
echo "⚙️  A instalar servico systemd..."

# Copiar servico
sudo cp inesbot-ws.service /etc/systemd/system/

# Recarregar daemon
sudo systemctl daemon-reload

# Ativar auto-start
sudo systemctl enable inesbot-ws

# Iniciar
sudo systemctl start inesbot-ws

echo "✅ Servico instalado!"
echo ""
echo "📋 Comandos uteis:"
echo "   sudo systemctl status inesbot-ws"
echo "   sudo systemctl start inesbot-ws"
echo "   sudo systemctl stop inesbot-ws"
echo "   sudo journalctl -u inesbot-ws -f"
