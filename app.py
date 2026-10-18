import os
import threading
from flask import Flask

# ... весь ваш код из bot.py (импорты, функции, LESSONS) ...

# Flask-приложение для Render
web = Flask(__name__)

@web.route('/')
def home():
    return 'Bot is running'

@web.route('/health')
def health():
    return 'OK'

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    print("Bot started in background thread")
    app.run_polling()

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    threading.Thread(target=run_bot, daemon=True).start()
    # Flask слушает порт, который даёт Render
    port = int(os.environ.get('PORT', 10000))
    web.run(host='0.0.0.0', port=port)
