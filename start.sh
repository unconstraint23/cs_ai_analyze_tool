#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export PATH="/Users/jr_zhang/.nvm/versions/node/v22.22.0/bin:/opt/homebrew/bin:$PATH"

if [ ! -d "frontend/dist" ]; then
  echo "📦 正在构建 React + TS + shadcn/ui 前端产物..."
  pnpm --dir frontend build
fi

echo "🚀 启动 CS2 完美平台战术习惯 & Anti-Strat AI 工作台..."
echo "👉 访问地址: http://127.0.0.1:8765"
exec ./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8765
