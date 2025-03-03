import pandas as pd
import datetime
import logging
from config import RENTAL_DATA_FILE, CLEANING_COST

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

_data_cache = None

def load_data():
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
    global _data_cache
    if _data_cache is None:
        _data_cache = load_data()
    return _data_cache

def refresh_data():
    global _data_cache
    _data_cache = load_data()
    logging.info("Данные обновлены.")

def parse_time_str(time_str):
    return datetime.datetime.strptime(time_str.strip(), "%H:%M").time()

def parse_time_range(range_str):
    parts = range_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Неверный формат временного диапазона: {range_str}")
    start = parse_time_str(parts[0])
    end = parse_time_str(parts[1])
    return start, end

def weekday_short(dt):
    mapping = {0:"Пн", 1:"Вт", 2:"Ср", 3:"Чт", 4:"Пт", 5:"Сб", 6:"Вс"}
    return mapping[dt.weekday()]

def weekday_in_range(day_short, range_str):
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

def get_pricing_schedule(boat_name, boarding_date):
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
    latest_start = max(seg_start, int_start)
    earliest_end = min(seg_end, int_end)
    delta = (earliest_end - latest_start).total_seconds() / 3600.0
    return max(delta, 0)

def calculate_segment_cost_and_hours(seg_start, seg_end, schedule, discount_factor=1.0):
    """Рассчитывает стоимость и фиксирует реальное время сегмента."""
    total_hours = (seg_end - seg_start).total_seconds() / 3600.0  # Реальное время сегмента
    effective_hours = total_hours * discount_factor  # Учитываем скидку для тех. времени
    cost = 0.0
    breakdown = []
    hours_remaining = total_hours
    for int_start, int_end, price in schedule:
        overlap = compute_overlap(seg_start, seg_end, int_start, int_end)
        if overlap > 0:
            overlap_hours = min(overlap, hours_remaining)
            effective_overlap = overlap_hours * discount_factor
            cost += price * effective_overlap
            breakdown.append((price, effective_overlap))
            hours_remaining -= overlap_hours
        if hours_remaining <= 0:
            break
    if hours_remaining > 0.01:
        logging.warning(f"Сегмент {seg_start}–{seg_end}: не все часы покрыты тарифами ({hours_remaining} ч остались)")
        # Используем последний тариф для оставшихся часов
        if schedule:
            last_price = schedule[-1][2]
            cost += last_price * (hours_remaining * discount_factor)
            breakdown.append((last_price, hours_remaining * discount_factor))
    return cost, breakdown, effective_hours

def aggregate_breakdown(breakdowns):
    agg = {}
    for price, hours in breakdowns:
        agg[price] = agg.get(price, 0) + hours
    parts = []
    for price, hours in agg.items():
        parts.append(f"({int(price)}₽/ч x {hours:.2f}ч)")
    return " + ".join(parts)

def parse_request(message_text):
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

def calculate_rental(date_obj, boat_name, times):
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
    schedule = get_pricing_schedule(boat_name, boarding_date)

    if full_format:
        prep_cost, prep_breakdown, prep_hours = calculate_segment_cost_and_hours(prep_start, boarding_dt, schedule, discount_factor=0.5)
        main_cost, main_breakdown, main_hours = calculate_segment_cost_and_hours(boarding_dt, disembarking_dt, schedule, discount_factor=1.0)
        unload_cost, unload_breakdown, unload_hours = calculate_segment_cost_and_hours(disembarking_dt, unloading_dt, schedule, discount_factor=0.5)
        total_hours = prep_hours + main_hours + unload_hours
    else:
        main_cost, main_breakdown, main_hours = calculate_segment_cost_and_hours(boarding_dt, disembarking_dt, schedule, discount_factor=1.0)
        prep_cost, unload_cost = 0, 0
        prep_breakdown, unload_breakdown = [], []
        total_hours = main_hours

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

if __name__ == '__main__':
    test_request = """09.08.25
Переяслав
09:30-10:30-13:30-14:00"""
    try:
        date_obj, boat_name, times = parse_request(test_request)
        result = calculate_rental(date_obj, boat_name, times)
        print(result)
    except Exception as e:
        logging.error("Ошибка при расчёте: %s", e)