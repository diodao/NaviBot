"""
Парсер данных из WordPress REST API (navibot/v1/prices).

Преобразует текстовые описания сезонов, времён и дней недели
из формата WP в формат NaviBot SQLite.
"""
import re
import logging
from datetime import date

logger = logging.getLogger(__name__)

MONTHS = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
    'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
    'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12,
}

# Текущий год для формирования дат
YEAR = date.today().year


def _clean_text(text):
    """Убирает HTML-теги, лишние пробелы и переносы."""
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_date(day_str, month_str):
    """Парсит '14 мая' → date(YEAR, 5, 14)."""
    day = int(day_str)
    month = MONTHS.get(month_str.lower())
    if not month:
        raise ValueError(f"Неизвестный месяц: {month_str}")
    return date(YEAR, month, day)


def parse_season_dates(text):
    """
    Парсит текстовое описание сезонных дат в список пар (date_start, date_end).

    Примеры:
        "до 14 мая и с 16 сентября" → [(01-01, 05-14), (09-16, 12-31)]
        "с 15 мая по 9 июня и с 1 июля по 15 сентября" → [(05-15, 06-09), (07-01, 09-15)]
        "с 10 июня по 30 июня" → [(06-10, 06-30)]
        "весь сезон" / пустая строка → [(01-01, 12-31)]
    """
    text = _clean_text(text)
    if not text or text.lower() in ('весь сезон', 'весь год', 'круглый год'):
        return [(date(YEAR, 1, 1), date(YEAR, 12, 31))]

    # Убираем текстовые названия сезонов в начале ("Белые ночи с 5 июня...")
    text = re.sub(r'^[А-Яа-яёЁ]+\s+[А-Яа-яёЁ]+\s+(?=с\s)', '', text)

    # Разбиваем по "и" / ","
    parts = re.split(r'\s+и\s+|,\s*', text)
    ranges = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Убираем лидирующие "и "
        part = re.sub(r'^и\s+', '', part)

        # "с/со DD месяца по/до DD месяца"
        m = re.match(r'(?:с|со)\s+(\d+)\s+(\w+)\s+(?:по|до)\s+(\d+)\s+(\w+)', part, re.IGNORECASE)
        if m:
            d_start = _parse_date(m.group(1), m.group(2))
            d_end = _parse_date(m.group(3), m.group(4))
            ranges.append((d_start, d_end))
            continue

        # "DD месяца по DD месяца" (без "с")
        m = re.match(r'(\d+)\s+(\w+)\s+по\s+(\d+)\s+(\w+)', part, re.IGNORECASE)
        if m and m.group(2).lower() in MONTHS:
            d_start = _parse_date(m.group(1), m.group(2))
            d_end = _parse_date(m.group(3), m.group(4))
            ranges.append((d_start, d_end))
            continue

        # "до/по DD месяца"
        m = re.match(r'(?:до|по)\s+(\d+)\s+(\w+)', part, re.IGNORECASE)
        if m:
            d_end = _parse_date(m.group(1), m.group(2))
            ranges.append((date(YEAR, 1, 1), d_end))
            continue

        # "с/со/от DD месяца"
        m = re.match(r'(?:с|со|от)\s+(\d+)\s+(\w+)', part, re.IGNORECASE)
        if m:
            d_start = _parse_date(m.group(1), m.group(2))
            ranges.append((d_start, date(YEAR, 12, 31)))
            continue

        # Голая дата "DD месяца" — считаем как "с DD месяца"
        m = re.match(r'(\d+)\s+(\w+)$', part, re.IGNORECASE)
        if m and m.group(2).lower() in MONTHS:
            d_start = _parse_date(m.group(1), m.group(2))
            ranges.append((d_start, date(YEAR, 12, 31)))
            continue

        logger.warning("Не удалось распарсить сезонные даты: '%s'", part)

    if not ranges:
        logger.warning("Пустой результат парсинга дат из '%s', используем весь год", text)
        return [(date(YEAR, 1, 1), date(YEAR, 12, 31))]

    return ranges


def normalize_time(time_str):
    """
    '10.00' → '10:00', '10:00' → '10:00', '9.00' → '09:00'
    """
    t = time_str.strip().replace('.', ':')
    parts = t.split(':')
    if len(parts) == 2:
        h = parts[0].zfill(2)
        m = parts[1].zfill(2)
        return f"{h}:{m}"
    return t


def parse_time_field(time_str):
    """
    '10.00 - 18.00' → ('10:00', '18:00')
    '06.00 - 21.00' → ('06:00', '21:00')
    """
    time_str = _clean_text(time_str)
    # Разделитель может быть " - ", "-", " – ", "–"
    parts = re.split(r'\s*[-–]\s*', time_str)
    if len(parts) != 2:
        raise ValueError(f"Не удалось распарсить время: '{time_str}'")
    return normalize_time(parts[0]), normalize_time(parts[1])


def normalize_day_range(day_range_str):
    """
    'Пт  - Сб' → 'Пт-Сб'
    'Вс - Чт' → 'Вс-Чт'
    'Пн-Чт' → 'Пн-Чт'
    """
    text = _clean_text(day_range_str)
    # Убираем лишние пробелы вокруг дефиса/тире
    text = re.sub(r'\s*[-–]\s*', '-', text)
    return text


def parse_wp_boat(boat_data):
    """
    Преобразует данные теплохода из WP JSON в список ценовых записей для NaviBot.

    Вход: {"name": "...", "prices": [{"season": "...", "season_dates": "...", "time": "...", "day_range": "...", "price": 42000}, ...]}
    Выход: список dict с ключами: season_name, date_start, date_end, day_range, time_start, time_end, price_per_hour
    """
    prices_out = []
    for p in boat_data.get('prices', []):
        season_name = _clean_text(p.get('season', ''))
        season_dates_text = p.get('season_dates', '')
        time_str = p.get('time', '')
        day_range_raw = p.get('day_range', '')
        price_raw = p.get('price', 0)

        try:
            price = float(price_raw)
        except (ValueError, TypeError):
            logger.warning("Некорректная цена '%s' для %s — пропуск", price_raw, boat_data.get('name'))
            continue

        if price <= 0:
            continue

        try:
            time_start, time_end = parse_time_field(time_str)
        except ValueError as e:
            logger.warning("Ошибка парсинга времени для %s: %s", boat_data.get('name'), e)
            continue

        day_range = normalize_day_range(day_range_raw)
        date_ranges = parse_season_dates(season_dates_text)

        for d_start, d_end in date_ranges:
            prices_out.append({
                'season_name': season_name,
                'date_start': d_start.strftime('%Y-%m-%d'),
                'date_end': d_end.strftime('%Y-%m-%d'),
                'day_range': day_range,
                'time_start': time_start,
                'time_end': time_end,
                'price_per_hour': price,
            })

    return prices_out
