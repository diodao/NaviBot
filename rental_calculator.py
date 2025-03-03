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

def calculate_rental_cost_and_breakdown(start_time, end_time, schedule, discount_factors):
    """Считает стоимость и breakdown для всего интервала с учётом тарифов и discount_factors."""
    total_cost = 0.0
    breakdown = []
    current_time = start_time
    remaining_hours = (end_time - start_time).total_seconds() / 3600.0
    
    # Разбиваем интервал по точкам смены discount_factor
    time_points = [(start_time, discount_factors[0][1])]  # Используем только коэффициент
    if len(discount_factors) > 1:
        boarding_dt = discount_factors[1][0]
        disembarking_dt = discount_factors[2][0]
        time_points.append((boarding_dt, discount_factors[1][1]))
        time_points.append((disembarking_dt, discount_factors[2][1]))
    time_points.append((end_time, 0))  # Конец интервала

    for i in range(len(time_points) - 1):
        seg_start = time_points[i][0]
        seg_end = time_points[i + 1][0]
        discount_factor = time_points[i][1]
        seg_hours = (seg_end - seg_start).total_seconds() / 3600.0
        if seg_hours <= 0:
            continue
        effective_hours = seg_hours * discount_factor
        hours_covered = 0.0
        seg_breakdown = []
        for int_start, int_end, price in schedule:
            overlap = compute_overlap(seg_start, seg_end, int_start, int_end)
            if overlap > 0:
                overlap_hours = min(overlap, seg_hours - hours_covered)
                effective_overlap = overlap_hours * discount_factor
                total_cost += price * effective_overlap
                seg_breakdown.append((price, effective_overlap))
                hours_covered += overlap_hours
                if hours_covered >= seg_hours:
                    break
        if hours_covered < seg_hours - 0.01:
            logging.warning(f"Интервал {seg_start}–{seg_end}: не все часы покрыты тарифами ({seg_hours - hours_covered} ч остались)")
            if schedule:
                last_price = schedule[-1][2]
                remaining_effective = (seg_hours - hours_covered) * discount_factor
                total_cost += last_price * remaining_effective
                seg_breakdown.append((last_price, remaining_effective))
        breakdown.extend(seg_breakdown)
    
    # Собираем breakdown в порядке времени
    agg_breakdown = []
    seen_hours = 0.0
    for price, hours in breakdown:  # Убрали сортировку, идём по порядку добавления
        if seen_hours < remaining_hours:  # Ограничение по общему времени аренды
            hours_to_add = min(hours, remaining_hours - seen_hours)
            if hours_to_add > 0:
                agg_breakdown.append((price, hours_to_add))
                seen_hours += hours_to_add
    
    return total_cost, agg_breakdown

def format_breakdown(breakdown):
    parts = []
    for price, hours in breakdown:
        formatted_price = f"{int(price):,}".replace(",", " ")
        parts.append(f"({formatted_price}₽/ч x {hours:.2f}ч)")
    return " + ".join(parts) if parts else "(0₽/ч x 0.00ч)"

def normalize_boat_name(name):
    name_lower = name.strip().lower()
    return [name_lower, name_lower.replace("е", "ё"), name_lower.replace("ё", "е")]

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
    possible_names = normalize_boat_name(boat_name)
    boat_rows = boats_df[boats_df["Название теплохода"].str.strip().str.lower().isin(possible_names)]
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
    schedule = get_pricing_schedule(boat_info["Название теплохода"], boarding_date)

    if full_format:
        discount_factors = [
            (prep_start, 0.5),      # Подготовка
            (boarding_dt, 1.0),     # Основное время
            (disembarking_dt, 0.5)  # Разгрузка
        ]
        total_cost, breakdown = calculate_rental_cost_and_breakdown(prep_start, unloading_dt, schedule, discount_factors)
    else:
        discount_factors = [(boarding_dt, 1.0)]
        total_cost, breakdown = calculate_rental_cost_and_breakdown(boarding_dt, disembarking_dt, schedule, discount_factors)

    total_cost += float(cleaning_cost)
    breakdown_str = format_breakdown(breakdown)
    formatted_total_cost = f"{int(total_cost):,}".replace(",", " ")

    def fmt_time(dt):
        return dt.strftime("%H:%M")

    if full_format:
        result = (
            f"*{date_obj.strftime('%d.%m.%y')}*\n\n"
            f"*{boat_info['Название теплохода']}* - {link}\n"
            f"{fmt_time(prep_start)} - Подготовка (50%)\n"
            f"{fmt_time(boarding_dt)} - Посадка\n"
            f"{fmt_time(disembarking_dt)} - Высадка\n"
            f"{fmt_time(unloading_dt)} - Разгрузка (50%)\n"
            f"Причал: {dock}\n"
            f"Аренда: {breakdown_str} + {int(cleaning_cost)}₽ (уборка) = *{formatted_total_cost}*₽"
        )
    else:
        result = (
            f"*{date_obj.strftime('%d.%m.%y')}*\n\n"
            f"*{boat_info['Название теплохода']}* - {link}\n"
            f"{fmt_time(boarding_dt)} - Посадка\n"
            f"{fmt_time(disembarking_dt)} - Высадка\n"
            f"Причал: {dock}\n"
            f"Аренда: {breakdown_str} + {int(cleaning_cost)}₽ (уборка) = *{formatted_total_cost}*₽"
        )
    return result

if __name__ == '__main__':
    test_request = """09.08.25
Миконос
09:30-10:30-13:30-14:00"""
    try:
        date_obj, boat_name, times = parse_request(test_request)
        result = calculate_rental(date_obj, boat_name, times)
        print(result)
    except Exception as e:
        logging.error("Ошибка при расчёте: %s", e)