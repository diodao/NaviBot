# rental_calculator.py
import pandas as pd
import datetime
import logging
from config import RENTAL_DATA_FILE, CLEANING_COST

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Глобальное кэширование данных из Excel
_data_cache = None

def load_data():
    """
    Загружает данные из файла rental_data.xlsx.
    Ожидается наличие двух листов: "Теплоходы" и "Цены".
    """
    try:
        boats_df = pd.read_excel(RENTAL_DATA_FILE, sheet_name="Теплоходы", engine="openpyxl")
        prices_df = pd.read_excel(RENTAL_DATA_FILE, sheet_name="Цены", engine="openpyxl")
        data = {"Теплоходы": boats_df, "Цены": prices_df}
        logging.info("Данные успешно загружены из файла: %s", RENTAL_DATA_FILE)
        return data
    except Exception as e:
        logging.error("Ошибка при загрузке данных из Excel: %s", e)
        raise

def get_data():
    """Возвращает кэшированные данные; при первом обращении загружает их."""
    global _data_cache
    if _data_cache is None:
        _data_cache = load_data()
    return _data_cache

def refresh_data():
    """Обновляет кэшированные данные из Excel."""
    global _data_cache
    _data_cache = load_data()
    logging.info("Данные обновлены.")

# --- Вспомогательные функции для работы с датами и временем ---

def parse_time_str(time_str):
    """Парсит строку вида '10:00' в объект datetime.time."""
    return datetime.datetime.strptime(time_str.strip(), "%H:%M").time()

def parse_time_range(range_str):
    """
    Из строки вида "10:00 - 18:00" возвращает пару time объектов (start, end).
    Если start >= end, считаем, что интервал переходит через полночь.
    """
    parts = range_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Неверный формат временного диапазона: {range_str}")
    start = parse_time_str(parts[0])
    end = parse_time_str(parts[1])
    return start, end

def weekday_short(dt):
    """Возвращает сокращённое название дня недели для даты dt (Monday -> 'Пн', ..., Sunday -> 'Вс')."""
    mapping = {0:"Пн", 1:"Вт", 2:"Ср", 3:"Чт", 4:"Пт", 5:"Сб", 6:"Вс"}
    return mapping[dt.weekday()]

def weekday_in_range(day_short, range_str):
    """
    Проверяет, входит ли день (например, 'Ср') в диапазон, заданный строкой.
    Например, если range_str="Пн-Чт", то 'Ср' входит; если range_str="Пт-Вс", то 'Ср' не входит.
    Дополнительно допускается перечисление через запятую.
    """
    options = [opt.strip() for opt in range_str.split(",")]
    for opt in options:
        if "-" in opt:
            start, end = opt.split("-")
            start = start.strip()
            end = end.strip()
            week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            if week.index(start) <= week.index(end):
                if week.index(start) <= week.index(day_short) <= week.index(end):
                    return True
            else:
                if week.index(day_short) >= week.index(start) or week.index(day_short) <= week.index(end):
                    return True
        else:
            if day_short == opt:
                return True
    return False

# --- Функции для формирования расписания тарифов на день ---

def get_pricing_schedule(boat_name, boarding_date):
    """
    Для заданного теплохода и даты посадки (boarding_date) выбирает из таблицы "Цены"
    все строки, для которых:
      - boarding_date входит в [Дата начала, Дата окончания] (даты берутся как date)
      - день недели посадки (boarding_date) удовлетворяет условию в столбце "День недели"
    Для каждой подходящей строки формируется кортеж:
       (start_datetime, end_datetime, price)
    Если время в диапазоне переходит через полночь, end_datetime увеличивается на 1 день.
    """
    data = get_data()
    prices_df = data["Цены"]
    schedule = []
    if isinstance(boarding_date, datetime.datetime):
        boarding_date = boarding_date.date()
    day_short = weekday_short(datetime.datetime.combine(boarding_date, datetime.time(0,0)))
    for _, row in prices_df.iterrows():
        if str(row["Название теплохода"]).strip().lower() != boat_name.lower():
            continue
        try:
            # Используем pd.to_datetime для корректного преобразования дат
            start_date = pd.to_datetime(row["Дата начала"]).date()
            end_date = pd.to_datetime(row["Дата окончания"]).date()
        except Exception as e:
            logging.error("Ошибка парсинга дат в строке: %s", row)
            continue
        if not (start_date <= boarding_date <= end_date):
            continue
        day_range = str(row["День недели"]).strip()
        if not weekday_in_range(day_short, day_range):
            continue
        time_range = str(row["Время"]).strip()
        try:
            t_start, t_end = parse_time_range(time_range)
        except Exception as e:
            logging.error("Ошибка парсинга временного диапазона: %s", time_range)
            continue
        dt_start = datetime.datetime.combine(boarding_date, t_start)
        dt_end = datetime.datetime.combine(boarding_date, t_end)
        if t_start >= t_end:
            dt_end += datetime.timedelta(days=1)
        price_raw = str(row["Стоимость (руб/ч)"]).replace(" ", "").replace(",", ".")
        try:
            price = float(price_raw)
        except Exception:
            price = 0.0
        schedule.append((dt_start, dt_end, price))
    if not schedule:
        logging.warning("Для теплохода '%s' и даты %s не найдено подходящих тарифных строк.", boat_name, boarding_date)
    schedule.sort(key=lambda x: x[0])
    return schedule

def compute_overlap(seg_start, seg_end, int_start, int_end):
    """
    Вычисляет пересечение интервала [seg_start, seg_end] с интервалом [int_start, int_end] в часах.
    Возвращает продолжительность в часах (float). Если пересечения нет – 0.
    """
    latest_start = max(seg_start, int_start)
    earliest_end = min(seg_end, int_end)
    delta = (earliest_end - latest_start).total_seconds() / 3600.0
    return max(delta, 0)

def calculate_segment_cost(boat_name, seg_start, seg_end, boarding_date, discount_factor=1.0):
    """
    Для заданного сегмента аренды (с datetime seg_start и seg_end) вычисляет стоимость и формирует
    breakdown – список кортежей (tariff, effective_hours).
    discount_factor – множитель (например, 0.5 для технических часов).
    Возвращает: (стоимость сегмента (float), breakdown (list))
    """
    schedule = get_pricing_schedule(boat_name, boarding_date)
    cost = 0.0
    breakdown = []
    for int_start, int_end, price in schedule:
        overlap = compute_overlap(seg_start, seg_end, int_start, int_end)
        if overlap > 0:
            effective_hours = overlap * discount_factor
            cost_seg = effective_hours * price
            cost += cost_seg
            breakdown.append((price, effective_hours))
    return cost, breakdown

def aggregate_breakdown(breakdowns):
    """
    Принимает список breakdown, состоящий из кортежей (tariff, effective_hours),
    и агрегирует их по тарифу.
    Возвращает строку вида:
      "(16000₽/ч x 4.75ч) + (15000₽/ч x 1.5ч)"
    """
    agg = {}
    for price, hours in breakdowns:
        agg[price] = agg.get(price, 0) + hours
    parts = []
    for price, hours in agg.items():
        parts.append(f"({int(price)}₽/ч x {round(hours,2)}ч)")
    return " + ".join(parts)

# --- Функция для разбора запроса менеджера ---

def parse_request(message_text):
    """
    Ожидаемый формат запроса:
      07.09.25
      Антверпен
      21:30-22:30-02:30-03:00
    или (без технических часов):
      07.09.25
      Антверпен
      18-22
    Возвращает: (date_obj, boat_name, times)
       где times – список объектов datetime.time.
       Если 4 значения – [prep, boarding, disembarking, unloading];
       Если 2 – [boarding, disembarking].
    """
    lines = [line.strip() for line in message_text.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValueError("Некорректный формат запроса. Должны быть не менее 3 строк.")
    date_str = lines[0]
    boat_name = lines[1]
    times_str = lines[2]
    time_parts = times_str.split("-")
    normalized_times = []
    for part in time_parts:
        if ":" in part:
            normalized_times.append(part)
        else:
            normalized_times.append(part + ":00")
    if len(normalized_times) not in [2, 4]:
        raise ValueError("Ожидается 2 или 4 временных значения.")
    try:
        date_obj = datetime.datetime.strptime(date_str, "%d.%m.%y").date()
    except Exception as e:
        raise ValueError("Неверный формат даты, ожидается dd.mm.yy.") from e
    times = []
    for t_str in normalized_times:
        try:
            t_obj = datetime.datetime.strptime(t_str, "%H:%M").time()
            times.append(t_obj)
        except Exception as e:
            raise ValueError(f"Неверный формат времени: {t_str}") from e
    return date_obj, boat_name, times

# --- Основная функция расчёта аренды ---

def calculate_rental(date_obj, boat_name, times):
    """
    Производит расчёт аренды и возвращает отформатированную строку-ответ.
    Если times содержит 4 значения – учитываются технические интервалы,
    если 2 – используется только основной интервал.
    В строке "Аренда:" выводится подробный расчёт тарифов.
    """
    data = get_data()
    boats_df = data["Теплоходы"]
    boat_rows = boats_df[boats_df["Название теплохода"].str.strip().str.lower() == boat_name.lower()]
    if boat_rows.empty:
        raise ValueError(f"Теплоход '{boat_name}' не найден.")
    boat_info = boat_rows.iloc[0]
    link = boat_info.get("Ссылка", f"https://example.com/{boat_name.lower()}")
    dock = boat_info.get("Адрес причала", "Неизвестный причал")
    cleaning_cost = boat_info.get("Стоимость уборки", CLEANING_COST)
    full_format = (len(times) == 4)
    if full_format:
        prep_time, boarding_time, disembarking_time, unloading_time = times
        prep_start = datetime.datetime.combine(date_obj, prep_time)
        boarding_dt = datetime.datetime.combine(date_obj, boarding_time)
        if boarding_dt <= prep_start:
            boarding_dt += datetime.timedelta(days=1)
        disembarking_dt = datetime.datetime.combine(date_obj, disembarking_time)
        if disembarking_dt <= boarding_dt:
            disembarking_dt += datetime.timedelta(days=1)
        unloading_dt = datetime.datetime.combine(date_obj, unloading_time)
        if unloading_dt <= disembarking_dt:
            unloading_dt += datetime.timedelta(days=1)
    else:
        boarding_dt = datetime.datetime.combine(date_obj, times[0])
        disembarking_dt = datetime.datetime.combine(date_obj, times[1])
        if disembarking_dt <= boarding_dt:
            disembarking_dt += datetime.timedelta(days=1)
        prep_start = boarding_dt
        unloading_dt = disembarking_dt

    boarding_date = boarding_dt.date()

    # Рассчитываем стоимость сегментов и получаем breakdown для каждого
    prep_cost, prep_breakdown = calculate_segment_cost(boat_name, prep_start, boarding_dt, boarding_date, discount_factor=0.5)
    main_cost, main_breakdown = calculate_segment_cost(boat_name, boarding_dt, disembarking_dt, boarding_date, discount_factor=1.0)
    unload_cost, unload_breakdown = calculate_segment_cost(boat_name, disembarking_dt, unloading_dt, boarding_date, discount_factor=0.5)

    total_cost = prep_cost + main_cost + unload_cost + float(cleaning_cost)
    overall_breakdown = prep_breakdown + main_breakdown + unload_breakdown
    breakdown_str = aggregate_breakdown(overall_breakdown)
    
    def fmt_time(dt):
        return dt.strftime("%H:%M")

    if full_format:
        result = (
            f"{date_obj.strftime('%d.%m.%y')}\n\n"
            f"{boat_name} - {link}\n"
            f"{fmt_time(prep_start)} - Подготовка (50%)\n"
            f"{fmt_time(boarding_dt)} - Посадка\n"
            f"{fmt_time(disembarking_dt)} - Высадка\n"
            f"{fmt_time(unloading_dt)} - Разгрузка (50%)\n"
            f"Причал: {dock}\n"
            f"Аренда: {breakdown_str} + {int(cleaning_cost)}₽ (уборка) = {int(total_cost)}₽"
        )
    else:
        result = (
            f"{date_obj.strftime('%d.%m.%y')}\n\n"
            f"{boat_name} - {link}\n"
            f"{fmt_time(boarding_dt)} - Посадка\n"
            f"{fmt_time(disembarking_dt)} - Высадка\n"
            f"Причал: {dock}\n"
            f"Аренда: {breakdown_str} + {int(cleaning_cost)}₽ (уборка) = {int(total_cost)}₽"
        )
    return result

# --- Для тестирования модуля ---
if __name__ == '__main__':
    # Пример запроса для Антверпена (уже тестировался):
    sample_request1 = """07.09.25
Антверпен
21:30-22:30-02:30-03:00"""
    
    # Пример запроса для Амели:
    sample_request2 = """17.07.25
Амели
13-14-19-19:30"""
    
    # Пример запроса для Хемингуэй:
    sample_request3 = """09.07.25
Хемингуэй
17-18-23-23:30"""
    
    for req in [sample_request1, sample_request2, sample_request3]:
        try:
            date_obj, boat_name, times = parse_request(req)
            result = calculate_rental(date_obj, boat_name, times)
            print(result)
            print("\n" + "-"*50 + "\n")
        except Exception as e:
            logging.error("Ошибка при расчёте: %s", e)
