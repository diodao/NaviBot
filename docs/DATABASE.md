# База данных

SQLite, файл `navibot.db`, создаётся автоматически при первом запуске.

## Схема таблиц

### users
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Автоинкремент |
| username | TEXT UNIQUE | Логин |
| password_hash | TEXT | SHA256-хеш пароля |
| display_name | TEXT | Отображаемое имя |
| role | TEXT | `admin` / `editor` / `manager` |
| avatar | TEXT NULL | Имя файла аватарки |
| created_at | TEXT | Дата создания |

### boats
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Автоинкремент |
| name | TEXT UNIQUE | Название теплохода |
| link | TEXT | URL на сайте |
| dock | TEXT | Адрес причала |
| cleaning_cost | REAL | Стоимость уборки (руб.) |
| prep_hours | REAL | Время подготовки (часы) |
| unload_hours | REAL | Время разгрузки (часы) |
| wp_slug | TEXT NULL | Slug товара на WordPress |
| updated_at | TEXT | Дата последнего обновления |

### prices
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Автоинкремент |
| boat_id | INTEGER FK → boats | Ссылка на теплоход (CASCADE) |
| season_name | TEXT | Название сезона ("Белые ночи") |
| date_start | TEXT | Начало действия (YYYY-MM-DD) |
| date_end | TEXT | Конец действия (YYYY-MM-DD) |
| day_range | TEXT | Дни недели ("Пн-Пт", "Сб,Вс") |
| time_start | TEXT | Начало интервала (HH:MM) |
| time_end | TEXT | Конец интервала (HH:MM) |
| price_per_hour | REAL | Цена за час (руб.) |

### calculations
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Автоинкремент |
| user_id | INTEGER FK → users | Кто считал (CASCADE) |
| input_text | TEXT | Исходный запрос |
| results_json | TEXT | Результат (JSON) |
| created_at | TEXT | Когда |

### sync_log
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | Автоинкремент |
| sync_type | TEXT | `wordpress` / `excel_migration` |
| status | TEXT | `success` / `error` |
| details | TEXT | Подробности |
| created_at | TEXT | Когда |

## Индексы

- `idx_boats_name` — быстрый поиск по имени
- `idx_prices_boat_id` — цены по теплоходу
- `idx_calculations_user_id` — история по пользователю
- `idx_calculations_created_at` — сортировка по дате

## Особенности

### LOWER_PY — кириллица в SQLite

SQLite встроенный `LOWER()` не работает с кириллицей. Мы регистрируем Python-функцию:

```python
conn.create_function("LOWER_PY", 1, lambda s: s.lower() if s else s)
```

Используется в `get_boat_by_name()` для case-insensitive поиска.

### Поиск теплоходов по имени

`get_boat_by_name(name)` ищет в три попытки:
1. Точное совпадение (LOWER_PY)
2. Замена `ё` → `е`
3. Замена `е` → `ё`

### Расписание цен

`get_pricing_schedule_db(boat_name, boarding_date)` возвращает тарифные интервалы:
1. Находит теплоход по имени
2. Фильтрует prices по `date_start <= дата <= date_end`
3. Фильтрует по дню недели через `_weekday_in_range()`
4. Возвращает `[(datetime_start, datetime_end, price_per_hour), ...]`

### Дни недели

`_weekday_in_range("Пт", "Пн-Пт,Сб")` → True

Поддерживает:
- Диапазоны: `Пн-Пт`
- Отдельные дни: `Сб`
- Комбинации через запятую: `Пн-Пт,Сб`
- Обёртку через воскресенье: `Пт-Вт` (Пт, Сб, Вс, Пн, Вт)

## Ключевые функции (database.py)

### Пользователи
- `get_user_by_username(username)` → dict | None
- `get_user_by_id(user_id)` → dict | None
- `get_all_users()` → [dict] (без password_hash)
- `create_user(username, password, display_name, role)` → id | None
- `update_user(user_id, display_name, password, role)` — опциональные поля
- `delete_user(user_id)` — каскад на calculations

### Теплоходы
- `get_all_boats()` → [dict] по алфавиту
- `get_boat_by_name(name)` → dict | None (ё/е, case-insensitive)
- `create_boat(name, ...)` → id | None
- `update_boat(boat_id, **fields)` — whitelist полей
- `delete_boat(boat_id)` — каскад на prices

### Цены
- `get_prices_for_boat(boat_id)` → [dict]
- `get_pricing_schedule_db(boat_name, date)` → [(dt_start, dt_end, price)]
- `replace_prices_for_boat(boat_id, prices_list)` — удаляет старые, вставляет новые

### Миграция
- `migrate_from_excel(path)` — из rental_data.xlsx в SQLite (лист "Теплоходы" + "Цены")
- `log_sync(type, status, details)` — запись в sync_log
- `get_last_sync()` → dict | None (последняя успешная)
