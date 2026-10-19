import os
import threading
import asyncio
import datetime
import json

from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from gigachat import GigaChat

# ============================================================
# Токены из переменных окружения Render
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GIGACHAT_KEY = os.environ.get("GIGACHAT_KEY")

# ============================================================
# GigaChat
# ============================================================
giga = GigaChat(credentials=GIGACHAT_KEY, verify_ssl_certs=False, model="GigaChat-2-Pro")

# ============================================================
# Загрузка уроков
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "lessons.json"), "r", encoding="utf-8") as f:
    LESSONS = {lesson["id"]: lesson for lesson in json.load(f)}

# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

     # Убираем старые задачи, если пользователь запускает /start повторно
    for job in context.job_queue.get_jobs_by_name(f"morning_{chat_id}"):
        job.schedule_removal()
    for job in context.job_queue.get_jobs_by_name(f"evening_{chat_id}"):
        job.schedule_removal()

    # Утреннее напоминание в 11:00 МСК (08:00 UTC)
    context.job_queue.run_daily(
        morning_reminder,
        time=datetime.time(8, 0),
        chat_id=chat_id,
        name=f"morning_{chat_id}",
    )

    await update.message.reply_text(
        "👋 Привет! Я бот для изучения Python.\n\n"
        "🔔 Я буду напоминать тебе утром (11:00) и вечером (23:00).\n"
        "📝 Отправь мне ответ на задание в формате:\n"
        "   задание 1 print('Hello')\n"
        "и я проверю его через AI."
    )

# ============================================================
# Напоминания
# ============================================================
async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="☀️ Доброе утро! Самое время открыть сайт и пройти новый урок Python.",
    )

async def evening_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="🌙 Вечернее напоминание: не забудь выполнить задание и отправить его мне "
             "в формате 'задание 1 ...'.",
    )

# ============================================================
# Проверка заданий
# ============================================================
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    if not user_text.lower().startswith("задание"):
        await update.message.reply_text(
            "Пожалуйста, отправь ответ в формате:\n"
            "задание 1 print('Hello')"
        )
        return

    try:
        parts = user_text.split(maxsplit=2)
        lesson_id = int(parts[1])
        user_answer = parts[2] if len(parts) > 2 else ""
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Не понял номер задания. Формат: задание 1 <твой ответ>"
        )
        return

    lesson = LESSONS.get(lesson_id)
    if not lesson:
        await update.message.reply_text(
            f"Задание №{lesson_id} не найдено. Проверь номер на сайте."
        )
        return

    if not user_answer.strip():
        await update.message.reply_text(
            "Ты не прислал ответ. Формат: задание 1 print('Hello')"
        )
        return

    await update.message.reply_text("🤖 Проверяю твой ответ...")

    prompt = (
        "Ты — строгий, но справедливый проверяющий заданий по Python.\n"
        "Твоя задача — сравнить ответ ученика с эталоном ПО СМЫСЛУ.\n\n"
        "УСЛОВИЕ ЗАДАНИЯ:\n" + lesson["task"] + "\n\n"
        "ЭТАЛОННЫЙ ОТВЕТ:\n" + lesson["expected"] + "\n\n"
        "ПОДСКАЗКА:\n" + lesson["check_hint"] + "\n\n"
        "ОТВЕТ УЧЕНИКА:\n" + user_answer + "\n\n"
        "ПРАВИЛА ПРОВЕРКИ:\n"
        "1. Если ответ ученика делает то же, что эталон — считай его ПРАВИЛЬНЫМ,\n"
        "   даже если кавычки, пробелы или порядок строк отличаются.\n"
        "   Одинарные и двойные кавычки в Python РАВНОЗНАЧНЫ — это НЕ ошибка.\n"
        "2. НЕ придумывай ошибок, которых нет. Если сомневаешься — считай верным.\n"
        "3. Если ответ действительно неверный — укажи ОДНУ конкретную проблему.\n"
        "4. Не показывай эталонный ответ целиком.\n"
        "5. Отвечай на русском, кратко, не более 100 слов.\n\n"
        "ФОРМАТ ОТВЕТА:\n"
        "- Начни с «✅ Верно!» или «❌ Есть ошибка.»\n"
        "- Затем 1–2 предложения пояснения.\n"
        f"- Если верно — добавь: «Переходи к уроку {lesson_id + 1}»."
    )

    try:
        response = giga.chat(prompt)
        await update.message.reply_text(
            "📝 Результат:\n\n" + response.choices[0].message.content
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка при обращении к AI: {e}")

# ============================================================
# Flask для Render (health-check)
# ============================================================
web = Flask(__name__)

@web.route('/')
def home():
    return 'Bot is running'

@web.route('/health')
def health():
    return 'OK'

# ============================================================
# Запуск бота в фоновом потоке
# ============================================================
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    print("Bot started in background thread")
    app.run_polling(stop_signals=None)

# ============================================================
# Точка входа — ОДНА
# ============================================================
if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 10000))
    web.run(host='0.0.0.0', port=port)