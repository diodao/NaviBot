# NaviBot — Система расчёта аренды теплоходов

## Что это

Веб-приложение для менеджеров компании по аренде теплоходов в Санкт-Петербурге. Позволяет быстро рассчитать стоимость аренды с учётом сезонов, дней недели, времени суток и фаз мероприятия (подготовка, посадка, высадка, разгрузка).

## Стек

| Слой | Технология |
|------|-----------|
| Frontend | React 19 + Vite 8 |
| Backend | Flask 3.1 + Gunicorn |
| Database | SQLite |
| Web Server | Nginx + Let's Encrypt |
| OS | Ubuntu 24.04 |
| Deploy | Git + systemd |

## Быстрый старт (локально)

```bash
# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 app.py  # http://localhost:5001

# Frontend (в отдельном терминале)
cd frontend && npm install && npm run dev  # http://localhost:5173
```

Логин по умолчанию: `admin` / `admin`

## Структура проекта

```
NaviBot/
├── app.py                  # Flask API — все эндпоинты
├── database.py             # SQLite — таблицы, запросы, миграции
├── rental_calculator.py    # Движок расчёта стоимости
├── wp_parser.py            # Парсер данных из WordPress
├── config.py               # Статические константы
├── requirements.txt        # Python-зависимости
├── .env.example            # Шаблон переменных окружения
│
├── frontend/
│   ├── src/App.jsx         # React SPA — все компоненты
│   ├── src/App.css         # Стили
│   ├── vite.config.js      # Vite + API proxy
│   └── dist/               # Собранный фронтенд (production)
│
├── deploy/
│   ├── deploy.sh           # Скрипт обновления на сервере
│   ├── navibot.nginx.conf  # Конфиг Nginx
│   └── navibot.service     # Systemd-сервис
│
├── docs/                   # Документация (ты тут)
│   ├── README.md           # Обзор проекта (этот файл)
│   ├── ARCHITECTURE.md     # Архитектура и схема взаимодействия
│   ├── API.md              # Все API-эндпоинты
│   ├── DATABASE.md         # Схема БД и функции
│   ├── CALCULATOR.md       # Логика расчёта стоимости
│   ├── WP_SYNC.md          # Синхронизация с WordPress
│   ├── FRONTEND.md         # React-компоненты и UI
│   └── DEPLOY.md           # Деплой и обновления
│
├── avatars/                # Аватарки пользователей
├── navibot.db              # SQLite база (не в git)
└── rental_data.xlsx        # Excel-источник (одноразовая миграция)
```

## Документация

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Общая архитектура, потоки данных, схема компонентов |
| [API.md](API.md) | REST API — все эндпоинты, запросы, ответы |
| [DATABASE.md](DATABASE.md) | Схема таблиц, функции, миграции |
| [CALCULATOR.md](CALCULATOR.md) | Алгоритм расчёта, сегменты, скидки |
| [WP_SYNC.md](WP_SYNC.md) | WordPress-интеграция, парсер дат |
| [FRONTEND.md](FRONTEND.md) | React-компоненты, стейт, стили |
| [DEPLOY.md](DEPLOY.md) | Деплой на VPS, обновления, SSL |

## Роли пользователей

| Роль | Расчёт | Теплоходы (edit) | Пользователи | Синхронизация |
|------|--------|------------------|---------------|---------------|
| manager | + | - | - | - |
| editor | + | + | - | - |
| admin | + | + | + | + |

## Продакшен

- **URL**: https://nevastm.ru
- **Сервер**: Beget VPS (5.35.93.76)
- **Обновление**: `ssh root@5.35.93.76` → `bash /opt/navibot/deploy/deploy.sh`
