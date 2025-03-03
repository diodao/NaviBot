import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import config
from rental_calculator import parse_request, calculate_rental, refresh_data

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_text = (
        "Привет! Я бот для расчёта стоимости аренды теплоходов.\n\n"
        "Формат запроса:\n"
        "1-я строка: дата (формат dd.mm.yy)\n"
        "2-я строка: название теплохода\n"
        "3-я строка: временной интервал (либо 2 значения, либо 4 для технических часов)\n\n"
        "Если в одном сообщении несколько запросов, отправьте их подряд (без пустых строк),\n"
        "либо пустые строки будут игнорированы и все непустые строки будут сгруппированы по 3.\n\n"
        "Для обновления базы данных отправьте команду /update_data или сообщение 'Обнови базу'."
    )
    await update.message.reply_text(welcome_text, disable_web_page_preview=True)

async def update_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        refresh_data()
        await update.message.reply_text("База данных обновлена.", disable_web_page_preview=True)
    except Exception as e:
        logger.error("Ошибка обновления базы: %s", e)
        await update.message.reply_text(f"Ошибка обновления базы: {e}", disable_web_page_preview=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    
    if text.lower() == "обнови базу":
        await update.message.reply_text("Обновляю базу...", disable_web_page_preview=True)
        try:
            refresh_data()
            await update.message.reply_text("База данных обновлена.", disable_web_page_preview=True)
        except Exception as e:
            logger.error("Ошибка обновления базы: %s", e)
            await update.message.reply_text(f"Ошибка обновления базы: {e}", disable_web_page_preview=True)
        return

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        await update.message.reply_text("Пустое сообщение.", disable_web_page_preview=True)
        return

    if len(lines) % 3 != 0:
        await update.message.reply_text(
            "Ошибка: общее число непустых строк должно быть кратно 3 (дата, название, временной интервал для каждого запроса).",
            disable_web_page_preview=True
        )
        return

    responses = []
    for i in range(0, len(lines), 3):
        block_lines = lines[i:i+3]
        block_text = "\n".join(block_lines)
        try:
            date_obj, boat_name, times = parse_request(block_text)
            result = calculate_rental(date_obj, boat_name, times)
            responses.append(result)
        except Exception as e:
            logger.error("Ошибка при обработке блока: %s", e)
            responses.append(f"Ошибка при обработке запроса:\n{block_text}\nОшибка: {e}")

    # Объединяем ответы без разделителей, просто через двойной перенос строки
    reply = "\n\n".join(responses)
    await update.message.reply_text(reply, disable_web_page_preview=True)

def main() -> None:
    application = ApplicationBuilder().token(config.TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update_data", update_data_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()