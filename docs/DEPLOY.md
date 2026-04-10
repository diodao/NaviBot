# Деплой и обновления

## Продакшен

| Параметр | Значение |
|----------|----------|
| Сервер | Beget VPS, 1 CPU / 1 GB RAM / 10 GB NVMe |
| IP | 5.35.93.76 |
| Домен | nevastm.ru |
| ОС | Ubuntu 24.04 LTS |
| Python | 3.12 |
| Node.js | 20.x |

## Структура на сервере

```
/opt/navibot/              ← рабочая директория
├── venv/                  ← Python виртуальное окружение
├── frontend/dist/         ← собранный React (Nginx отдаёт)
├── avatars/               ← аватарки пользователей
├── navibot.db             ← SQLite база
├── .env                   ← секреты (JWT_SECRET)
├── deploy/                ← конфиги деплоя
└── ...                    ← остальной код

/etc/nginx/sites-enabled/navibot    ← конфиг Nginx
/etc/systemd/system/navibot.service ← systemd-сервис
/var/log/navibot/                   ← логи Gunicorn
```

## Компоненты

### Gunicorn (бэкенд)

```
/opt/navibot/venv/bin/gunicorn
  --workers 2
  --bind 127.0.0.1:5001
  --timeout 120
  app:app
```

Управление:
```bash
systemctl status navibot      # статус
systemctl restart navibot     # перезапуск
systemctl reload navibot      # graceful reload (без даунтайма)
journalctl -u navibot -f      # логи в реальном времени
```

### Nginx (веб-сервер)

- Слушает 80 (→ redirect 443) и 443 (SSL)
- `/api/*` → проксирует на Gunicorn (127.0.0.1:5001)
- `/api/avatars/*` → отдаёт файлы из /opt/navibot/avatars/
- `/assets/*` → статика с кешем 1 год
- Всё остальное → `frontend/dist/index.html` (SPA)

### SSL (Let's Encrypt)

```bash
# Первичная установка
certbot --nginx -d nevastm.ru --non-interactive --agree-tos -m admin@nevastm.ru

# Обновление (автоматическое через cron, но можно вручную)
certbot renew
```

## Обновление приложения

### Быстрый способ (одна команда)

```bash
ssh root@5.35.93.76
bash /opt/navibot/deploy/deploy.sh
```

Скрипт:
1. `git pull origin master`
2. Обновляет Python-зависимости
3. Пересобирает фронтенд (`npm run build`)
4. `systemctl reload navibot` (graceful — без даунтайма)

### Ручное обновление

```bash
ssh root@5.35.93.76
cd /opt/navibot

# Забрать код
git pull origin master

# Если изменились Python-зависимости
source venv/bin/activate
pip install -r requirements.txt

# Если изменился фронтенд
cd frontend && npm install && npm run build && cd ..

# Если изменился только бэкенд
systemctl reload navibot

# Если изменился Nginx-конфиг
cp deploy/navibot.nginx.conf /etc/nginx/sites-available/navibot
nginx -t && systemctl reload nginx
```

## Рабочий процесс разработки

```
1. Вносим правки локально (с Claude Code)
2. Тестируем через localhost:5173
3. Коммитим: git add ... && git commit
4. Пушим: git push origin master
5. На сервере: bash /opt/navibot/deploy/deploy.sh
```

## Мониторинг

```bash
# Статус бэкенда
systemctl status navibot

# Логи бэкенда (live)
journalctl -u navibot -f

# Логи Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Логи Gunicorn
tail -f /var/log/navibot/access.log
tail -f /var/log/navibot/error.log

# Диск
df -h

# RAM
free -h

# Процессы
htop
```

## Бекапы

### База данных

```bash
# Бекап
cp /opt/navibot/navibot.db /opt/navibot/navibot.db.backup.$(date +%Y%m%d)

# Восстановление
cp /opt/navibot/navibot.db.backup.YYYYMMDD /opt/navibot/navibot.db
systemctl restart navibot
```

### Полный бекап

```bash
tar czf /tmp/navibot-backup-$(date +%Y%m%d).tar.gz \
  /opt/navibot/navibot.db \
  /opt/navibot/avatars/ \
  /opt/navibot/.env
```

## Troubleshooting

### Бэкенд не запускается
```bash
journalctl -u navibot --no-pager -n 50  # смотреть логи
```

### 502 Bad Gateway
```bash
systemctl status navibot  # проверить что Gunicorn жив
systemctl restart navibot  # перезапустить
```

### Порт 5001 занят
```bash
lsof -ti:5001 | xargs kill -9
systemctl start navibot
```

### Фронтенд не обновился
```bash
cd /opt/navibot/frontend && npm run build
# Или в браузере: Ctrl+Shift+R (hard refresh)
```

### SSL сертификат истёк
```bash
certbot renew
systemctl reload nginx
```

## Масштабирование (будущее)

При переходе на PostgreSQL:
1. Установить PostgreSQL: `apt install postgresql`
2. Создать БД и пользователя
3. Заменить `database.py`: sqlite3 → psycopg2 / SQLAlchemy
4. Мигрировать данные
5. Увеличить Gunicorn workers до 4-8

При добавлении фоновых задач (чат, отчёты):
1. Установить Redis: `apt install redis-server`
2. Добавить Celery для очередей
3. Создать отдельный systemd-сервис для Celery worker
