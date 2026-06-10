#!/bin/bash
echo "🚀 A iniciar InesBot WebSocket..."

# Verificar se estamos no diretorio correto
if [ ! -f "backend/main.py" ]; then
    echo "❌ Erro: Nao encontrado backend/main.py"
    echo "   Certifica-te que estas em ~/openrouterws"
    exit 1
fi

# Criar diretorios necessarios
mkdir -p data logs

# Ativar venv
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "⚠️  Virtual environment nao encontrado. A criar..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Verificar se backend ja esta a correr
if lsof -i :8001 > /dev/null 2>&1; then
    echo "⚠️  Backend ja esta a correr na porta 8001"
    echo "   Executa ./stop.sh primeiro"
    exit 1
fi

# Iniciar backend
echo "🤖 A iniciar backend na porta 8001..."
cd backend
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Esperar e verificar
echo "⏳ A verificar se arrancou..."
sleep 3

if curl -s http://localhost:8001/ > /dev/null 2>&1; then
    echo "✅ Backend arrancou com sucesso!"
    echo "   PID: $BACKEND_PID"
    echo "   URL: http://localhost:8001"
    echo "   WebSocket: ws://localhost:8001/ws"
    echo ""
    echo "📋 Para ver logs:"
    echo "   tail -f logs/backend.log"
    echo ""
    echo "🌐 Acede via Nginx: http://localhost/"
else
    echo "❌ Backend nao arrancou. Verifica logs:"
    echo "   tail -n 20 logs/backend.log"
    exit 1
fi
