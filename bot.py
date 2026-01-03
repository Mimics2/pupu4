import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Включаем ВСЕ логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # ИЗМЕНИЛИ НА DEBUG!
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8569312600:AAGiuvWLi2n84SYahF_pyye94xFqKgNl2IU"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ПРОСТАЯ команда start"""
    logger.info(f"=== START COMMAND CALLED ===")
    logger.info(f"User ID: {update.effective_user.id}")
    logger.info(f"Username: {update.effective_user.username}")
    logger.info(f"First name: {update.effective_user.first_name}")
    
    try:
        await update.message.reply_text(
            "✅ БОТ РАБОТАЕТ!\n"
            "Тестовая версия бота.\n\n"
            "Команды:\n"
            "/start - это сообщение\n"
            "/test - тестовая команда\n"
            "/ping - проверка связи"
        )
        logger.info("=== START COMMAND SUCCESS ===")
    except Exception as e:
        logger.error(f"=== START COMMAND FAILED: {e} ===")

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда"""
    logger.info(f"=== TEST COMMAND CALLED ===")
    await update.message.reply_text("✅ Тест выполнен успешно!")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка связи"""
    logger.info(f"=== PING COMMAND CALLED ===")
    await update.message.reply_text("🏓 Понг! Бот жив!")

def main():
    """Простой запуск"""
    print("=" * 60)
    print("🚀 DEBUG BOT STARTING...")
    print(f"TOKEN: {BOT_TOKEN}")
    print("=" * 60)
    
    try:
        # Создаем приложение
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем ТОЛЬКО 3 команды
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("test", test))
        app.add_handler(CommandHandler("ping", ping))
        
        print("✅ Bot handlers added")
        print("🚀 Starting polling...")
        
        # Запускаем polling
        app.run_polling(
            drop_pending_updates=True,
            timeout=30,
            poll_interval=1.0
        )
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
