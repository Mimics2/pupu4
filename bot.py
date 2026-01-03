import os
import sys
import logging
import traceback
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    ApplicationBuilder
)

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
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
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Настраиваем root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console_handler],
    force=True  # Перезаписываем существующие обработчики
)

logger = logging.getLogger(__name__)
logger.info("=" * 80)
logger.info(f"🚀 ЗАПУСК ОТЛАДОЧНОГО БОТА - {datetime.now()}")
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
        user_info = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'language_code': user.language_code,
            'is_bot': user.is_bot
        }
        logger.info(f"📊 Данные пользователя: {user_info}")
        
        # Шаг 2: Проверяем чат
        chat = update.effective_chat
        chat_info = {
            'id': chat.id,
            'type': chat.type,
            'title': getattr(chat, 'title', None)
        }
        logger.info(f"💬 Данные чата: {chat_info}")
        
        # Шаг 3: Пытаемся отправить тестовое сообщение
        logger.info("🔄 Попытка отправки тестового сообщения...")
        test_message = await update.message.reply_text("🔄 Отправка тестового сообщения...")
        logger.info(f"✅ Тестовое сообщение отправлено, ID: {test_message.message_id}")
        
        # Шаг 4: Отправляем основное сообщение
        main_text = f"""
✅ БОТ РАБОТАЕТ! 

📊 <b>Информация о сессии:</b>
👤 <b>Пользователь:</b> {user.first_name}
🆔 <b>ID:</b> <code>{user.id}</code>
📝 <b>Сообщение ID:</b> {update.message.message_id}
⏰ <b>Время:</b> {update.message.date.strftime('%H:%M:%S')}

🚀 <b>Тестовые команды:</b>
• /test - Простой тест
• /error - Тест ошибки
• /buttons - Тест кнопок
• /photo - Тест фото

📋 <b>Для проверки введите:</b>
<code>/test</code>
"""
        
        logger.info("🔄 Попытка отправки основного сообщения...")
        main_message = await update.message.reply_text(main_text, parse_mode='HTML')
        logger.info(f"✅ Основное сообщение отправлено, ID: {main_message.message_id}")
        
        # Шаг 5: Логируем успех
        logger.info("🎉 КОМАНДА /start ВЫПОЛНЕНА УСПЕШНО!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА В /start: {e}")
        logger.error(f"Трассировка:\n{traceback.format_exc()}")
        
        # Пытаемся отправить сообщение об ошибке
        try:
            await update.message.reply_text(
                f"❌ ОШИБКА В /start:\n"
                f"{str(e)[:300]}"
            )
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")

@debug_log
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда"""
    logger.info("🧪 Вызвана команда /test")
    
    try:
        # Проверяем разные типы сообщений
        await update.message.reply_text("✅ Тест 1: Простой текст")
        
        # Тест с разметкой
        await update.message.reply_text(
            "<b>✅ Тест 2:</b> HTML разметка\n"
            "<i>Курсив</i>\n"
            "<code>Моноширинный</code>",
            parse_mode='HTML'
        )
        
        # Тест с упоминанием
        await update.message.reply_text(
            f"✅ Тест 3: Упоминание пользователя\n"
            f"Привет, {update.effective_user.first_name}!",
            parse_mode='HTML'
        )
        
        logger.info("🎯 Все тесты пройдены успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")

@debug_log
async def error_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тест обработки ошибок"""
    logger.warning("⚠️ Вызван тест ошибок /error")
    
    try:
        # Намеренная ошибка
        raise ValueError("Это тестовая ошибка для проверки обработки")
        
    except Exception as e:
        logger.error(f"✅ Ошибка поймана: {e}")
        await update.message.reply_text(f"✅ Ошибка обработана: {e}")

@debug_log
async def buttons_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тест кнопок"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    logger.info("🔘 Тест кнопок")
    
    keyboard = [
        [InlineKeyboardButton("Кнопка 1", callback_data="test_1")],
        [InlineKeyboardButton("Кнопка 2", callback_data="test_2")],
        [InlineKeyboardButton("Кнопка 3", url="https://google.com")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔘 Тест инлайн-кнопок:\n\n"
        "Нажмите любую кнопку",
        reply_markup=reply_markup
    )

@debug_log
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback от кнопок"""
    query = update.callback_query
    await query.answer()
    
    logger.info(f"🔄 Callback получен: {query.data}")
    await query.edit_message_text(f"Вы нажали: {query.data}")

@debug_log
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text
    logger.info(f"📨 Получен текст: '{text}' от {update.effective_user.id}")
    
    await update.message.reply_text(f"📝 Вы написали: {text}")

@debug_log
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото"""
    logger.info(f"📸 Получено фото от {update.effective_user.id}")
    await update.message.reply_text("✅ Фото получено!")

@debug_log
async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error("🔥 ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ВЫЗВАН")
    logger.error(f"Ошибка: {context.error}")
    logger.error(f"Тип ошибки: {type(context.error)}")
    logger.error(f"Трассировка:\n{''.join(traceback.format_tb(context.error.__traceback__))}")
    
    # Логируем Update если есть
    if update:
        logger.error(f"Update: {update}")
        if update.effective_user:
            logger.error(f"Пользователь: {update.effective_user.id}")
    
    # Пытаемся сообщить пользователю
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка в боте. Администратор уведомлен."
            )
    except:
        logger.error("Не удалось отправить сообщение об ошибке")

# ========== ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ ==========
async def init_bot():
    """Инициализация бота с максимальной диагностикой"""
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
        application.add_handler(CommandHandler("error", error_test))
        application.add_handler(CommandHandler("buttons", buttons_test))
        application.add_handler(CommandHandler("photo", lambda u, c: u.message.reply_text("Используйте /test для теста фото")))
        
        # Callback handler
        application.add_handler(CallbackQueryHandler(callback_handler))
        
        # Text handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        # Photo handler
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
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
        
        # Записываем выполненные шаги
        logger.critical("Выполненные шаги:")
        for step in steps:
            logger.critical(f"  {step}")
        
        raise

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def main():
    """Основная функция запуска"""
    logger.info("🚀 ЗАПУСК ОТЛАДОЧНОГО БОТА С МАКСИМАЛЬНОЙ ДИАГНОСТИКОЙ")
    logger.info(f"📁 Логи сохраняются в: {log_filename}")
    
    try:
        # Инициализация
        application = await init_bot()
        
        # Запуск polling
        logger.info("🔄 Запуск polling...")
        logger.info("=" * 80)
        logger.info("🤖 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
        logger.info("📝 Отправьте /start в Telegram для проверки")
        logger.info("=" * 80)
        
        # Запускаем polling с обработкой ошибок
        await application.updater.start_polling(
            drop_pending_updates=True,
            timeout=30,
            poll_interval=0.5,
            allowed_updates=None
        )
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"💥 КРИТИЧЕСКАЯ ОШИБКА В MAIN: {e}")
        logger.critical(f"Трассировка:\n{traceback.format_exc()}")
    finally:
        try:
            await application.stop()
        except:
            pass
        logger.info("📁 Файл логов: " + log_filename)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
