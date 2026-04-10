# API Reference

Base URL: `/api`

Все ответы — JSON. Аутентификация через заголовок `Authorization: Bearer {token}`.

## Аутентификация

### POST `/login`
Вход в систему.

**Запрос:**
```json
{ "username": "admin", "password": "admin" }
```

**Ответ 200:**
```json
{
  "token": "eyJ...",
  "user": { "id": 1, "username": "admin", "display_name": "Администратор", "role": "admin", "avatar": null }
}
```

**Ошибки:** 400 (нет полей), 401 (неверные данные)

### GET `/me` `@auth`
Текущий пользователь по токену.

**Ответ 200:**
```json
{ "user": { "id": 1, "username": "admin", "display_name": "Администратор", "role": "admin", "avatar": null } }
```

---

## Расчёты

### POST `/calculate` `@auth`
Расчёт стоимости аренды.

**Запрос:**
```json
{ "text": "16.08.26\nШустрый бобер\n16-17-23-23:30" }
```

Формат текста — блоки по 3 строки:
1. Дата: `DD.MM.YY`
2. Название теплохода
3. Время: `HH:MM-HH:MM` (посадка-высадка) или `HH:MM-HH:MM-HH:MM-HH:MM` (подготовка-посадка-высадка-разгрузка)

Можно несколько блоков подряд (6, 9, 12... строк).

**Ответ 200:**
```json
{
  "results": [
    {
      "result": "*16.08.26*\n\n*Шустрый бобер* - https://...\n16:00 - Подготовка (50%)\n..."
    }
  ]
}
```

Каждый элемент `results` — либо `{ "result": "..." }`, либо `{ "error": "...", "input": "..." }`.

### GET `/history` `@auth`
История расчётов текущего пользователя (до 200 записей).

**Ответ 200:**
```json
{
  "history": [
    { "id": 1, "input_text": "...", "results": [...], "created_at": "2026-04-10 19:00:00" }
  ]
}
```

### DELETE `/history/<id>` `@auth`
Удаление записи из истории (только своей).

---

## Теплоходы

### GET `/boats` `@auth`
Список всех теплоходов.

**Ответ 200:**
```json
{
  "boats": [
    { "id": 1, "name": "Хемингуэй", "link": "https://...", "dock": "Университетская 13", "cleaning_cost": 3000, "prep_hours": 1.0, "unload_hours": 0.5, "wp_slug": "teplohod-hemingway", "updated_at": "..." }
  ]
}
```

### GET `/boats/<id>` `@auth`
Теплоход + его цены.

**Ответ 200:**
```json
{
  "boat": { ... },
  "prices": [
    { "id": 1, "boat_id": 1, "season_name": "Белые ночи", "date_start": "2026-06-10", "date_end": "2026-06-30", "day_range": "Вс-Чт", "time_start": "06:00", "time_end": "21:00", "price_per_hour": 42000 }
  ]
}
```

### PUT `/boats/<id>` `@editor`
Редактирование метаданных теплохода.

**Запрос:**
```json
{ "link": "https://...", "dock": "Набережная 5", "cleaning_cost": 5000, "prep_hours": 1.5, "unload_hours": 1.0 }
```

Все поля опциональные.

### POST `/boats` `@admin`
Создание нового теплохода.

**Запрос:**
```json
{ "name": "Новый теплоход", "dock": "Причал 1", "cleaning_cost": 3000 }
```

**Ответ 201:** `{ "id": 79 }`

### DELETE `/boats/<id>` `@admin`
Удаление теплохода и всех его цен.

---

## Синхронизация

### GET `/sync/status` `@auth`
Статистика базы.

**Ответ 200:**
```json
{
  "boats_count": 78,
  "prices_count": 1796,
  "last_sync": { "id": 3, "sync_type": "wordpress", "status": "success", "details": "Обновлено: 77", "created_at": "2026-04-10 19:51:06" }
}
```

### POST `/sync/wp` `@admin`
Синхронизация цен с сайта teplohod-restoran.ru.

**Ответ 200:**
```json
{
  "message": "Синхронизация завершена. Обновлено: 77 теплоходов",
  "updated": 77,
  "skipped": []
}
```

### POST `/sync/migrate-excel` `@admin`
Одноразовая миграция из rental_data.xlsx.

---

## Пользователи (админ)

### GET `/admin/users` `@admin`
Список всех пользователей.

### POST `/admin/users` `@admin`
Создание пользователя.

**Запрос:**
```json
{ "username": "ivan", "password": "pass123", "display_name": "Иван Петров", "role": "manager" }
```

Роли: `admin`, `editor`, `manager`

### PUT `/admin/users/<id>` `@admin`
Обновление пользователя (все поля опциональные).

### DELETE `/admin/users/<id>` `@admin`
Удаление пользователя. Нельзя удалить самого себя.

### POST `/admin/users/<id>/avatar` `@admin`
Загрузка аватарки (multipart/form-data, поле `avatar`). Форматы: png, jpg, jpeg, webp.

### DELETE `/admin/users/<id>/avatar` `@admin`
Удаление аватарки.

### GET `/avatars/<filename>` (без авторизации)
Отдача файла аватарки.

---

## Коды ошибок

| Код | Значение |
|-----|----------|
| 400 | Неверный запрос (отсутствуют поля, неверный формат) |
| 401 | Не авторизован (нет токена, токен истёк, пользователь не найден) |
| 403 | Нет прав (роль не соответствует) |
| 404 | Не найдено (теплоход, пользователь) |
| 409 | Конфликт (имя уже занято) |
| 500 | Внутренняя ошибка сервера |

## Декораторы авторизации

| Декоратор | Доступ |
|-----------|--------|
| `@auth_required` | Любой авторизованный пользователь |
| `@editor_required` | admin + editor |
| `@admin_required` | Только admin |
