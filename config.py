# config.py

# Токен вашего бота (убедитесь, что он актуален)
TOKEN = '6951228291:AAHpvIyR7hFX-THCFc2P7-lG8WqKFCrf5b4'

# Пути к файлам
RENTAL_DATA_FILE = 'rental_data.xlsx'
LOG_FILE = 'bot.log'  # Изменили на относительный путь

# Форматы (для отображения и валидации)
DATE_FORMAT = 'DD.MM.YY'
TIME_FORMAT = 'HH:MM-HH:MM-HH:MM-HH:MM'

# Форма ввода – менеджерам для понимания требуемого формата запроса
INPUT_FORMAT = f"""
Дата (формат {DATE_FORMAT})
Название теплохода
Времена (формат {TIME_FORMAT} или HH:MM-HH:MM)
"""

# Форма вывода – как будет выглядеть ответ бота
OUTPUT_FORMAT = """\
{date}

{ship_name} - {link}
{prep_start} - Подготовка (50%)
{boarding_start} - Посадка
{disembarking_end} - Высадка
{unloading_end} - Разгрузка (50%)
Причал: {dock}
Аренда: {rental_cost}
"""

# Форматы ответов (если понадобится для обработки занятости времён)
RESPONSE_AVAILABLE = "Все времена доступны."
RESPONSE_NOT_AVAILABLE = "Одно или несколько времен заняты."
RESPONSE_ERROR = "Произошла ошибка: {error}"

# Тарифы и сезонность (пока используются как справочная информация, если данные будут брать из Excel,
# эти значения могут служить резервными или для других интерфейсов)
SEASONS = {
    'Белые ночи': {'start': '01.06', 'end': '30.06'},
    'Высокий сезон': {'start': '01.07', 'end': '31.08'},
    'Низкий сезон': {'start': '01.09', 'end': '31.05'},
}

WEEK_RANGES = {
    'Вс-Чт': ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг'],
    'Пт-Сб': ['Пятница', 'Суббота'],
    'Пн-Чт': ['Понедельник', 'Вторник', 'Среда', 'Четверг'],
    'Пт-Вс': ['Пятница', 'Суббота', 'Воскресенье'],
}

# Данные по причалам (также для справки или резервных значений)
DOCKS = {
    'Сицилия': 'Университетская 13',
    'Сиеста': 'Университетская 13',
}

# Пример тарифов (также для справки; основная информация для расчётов берется из Excel)
TARIFFS = {
    'Сицилия': {
        'Белые ночи': 11500,
        'Высокий сезон': 11000,
        'Низкий сезон': 10500,
        'Вс-Чт': 11000,
        'Пт-Сб': 11500,
        'Пн-Чт': 11000,
        'Пт-Вс': 11500,
    },
    'Сиеста': {
        'Белые ночи': 10500,
        'Высокий сезон': 10000,
        'Низкий сезон': 9500,
        'Вс-Чт': 10000,
        'Пт-Сб': 10500,
        'Пн-Чт': 10000,
        'Пт-Вс': 10500,
    },
}

# Стоимость уборки теплохода после аренды
CLEANING_COST = 3000
