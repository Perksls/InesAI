#!/bin/bash
# Diagnostico InesBot WebSocket

echo "🔍 Diagnostico InesBot WebSocket"
echo "================================"
echo ""

# 1. Verificar se backend esta a correr
echo "1. Backend (porta 8001):"
if curl -s http://localhost:8001/ > /dev/null 2>&1; then
    echo "   ✅ Backend a correr na porta 8001"
    curl -s http://localhost:8001/ | head -c 200
    echo ""
else
    echo "   ❌ Backend NAO esta a correr na porta 8001"
    echo "   Logs do backend:"
    tail -n 10 ~/openrouterws/logs/backend.log 2>/dev/null || echo "   (sem logs)"
fi
echo ""

# 2. Verificar Nginx
echo "2. Nginx:"
if systemctl is-active nginx > /dev/null 2>&1; then
    echo "   ✅ Nginx ativo"
else
    echo "   ❌ Nginx PARADO"
    echo "   Iniciar: sudo systemctl start nginx"
fi
echo ""

# 3. Verificar ports
echo "3. Ports em uso:"
sudo lsof -i :8001 2>/dev/null | grep -v COMMAND | head -3 || echo "   Porta 8001: nada"
sudo lsof -i :80 2>/dev/null | grep -v COMMAND | head -3 || echo "   Porta 80: nada"
echo ""

# 4. Verificar frontend
echo "4. Frontend files:"
ls -la ~/openrouterws/frontend/ 2>/dev/null || echo "   ❌ Diretorio frontend nao encontrado"
echo ""

# 5. Verificar Nginx config
echo "5. Nginx config:"
ls -la /etc/nginx/sites-enabled/ 2>/dev/null
echo ""

# 6. Resumo
echo "6. Resumo:"
echo "   Backend:  http://localhost:8001"
echo "   Frontend: http://localhost (via Nginx)"
echo "   WebSocket: ws://localhost:8001/ws"
echo ""
echo "🔧 Se o backend nao esta a correr:"
echo "   cd ~/openrouterws && ./start.sh"
echo ""
echo "🔧 Se o Nginx nao esta a correr:"
echo "   sudo systemctl start nginx"
echo ""
echo "🔧 Para ver logs:"
echo "   tail -f ~/openrouterws/logs/backend.log"
echo "   sudo journalctl -u nginx -f"
