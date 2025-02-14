#!/usr/bin/env python3
import os
import asyncio
import threading
from flask import Flask

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import rental_calculator  # импортируйте модуль с функциями расчёта

# === Flask-сервер для работы в качестве веб-сервиса (Render/Beget требует, чтобы приложение слушало порт) ===
app = Flask(__name__)

@app.route('/')
def index():
    return 'ok'

def run_flask():
    # Получаем порт из переменной окружения PORT, если её нет – используем 5000
    port = int(os.environ.get('PORT', 5000))
    # Запускаем Flask на всех интерфейсах
    app.run(host='0.0.0.0', port=port)

# === Обработчики команд Telegram бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Получена команда /start")
    await update.message.reply_text("Привет! Я бот для расчёта стоимости аренды теплоходов.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        text = update.message.text.strip()
        # Вызов функции расчёта из модуля rental_calculator
        result = rental_calculator.calculate_rental(text)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке запроса: {e}")

# Команда для обновления базы данных (используем латинское название update_bd)
async def update_bd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        rental_calculator.load_data(force_reload=True)
        await update.message.reply_text("База данных обновлена.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обновлении базы: {e}")

# === Основная асинхронная функция для запуска бота ===
async def main_async():
    application = ApplicationBuilder().token(config.TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update_bd", update_bd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Удаляем webhook, если он установлен
    await application.bot.delete_webhook(drop_pending_updates=True)

    # Инициализируем и запускаем polling
    await application.initialize()
    await application.run_polling()

    # Эта строка удерживает цикл событий (никогда не завершается)
    await asyncio.Future()

# === Функция main: запускаем Flask-сервер в отдельном потоке и бота в основном потоке ===
def main():
    # Запускаем Flask-сервер в отдельном daemon‑потоке (чтобы приложение слушало указанный порт)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Получаем или создаём event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Добавляем задачу для запуска бота и запускаем цикл событий бесконечно
    loop.create_task(main_async())
    loop.run_forever()

if __name__ == '__main__':
    main()
