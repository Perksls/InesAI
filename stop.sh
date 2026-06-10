#!/bin/bash
echo "🛑 A parar InesBot WebSocket..."

# Matar processos do backend
pkill -f "uvicorn main:app.*port 8001" 2>/dev/null

# Verificar se parou
sleep 2
if lsof -i :8001 > /dev/null 2>&1; then
    echo "💀 A matar processos pendentes..."
    kill -9 $(lsof -t -i :8001) 2>/dev/null
fi

echo "✅ InesBot parado!"
