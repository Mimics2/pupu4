import os
import sys
import logging
import traceback
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    ApplicationBuilder,
    CallbackQueryHandler  # <-- ДОБАВИЛИ ЭТО!
)

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
# Принудительно настраиваем UTF-8
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Создаем кастомный форматтер для детальных логов
class DetailedFormatter(logging.Formatter):
    def format(self, record):
        result = super().format(record)
        if record.exc_info:
            result += '\n' + traceback.format_exc()
        return result

# Настраиваем логирование в файл и консоль
log_filename = f"bot_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Логи в файл
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = DetailedFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)
file_handler.setFormatter(file_formatter)

# Логи в консоль
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)  # ИЗМЕНИЛИ НА DEBUG!
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Настраиваем root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.handlers = []  # Очищаем старые обработчики
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Логируем запуск
logger = logging.getLogger(__name__)
logger.info("=" * 80)
logger.info(f"🚀 ЗАПУСК БОТА - {datetime.now()}")
logger.info(f"📁 Файл логов: {log_filename}")
logger.info("=" * 80)

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8569312600:AAGiuvWLi2n84SYahF_pyye94xFqKgNl2IU"
logger.info(f"Используется токен: {BOT_TOKEN[:10]}...")

# ========== ДЕКОРАТОР ДЛЯ ОТЛАДКИ ==========
def debug_log(func):
    """Декоратор для логирования вызовов функций"""
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"▶️ ВХОД В ФУНКЦИЮ: {func_name}")
        
        try:
            # Логируем аргументы
            if args:
                for i, arg in enumerate(args):
                    if isinstance(arg, Update):
                        logger.debug(f"  Аргумент {i}: Update object")
                        if arg.effective_user:
                            logger.debug(f"    User: {arg.effective_user.id}")
                        if arg.message:
                            logger.debug(f"    Message ID: {arg.message.message_id}")
                    else:
                        logger.debug(f"  Аргумент {i}: {type(arg).__name__}")
            
            # Вызываем функцию
            result = await func(*args, **kwargs)
            
            logger.debug(f"✅ ФУНКЦИЯ ВЫПОЛНЕНА: {func_name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ ОШИБКА В ФУНКЦИИ {func_name}: {e}")
            logger.error(f"Трассировка ошибки:\n{traceback.format_exc()}")
            
            # Пытаемся отправить сообщение об ошибке пользователю
            try:
                update = args[0] if args else None
                if update and isinstance(update, Update) and update.message:
                    await update.message.reply_text(
                        f"⚠️ Произошла ошибка в функции {func_name}:\n"
                        f"{str(e)[:200]}"
                    )
            except:
                logger.error("Не удалось отправить сообщение об ошибке пользователю")
            
            raise
    
    return wrapper

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@debug_log
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    logger.info("=" * 60)
    logger.info(f"🚨 КОМАНДА /start ВЫЗВАНА!")
    logger.info(f"👤 Пользователь: {update.effective_user.id}")
    logger.info(f"📝 Сообщение ID: {update.message.message_id}")
    logger.info(f"⏰ Время: {update.message.date}")
    
    try:
        # Шаг 1: Проверяем данные пользователя
        user = update.effective_user
        logger.info(f"📊 Пользователь: {user.first_name} (ID: {user.id})")
        
        # Шаг 2: Отправляем простое сообщение
        logger.info("🔄 Попытка отправки сообщения...")
        
        response = await update.message.reply_text(
            "✅ БОТ РАБОТАЕТ!\n\n"
            f"Привет, {user.first_name}!\n"
            f"Твой ID: {user.id}\n\n"
            "Тестовые команды:\n"
            "/test - простой тест\n"
            "/ping - проверка связи\n"
            "/debug - отладочная информация"
        )
        
        logger.info(f"✅ Сообщение отправлено! ID: {response.message_id}")
        logger.info("🎉 КОМАНДА /start ВЫПОЛНЕНА УСПЕШНО!")
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА В /start: {e}")
        logger.error(f"Трассировка:\n{traceback.format_exc()}")

@debug_log
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда"""
    logger.info("🧪 Вызвана команда /test")
    await update.message.reply_text("✅ Тест выполнен успешно!")

@debug_log
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка связи"""
    logger.info("🏓 Вызвана команда /ping")
    await update.message.reply_text("🏓 Понг! Бот жив!")

@debug_log
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отладочная информация"""
    logger.info("🔧 Вызвана команда /debug")
    
    import psutil
    import platform
    
    # Информация о системе
    system_info = f"""
🖥️ Системная информация:
ОС: {platform.system()} {platform.release()}
Python: {platform.python_version()}
Память: {psutil.virtual_memory().percent}% использовано
CPU: {psutil.cpu_percent()}% загружен
"""
    
    await update.message.reply_text(
        f"📊 Отладочная информация:\n\n"
        f"{system_info}\n"
        f"👤 Пользователь ID: {update.effective_user.id}\n"
        f"💬 Чат ID: {update.effective_chat.id}"
    )

@debug_log
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text
    logger.info(f"📨 Получен текст: '{text}' от {update.effective_user.id}")
    await update.message.reply_text(f"📝 Вы написали: {text}")

@debug_log
async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error("🔥 ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ВЫЗВАН")
    logger.error(f"Ошибка: {context.error}")
    
    if update:
        logger.error(f"Update ID: {update.update_id if update.update_id else 'N/A'}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ Произошла ошибка в боте.")
    except:
        pass

# ========== ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ ==========
async def init_bot():
    """Инициализация бота"""
    logger.info("🔧 НАЧАЛО ИНИЦИАЛИЗАЦИИ БОТА")
    
    steps = []
    
    try:
        # Шаг 1: Проверка токена
        logger.info("🔄 Шаг 1: Проверка токена...")
        if not BOT_TOKEN or len(BOT_TOKEN) < 30:
            raise ValueError(f"Неверный токен: {BOT_TOKEN}")
        steps.append("✅ Токен проверен")
        
        # Шаг 2: Создание Application
        logger.info("🔄 Шаг 2: Создание Application...")
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        steps.append("✅ Application создан")
        
        # Шаг 3: Добавление обработчиков
        logger.info("🔄 Шаг 3: Добавление обработчиков...")
        
        # Основные команды
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("test", test))
        application.add_handler(CommandHandler("ping", ping))
        application.add_handler(CommandHandler("debug", debug))
        
        # Text handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        # Error handler
        application.add_error_handler(handle_error)
        
        steps.append("✅ Обработчики добавлены")
        
        # Шаг 4: Инициализация
        logger.info("🔄 Шаг 4: Инициализация приложения...")
        await application.initialize()
        steps.append("✅ Приложение инициализировано")
        
        # Шаг 5: Старт
        logger.info("🔄 Шаг 5: Запуск приложения...")
        await application.start()
        steps.append("✅ Приложение запущено")
        
        # Шаг 6: Проверка бота
        logger.info("🔄 Шаг 6: Проверка бота...")
        bot = application.bot
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот: @{bot_info.username} ({bot_info.first_name})")
        steps.append(f"✅ Бот проверен: @{bot_info.username}")
        
        # Шаг 7: Удаление старых webhook
        logger.info("🔄 Шаг 7: Очистка webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        steps.append("✅ Webhook очищен")
        
        logger.info("🎉 БОТ УСПЕШНО ИНИЦИАЛИЗИРОВАН!")
        logger.info("=" * 80)
        
        for step in steps:
            logger.info(step)
        
        return application
        
    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ИНИЦИАЛИЗАЦИИ: {e}")
        logger.critical(f"Трассировка:\n{traceback.format_exc()}")
        
        logger.critical("Выполненные шаги:")
        for step in steps:
            logger.critical(f"  {step}")
        
        raise

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def main():
    """Основная функция запуска"""
    logger.info("🚀 ЗАПУСК БОТА")
    
    try:
        # Инициализация
        application = await init_bot()
        
        # Запуск polling
        logger.info("🔄 Запуск polling...")
        logger.info("=" * 80)
        logger.info("🤖 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
        logger.info("📝 Отправьте /start в Telegram для проверки")
        logger.info("=" * 80)
        
        # Запускаем polling
        await application.updater.start_polling(
            drop_pending_updates=True,
            timeout=30,
            poll_interval=1.0
        )
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.critical(f"Трассировка:\n{traceback.format_exc()}")
    finally:
        logger.info("📁 Файл логов: " + log_filename)

if __name__ == "__main__":
    # Запускаем asyncio
    asyncio.run(main())
