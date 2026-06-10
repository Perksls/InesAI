#!/bin/bash
echo "⚙️  A instalar configuracao Nginx..."

# Copiar configuracao
sudo cp nginx-inesbot-ws.conf /etc/nginx/sites-available/inesbot-ws

# Criar symlink (remover antigo se existir)
if [ -L /etc/nginx/sites-enabled/inesbot-ws ]; then
    echo "🗑️  A remover link antigo..."
    sudo rm /etc/nginx/sites-enabled/inesbot-ws
fi
if [ -L /etc/nginx/sites-enabled/inesbot-ws.conf ]; then
    sudo rm /etc/nginx/sites-enabled/inesbot-ws.conf
fi

sudo ln -s /etc/nginx/sites-available/inesbot-ws /etc/nginx/sites-enabled/inesbot-ws

# Verificar configuracao
echo "🔍 A verificar configuracao..."
if sudo nginx -t; then
    echo "✅ Configuracao valida!"
    echo "🔄 A recarregar Nginx..."
    sudo systemctl reload nginx || sudo systemctl restart nginx
    echo "✅ Nginx recarregado!"
    echo ""
    echo "🌐 InesBot WebSocket disponivel em:"
    echo "   http://localhost/"
    echo "   ws://localhost/ws"
else
    echo "❌ Erro na configuracao! Verifica os logs acima."
    exit 1
fi
