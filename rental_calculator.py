import datetime
import logging
from database import get_boat_by_name, get_pricing_schedule_db, get_boat_count

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def parse_time_str(time_str):
    return datetime.datetime.strptime(time_str.strip(), "%H:%M").time()


def parse_time_range(range_str):
    parts = range_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Неверный формат временного диапазона: {range_str}")
    start = parse_time_str(parts[0])
    end = parse_time_str(parts[1])
    return start, end


def compute_overlap(seg_start, seg_end, int_start, int_end):
    latest_start = max(seg_start, int_start)
    earliest_end = min(seg_end, int_end)
    delta = (earliest_end - latest_start).total_seconds() / 3600.0
    return max(delta, 0)


def calculate_segment_cost_and_hours(seg_start, seg_end, schedule, discount_factor=1.0):
    total_hours = (seg_end - seg_start).total_seconds() / 3600.0
    effective_hours = total_hours * discount_factor
    cost = 0.0
    breakdown = []
    current_time = seg_start

    overlaps = []
    for int_start, int_end, price in schedule:
        overlap = compute_overlap(seg_start, seg_end, int_start, int_end)
        if overlap > 0:
            overlap_start = max(seg_start, int_start)
            overlap_end = min(seg_end, int_end)
            overlaps.append((overlap_start, overlap_end, price, overlap))

    overlaps.sort(key=lambda x: x[0])

    hours_covered = 0.0
    for overlap_start, overlap_end, price, overlap_hours in overlaps:
        if current_time < seg_end and overlap_start <= seg_end:
            segment_end = min(overlap_end, seg_end)
            hours = (segment_end - max(current_time, overlap_start)).total_seconds() / 3600.0
            if hours > 0:
                effective_hours_segment = hours * discount_factor
                cost += price * effective_hours_segment
                breakdown.append((max(current_time, overlap_start), price, effective_hours_segment))
                hours_covered += hours
                current_time = max(current_time, segment_end)

    if abs(hours_covered - total_hours) > 0.01:
        logging.warning(f"Сегмент {seg_start}–{seg_end}: не все часы покрыты тарифами ({total_hours - hours_covered:.2f} ч остались)")
        if schedule:
            last_price = schedule[-1][2]
            remaining_hours = total_hours - hours_covered
            cost += last_price * (remaining_hours * discount_factor)
            breakdown.append((seg_end, last_price, remaining_hours * discount_factor))

    return cost, breakdown, effective_hours


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
    boat = get_boat_by_name(boat_name)
    if not boat:
        raise ValueError(f"Теплоход '{boat_name}' не найден.")

    link = boat.get('link', '')
    dock = boat.get('dock', 'Неизвестный причал')
    cleaning_cost = float(boat.get('cleaning_cost', 3000))

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
    schedule = get_pricing_schedule_db(boat['name'], boarding_date)

    if full_format:
        prep_cost, prep_breakdown, prep_hours = calculate_segment_cost_and_hours(prep_start, boarding_dt, schedule, discount_factor=0.5)
        main_cost, main_breakdown, main_hours = calculate_segment_cost_and_hours(boarding_dt, disembarking_dt, schedule, discount_factor=1.0)
        unload_cost, unload_breakdown, unload_hours = calculate_segment_cost_and_hours(disembarking_dt, unloading_dt, schedule, discount_factor=0.5)
        total_cost = prep_cost + main_cost + unload_cost + cleaning_cost
        all_breakdown = prep_breakdown + main_breakdown + unload_breakdown
    else:
        main_cost, main_breakdown, main_hours = calculate_segment_cost_and_hours(boarding_dt, disembarking_dt, schedule, discount_factor=1.0)
        total_cost = main_cost + cleaning_cost
        all_breakdown = main_breakdown

    # Агрегируем breakdown
    all_breakdown.sort(key=lambda x: x[0])
    agg = {}
    order = []
    for start_time, price, hours in all_breakdown:
        if price not in agg:
            agg[price] = 0
            order.append((start_time, price))
        agg[price] += hours

    order.sort(key=lambda x: x[0])
    breakdown = [(price, agg[price]) for _, price in order]
    breakdown_str = " + ".join(f"({int(price):,}₽/ч x {hours:.2f}ч)".replace(",", " ") for price, hours in breakdown)

    def fmt_time(dt):
        return dt.strftime("%H:%M")

    if full_format:
        result = (
            f"*{date_obj.strftime('%d.%m.%y')}*\n\n"
            f"*{boat['name']}* - {link}\n"
            f"{fmt_time(prep_start)} - Подготовка (50%)\n"
            f"{fmt_time(boarding_dt)} - Посадка\n"
            f"{fmt_time(disembarking_dt)} - Высадка\n"
            f"{fmt_time(unloading_dt)} - Разгрузка (50%)\n"
            f"Причал: {dock}\n"
            f"Аренда: {breakdown_str} + {int(cleaning_cost)}₽ (уборка) = *{int(total_cost):,}*₽".replace(",", " ")
        )
    else:
        result = (
            f"*{date_obj.strftime('%d.%m.%y')}*\n\n"
            f"*{boat['name']}* - {link}\n"
            f"{fmt_time(boarding_dt)} - Посадка\n"
            f"{fmt_time(disembarking_dt)} - Высадка\n"
            f"Причал: {dock}\n"
            f"Аренда: {breakdown_str} + {int(cleaning_cost)}₽ (уборка) = *{int(total_cost):,}*₽".replace(",", " ")
        )
    return result


def refresh_data():
    """Совместимость — теперь данные в SQLite, перечитывать не нужно."""
    logging.info("Данные хранятся в SQLite, refresh не требуется.")


def get_data():
    """Совместимость — возвращает количество теплоходов."""
    return {'boat_count': get_boat_count()}
