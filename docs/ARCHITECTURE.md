# Архитектура NaviBot

## Общая схема

```
                    ┌─────────────┐
                    │   Браузер   │
                    └──────┬──────┘
                           │ HTTPS
                    ┌──────▼──────┐
                    │    Nginx    │
                    │  (SSL, gzip)│
                    └──┬──────┬──┘
           /api/*      │      │     всё остальное
                ┌──────▼──┐ ┌─▼──────────┐
                │ Gunicorn │ │ dist/      │
                │ (Flask)  │ │ (React SPA)│
                │ :5001    │ └────────────┘
                └────┬─────┘
                     │
              ┌──────▼──────┐
              │   SQLite    │
              │ navibot.db  │
              └─────────────┘
```

## Потоки данных

### 1. Расчёт стоимости

```
Менеджер вводит текст → POST /api/calculate
  → parse_request()         # парсинг 3 строк: дата, теплоход, время
  → get_boat_by_name()      # SQLite: boats table
  → get_pricing_schedule_db() # SQLite: prices table, фильтр по дате + день недели
  → calculate_rental()      # сегментация, перекрытие интервалов, скидки
  → save_calculation()      # SQLite: calculations table
  → JSON-ответ с форматированным текстом
```

### 2. Синхронизация с WordPress

```
Админ нажимает "Синхронизировать" → POST /api/sync/wp
  → requests.get(teplohod-restoran.ru/wp-json/navibot/v1/prices)
  → Для каждого теплохода:
     → parse_wp_boat()
        → parse_season_dates()  # "до 14 мая и с 16 сентября" → даты
        → parse_time_field()    # "10.00 - 18.00" → "10:00", "18:00"
        → normalize_day_range() # "Пт  - Сб" → "Пт-Сб"
     → get_boat_by_name() или create_boat()
     → replace_prices_for_boat()
  → log_sync()
```

### 3. Аутентификация

```
POST /api/login (username, password)
  → get_user_by_username()
  → verify_password() (SHA256)
  → create_token() (JWT, 72ч)
  → Клиент сохраняет в localStorage

Каждый запрос:
  → Header: Authorization: Bearer {token}
  → @auth_required декоратор → jwt.decode() → g.user
```

## Ключевые решения

| Решение | Причина |
|---------|---------|
| SQLite вместо PostgreSQL | Достаточно для текущей нагрузки (< 10 пользователей), проще деплой, нет зависимости от внешнего сервиса |
| JWT вместо сессий | Stateless, не нужен Redis/memcached, токен живёт 72 часа |
| Один файл App.jsx | Приложение компактное (~700 строк), разделение на файлы усложнит без пользы |
| Gunicorn 2 workers | 1 ГБ RAM на сервере, SQLite не любит параллельную запись |
| Nginx отдаёт статику | Быстрее чем через Flask, кеширование assets на 1 год |
| WordPress pull (не push) | Контроль на стороне NaviBot, не зависим от WP-хуков |

## Масштабирование (план)

При росте системы (чат, бухгалтерия, отчёты):

1. **БД** — миграция SQLite → PostgreSQL (заменить `get_db()`, добавить пул соединений)
2. **Кеш** — Redis для сессий и часто запрашиваемых данных
3. **Очереди** — Celery для фоновых задач (синхронизация, отчёты)
4. **Фронтенд** — разбить App.jsx на модули, добавить React Router
5. **API** — версионирование (`/api/v1/`, `/api/v2/`)
6. **Мониторинг** — Sentry для ошибок, Prometheus для метрик
