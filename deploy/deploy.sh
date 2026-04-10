#!/bin/bash
# NaviBot — скрипт обновления на сервере
# Запуск: bash /opt/navibot/deploy/deploy.sh
#
# Что делает:
# 1. Забирает свежий код из GitHub
# 2. Обновляет Python-зависимости
# 3. Пересобирает фронтенд
# 4. Перезапускает бэкенд (graceful reload — без даунтайма)

set -e

APP_DIR="/opt/navibot"
cd "$APP_DIR"

echo "=== NaviBot Deploy ==="
echo "$(date '+%Y-%m-%d %H:%M:%S')"

# 1. Забираем код
echo "[1/4] Git pull..."
git pull origin master

# 2. Python-зависимости
echo "[2/4] Обновляю Python-зависимости..."
source venv/bin/activate
pip install -r requirements.txt --quiet

# 3. Фронтенд
echo "[3/4] Собираю фронтенд..."
cd frontend
npm install --silent
npm run build
cd ..

# 4. Перезапуск бэкенда (graceful — текущие запросы дообработаются)
echo "[4/4] Перезапускаю бэкенд..."
sudo systemctl reload navibot || sudo systemctl restart navibot

echo "=== Деплой завершён ==="
echo "$(date '+%Y-%m-%d %H:%M:%S')"
