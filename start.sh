#!/bin/bash
set -e

MODE=${1:-dev}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config/config.json"

# 从配置文件读取端口（需要 python3）
read_config() {
    python3 -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg['$1']['$2'])"
}

BACKEND_PORT=$(read_config backend port)
BACKEND_HOST=$(read_config backend host)
FRONTEND_PORT=$(read_config frontend port)

if [ "$MODE" = "prod" ]; then
    echo "=== 构建前端 ==="
    cd "$SCRIPT_DIR/frontend" && npm run build

    echo "=== 启动后端（含前端静态文件，端口 $BACKEND_PORT） ==="
    fuser -k "$BACKEND_PORT/tcp" 2>/dev/null || true
    cd "$SCRIPT_DIR/backend"
    nohup uvicorn main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" > /tmp/gameplan.log 2>&1 &

    echo "=== 启动完成 ==="
    IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')
    echo "访问地址: http://${IP}:${BACKEND_PORT}"
else
    echo "=== 开发模式 ==="
    echo "终端1: cd backend && uvicorn main:app --reload --port $BACKEND_PORT"
    echo "终端2: cd frontend && npm run dev"
    echo ""
    echo "后端: http://localhost:$BACKEND_PORT"
    echo "前端: http://localhost:$FRONTEND_PORT"
fi
