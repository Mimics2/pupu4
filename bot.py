import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from enum import Enum

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, InputMediaPhoto, InputMediaVideo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from database import Database

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv('BOT_TOKEN', '8569312600:AAGiuvWLi2n84SYahF_pyye94xFqKgNl2IU')
ADMIN_ID = int(os.getenv('ADMIN_ID', '6646433980'))
PORT = int(os.getenv('PORT', '8000'))

# Состояния для ConversationHandler
class States(Enum):
    AWAITING_CONTENT = 1
    AWAITING_TIME = 2
    AWAITING_CUSTOM_TIME = 3
    ADMIN_SET_PRICE = 4
    ADMIN_ADD_CHANNEL = 5

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database("scheduler.db")

# ========== ОСНОВНОЙ КЛАСС БОТА ==========
class SchedulerBot:
    def __init__(self):
        self.application = None
        self.scheduler = AsyncIOScheduler()
        self.user_states = {}  # Временное хранилище состояний
        
    async def setup(self):
        """Настройка бота"""
        logger.info("🚀 Инициализация бота...")
        
        # Инициализация базы данных
        await db.init_db()
        
        # Создание приложения
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Настройка обработчиков
        self.setup_handlers()
        
        # Инициализация приложения
        await self.application.initialize()
        await self.application.start()
        
        # Запуск планировщика
        self.scheduler.start()
        
        # Запуск фоновых задач
        asyncio.create_task(self.background_tasks())
        
        logger.info("✅ Бот инициализирован")
        
    def setup_handlers(self):
        """Настройка обработчиков"""
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        
        # Планирование постов
        self.application.add_handler(CommandHandler("schedule", self.schedule_command))
        self.application.add_handler(CommandHandler("posts", self.posts_command))
        
        # Управление каналами
        self.application.add_handler(CommandHandler("channels", self.channels_command))
        self.application.add_handler(CommandHandler("addchannel", self.add_channel_command))
        
        # Тарифы и оплата
        self.application.add_handler(CommandHandler("tariffs", self.tariffs_command))
        self.application.add_handler(CommandHandler("buy", self.buy_command))
        
        # Админ команды
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("export", self.export_command))
        
        # Обработчики callback запросов
        self.application.add_handler(CallbackQueryHandler(self.callback_handler))
        
        # Обработчики сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.text_message_handler
        ))
        self.application.add_handler(MessageHandler(
            filters.PHOTO | filters.VIDEO,
            self.media_message_handler
        ))
        
        # Обработчик пересланных сообщений для добавления каналов
        self.application.add_handler(MessageHandler(
            filters.FORWARDED,
            self.forwarded_message_handler
        ))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
        
    # ========== КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ==========
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        await db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        welcome_text = f"""
🎉 <b>Добро пожаловать, {user.first_name}!</b>

🤖 <b>Я бот для планирования публикаций в Telegram каналах</b>

✨ <b>Основные возможности:</b>
• 📅 Планирование постов на любое время
• 📢 Управление несколькими каналами
• 💎 Гибкая тарифная система
• 👑 Удобная админ-панель

💡 <b>Для начала работы:</b>
1. Добавьте каналы командой /channels
2. Выберите тариф командой /tariffs
3. Планируйте посты командой /schedule

👇 <b>Используйте меню ниже:</b>
"""
        
        keyboard = [
            [InlineKeyboardButton("📅 Запланировать пост", callback_data="schedule")],
            [InlineKeyboardButton("📢 Мои каналы", callback_data="channels")],
            [InlineKeyboardButton("💎 Тарифы", callback_data="tariffs")],
            [InlineKeyboardButton("📋 Помощь", callback_data="help")]
        ]
        
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 Админ панель", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        help_text = """
<b>🤖 ПОМОЩЬ ПО БОТУ</b>

<b>📋 Основные команды:</b>
/start - Начать работу
/menu - Главное меню
/help - Эта справка

<b>📅 Планирование:</b>
/schedule - Запланировать новый пост
/posts - Мои запланированные посты

<b>📢 Каналы:</b>
/channels - Мои каналы
/addchannel - Добавить канал

<b>💎 Тарифы:</b>
/tariffs - Просмотр тарифов
/buy [тариф] - Купить тариф

<b>👑 Админ команды:</b>
/admin - Админ панель
/stats - Статистика
/export - Экспорт пользователей

<b>⏰ Формат времени:</b>
<code>ГГГГ.ММ.ДД ЧЧ:ММ</code>
<b>Пример:</b> <code>2025.12.31 15:30</code>

<b>🚀 Быстрый старт:</b>
1. Добавьте канал командой /addchannel
2. Выберите тариф командой /tariffs
3. Запланируйте пост командой /schedule
"""
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
        
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню"""
        keyboard = [
            [InlineKeyboardButton("📅 Запланировать пост", callback_data="schedule")],
            [InlineKeyboardButton("📢 Мои каналы", callback_data="channels")],
            [InlineKeyboardButton("💎 Тарифы", callback_data="tariffs")],
            [InlineKeyboardButton("📋 Помощь", callback_data="help")]
        ]
        
        if update.effective_user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 Админ панель", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📱 <b>Главное меню</b>\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
    # ========== ПЛАНИРОВАНИЕ ПОСТОВ ==========
    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать планирование поста"""
        user_id = update.effective_user.id
        
        # Проверяем лимит постов
        can_post, message = await db.check_post_limit(user_id)
        if not can_post:
            await update.message.reply_text(f"❌ {message}")
            return
            
        # Проверяем наличие каналов
        channels = await db.get_user_channels(user_id)
        if not channels:
            await update.message.reply_text(
                "📭 У вас нет добавленных каналов.\n\n"
                "Добавьте канал командой /addchannel\n"
                "или через меню 'Мои каналы'"
            )
            return
            
        keyboard = [
            [InlineKeyboardButton("⏰ Через 1 час", callback_data="time_1h")],
            [InlineKeyboardButton("🕐 Через 3 часа", callback_data="time_3h")],
            [InlineKeyboardButton("🕒 Через 6 часов", callback_data="time_6h")],
            [InlineKeyboardButton("📅 Выбрать своё время", callback_data="time_custom")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📅 <b>Выберите время публикации:</b>\n\n"
            "Или отправьте время в формате:\n"
            "<code>ГГГГ.ММ.ДД ЧЧ:ММ</code>\n\n"
            "<b>Пример:</b> <code>2025.12.31 15:30</code>",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
    async def posts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать запланированные посты"""
        user_id = update.effective_user.id
        posts = await db.get_user_posts(user_id, limit=10)
        
        if not posts:
            await update.message.reply_text("📭 У вас нет запланированных постов.")
            return
            
        text = "📋 <b>Ваши запланированные посты:</b>\n\n"
        
        for post in posts:
            post_time = datetime.fromisoformat(post['scheduled_time'])
            status_emoji = "⏳" if post['status'] == 'pending' else "✅" if post['status'] == 'published' else "❌"
            
            text += f"{status_emoji} <b>ID:</b> {post['id']}\n"
            text += f"   <b>Время:</b> {post_time.strftime('%Y.%m.%d %H:%M')}\n"
            text += f"   <b>Канал:</b> {post['channel_id']}\n"
            text += f"   <b>Статус:</b> {post['status']}\n\n"
            
        keyboard = [[InlineKeyboardButton("📅 Запланировать новый", callback_data="schedule")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    # ========== УПРАВЛЕНИЕ КАНАЛАМИ ==========
    async def channels_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать каналы пользователя"""
        user_id = update.effective_user.id
        channels = await db.get_user_channels(user_id)
        
        if not channels:
            text = "📭 <b>У вас нет добавленных каналов</b>\n\n"
            text += "Чтобы добавить канал:\n"
            text += "1. Перешлите любое сообщение из канала\n"
            text += "2. Или отправьте ссылку на канал\n"
            text += "3. Используйте команду /addchannel"
            
            keyboard = [[InlineKeyboardButton("➕ Добавить канал", callback_data="add_channel")]]
        else:
            user = await db.get_user(user_id)
            tariff_info = await db.get_tariff_info(user['tariff'])
            limit = tariff_info['channels_limit'] if tariff_info else 1
            
            text = f"📢 <b>Ваши каналы</b> ({len(channels)}/{limit})\n\n"
            
            for i, channel in enumerate(channels, 1):
                added_date = datetime.fromisoformat(channel['added_at']).strftime('%d.%m.%Y')
                text += f"{i}. <b>{channel['channel_name']}</b>\n"
                text += f"   ID: <code>{channel['channel_id']}</code>\n"
                text += f"   Добавлен: {added_date}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("➕ Добавить канал", callback_data="add_channel")],
                [InlineKeyboardButton("🗑️ Удалить канал", callback_data="remove_channel")]
            ]
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    async def add_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление канала"""
        await update.message.reply_text(
            "🔗 <b>Добавление канала</b>\n\n"
            "Чтобы добавить канал:\n"
            "1. <b>Перешлите любое сообщение</b> из канала\n"
            "2. <b>Или отправьте ссылку</b> на канал\n"
            "   Пример: https://t.me/channelname\n\n"
            "Для отмены отправьте /cancel",
            parse_mode=ParseMode.HTML
        )
        
    async def forwarded_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка пересланных сообщений для добавления каналов"""
        if not update.message.forward_from_chat:
            return
            
        chat = update.message.forward_from_chat
        
        if chat.type not in ['channel', 'group']:
            await update.message.reply_text("❌ Можно добавить только каналы и группы.")
            return
            
        user_id = update.effective_user.id
        channel_id = f"@{chat.username}" if chat.username else str(chat.id)
        
        success, message = await db.add_user_channel(user_id, channel_id, chat.title)
        
        if success:
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
            
    # ========== ТАРИФЫ И ОПЛАТА ==========
    async def tariffs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать тарифы"""
        user_id = update.effective_user.id
        user = await db.get_user(user_id)
        tariffs = await db.get_all_tariffs()
        
        text = "💎 <b>Доступные тарифы:</b>\n\n"
        
        for tariff in tariffs:
            current = " (текущий)" if user and user['tariff'] == tariff['tariff_name'] else ""
            
            text += f"<b>{tariff['tariff_name'].upper()}{current}</b>\n"
            text += f"💰 Цена: {tariff['price']} звёзд\n"
            text += f"📢 Каналов: {tariff['channels_limit']}\n"
            text += f"📊 Постов в день: {tariff['posts_per_day']}\n"
            text += f"📅 Длительность: {tariff['duration_days']} дней\n\n"
        
        keyboard = []
        for tariff in tariffs:
            keyboard.append([
                InlineKeyboardButton(
                    f"Купить {tariff['tariff_name'].upper()} - {tariff['price']} звёзд",
                    callback_data=f"buy_{tariff['tariff_name']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Покупка тарифа"""
        if not context.args:
            await update.message.reply_text(
                "💎 <b>Покупка тарифа</b>\n\n"
                "Используйте: /buy [тариф]\n"
                "Пример: /buy premium\n\n"
                "Доступные тарифы: basic, premium, vip\n\n"
                "Для просмотра тарифов используйте /tariffs",
                parse_mode=ParseMode.HTML
            )
            return
            
        tariff_name = context.args[0].lower()
        tariff_info = await db.get_tariff_info(tariff_name)
        
        if not tariff_info:
            await update.message.reply_text(f"❌ Тариф '{tariff_name}' не найден.")
            return
            
        user_id = update.effective_user.id
        
        # Здесь должна быть логика оплаты
        # В демо-версии просто активируем тариф
        
        success = await db.update_user_tariff(user_id, tariff_name)
        
        if success:
            # Добавляем запись о платеже
            await db.add_payment(user_id, tariff_name, tariff_info['price'])
            
            # Получаем приватный канал для тарифа
            private_channel = await db.get_private_channel(tariff_name)
            
            if private_channel:
                text = f"""
✅ <b>Тариф успешно активирован!</b>

💎 <b>Тариф:</b> {tariff_name.upper()}
💰 <b>Стоимость:</b> {tariff_info['price']} звёзд
📅 <b>Действует:</b> {tariff_info['duration_days']} дней

🔗 <b>Приватный канал:</b>
{private_channel['invite_link']}

⚠️ <b>Внимание:</b> доступ к каналу будет отозван через 2 часа, если вы не войдете самостоятельно.
"""
                
                # Планируем удаление через 2 часа
                await self.schedule_channel_kick(user_id, private_channel['channel_id'])
            else:
                text = f"""
✅ <b>Тариф успешно активирован!</b>

💎 <b>Тариф:</b> {tariff_name.upper()}
💰 <b>Стоимость:</b> {tariff_info['price']} звёзд
📅 <b>Действует:</b> {tariff_info['duration_days']} дней

⚠️ <b>Примечание:</b> приватный канал для этого тарифа еще не настроен.
"""
            
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Ошибка при активации тарифа.")
            
    async def schedule_channel_kick(self, user_id: int, channel_id: str):
        """Планирование удаления пользователя из канала"""
        
        async def kick_user():
            try:
                bot = self.application.bot
                await bot.ban_chat_member(channel_id, user_id)
                await bot.unban_chat_member(channel_id, user_id)
                logger.info(f"User {user_id} kicked from channel {channel_id}")
            except Exception as e:
                logger.error(f"Failed to kick user {user_id}: {e}")
        
        kick_time = datetime.now() + timedelta(hours=2)
        self.scheduler.add_job(
            kick_user,
            DateTrigger(run_date=kick_time),
            id=f"kick_{user_id}_{channel_id}"
        )
        
    # ========== АДМИН КОМАНДЫ ==========
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админ панель"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Доступ запрещен.")
            return
            
        stats = await db.get_statistics()
        
        text = f"""
👑 <b>АДМИН ПАНЕЛЬ</b>

📊 <b>Статистика:</b>
👥 Пользователей: {stats['total_users']}
💰 Общая прибыль: {stats['total_revenue']} звёзд
📅 Ожидающих публикаций: {stats['pending_posts']}
🔥 Активных пользователей (7 дней): {stats['active_users']}

<b>Пользователи по тарифам:</b>
"""
        
        for tariff, count in stats['tariff_stats'].items():
            text += f"  {tariff}: {count}\n"
        
        keyboard = [
            [InlineKeyboardButton("📊 Подробная статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
            [InlineKeyboardButton("💰 Изменить цены", callback_data="admin_prices")],
            [InlineKeyboardButton("🔗 Управление каналами", callback_data="admin_channels")],
            [InlineKeyboardButton("📦 Экспорт данных", callback_data="admin_export")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подробная статистика"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Доступ запрещен.")
            return
            
        stats = await db.get_statistics()
        users = await db.get_all_users(limit=10)
        
        text = f"""
📈 <b>ПОДРОБНАЯ СТАТИСТИКА</b>

<b>Общая статистика:</b>
👥 Всего пользователей: {stats['total_users']}
💰 Общая прибыль: {stats['total_revenue']} звёзд
📅 Ожидающих публикаций: {stats['pending_posts']}
🔥 Активных пользователей: {stats['active_users']}

<b>Распределение по тарифам:</b>
"""
        
        for tariff, count in stats['tariff_stats'].items():
            percentage = (count / stats['total_users'] * 100) if stats['total_users'] > 0 else 0
            text += f"  {tariff}: {count} ({percentage:.1f}%)\n"
        
        text += f"\n<b>Последние 10 регистраций:</b>\n"
        for user in users[:10]:
            reg_date = datetime.fromisoformat(user['registered_at']).strftime('%d.%m.%Y')
            text += f"  {user['user_id']} - {user['first_name']} ({reg_date})\n"
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        
    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Экспорт пользователей"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Доступ запрещен.")
            return
            
        csv_data = await db.export_users_csv()
        
        await update.message.reply_document(
            document=csv_data.encode('utf-8'),
            filename="users_export.csv",
            caption="📦 Экспорт пользователей"
        )
        
    # ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========
    async def text_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Проверяем, не является ли это временем для планирования
        if self.is_valid_time_format(text):
            await self.handle_time_input(update, text)
            return
            
        # Проверяем, не является ли это ссылкой на канал
        if text.startswith("https://t.me/"):
            await self.handle_channel_link(update, text)
            return
            
        # Проверяем состояние пользователя
        if user_id in self.user_states:
            await self.handle_user_state(update, text)
            return
            
        # Обычное сообщение
        await update.message.reply_text(
            f"📝 Вы написали: {text}\n\n"
            f"Используйте /help для списка команд."
        )
        
    async def media_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка медиа сообщений"""
        user_id = update.effective_user.id
        
        if user_id in self.user_states and self.user_states[user_id].get('state') == 'waiting_for_content':
            await self.handle_content_input(update)
            return
            
        await update.message.reply_text(
            "📸 Медиа получено!\n"
            "Для планирования поста используйте /schedule"
        )
        
    # ========== ОБРАБОТЧИК CALLBACK ==========
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback запросов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        # Основные действия
        if data == "menu":
            await self.menu_command(query.message, context)
        elif data == "help":
            await self.help_command(query.message, context)
        elif data == "schedule":
            await self.schedule_command(query.message, context)
        elif data == "channels":
            await self.channels_command(query.message, context)
        elif data == "tariffs":
            await self.tariffs_command(query.message, context)
        elif data == "add_channel":
            await self.add_channel_command(query.message, context)
            
        # Время для планирования
        elif data.startswith("time_"):
            await self.handle_time_selection(query, data)
            
        # Покупка тарифа
        elif data.startswith("buy_"):
            await self.handle_tariff_purchase(query, data)
            
        # Админ действия
        elif data.startswith("admin_"):
            await self.handle_admin_action(query, data)
            
    async def handle_time_selection(self, query, data: str):
        """Обработка выбора времени"""
        user_id = query.from_user.id
        
        if data == "time_1h":
            schedule_time = datetime.now() + timedelta(hours=1)
        elif data == "time_3h":
            schedule_time = datetime.now() + timedelta(hours=3)
        elif data == "time_6h":
            schedule_time = datetime.now() + timedelta(hours=6)
        elif data == "time_custom":
            await query.edit_message_text(
                "⏰ <b>Введите время публикации:</b>\n\n"
                "Формат: <code>ГГГГ.ММ.ДД ЧЧ:ММ</code>\n"
                "<b>Пример:</b> <code>2025.12.31 15:30</code>\n\n"
                "Для отмены отправьте /cancel",
                parse_mode=ParseMode.HTML
            )
            return
            
        # Сохраняем время и запрашиваем контент
        self.user_states[user_id] = {
            'state': 'waiting_for_content',
            'schedule_time': schedule_time
        }
        
        await query.edit_message_text(
            f"✅ <b>Время выбрано:</b> {schedule_time.strftime('%Y.%m.%d %H:%M')}\n\n"
            "📝 <b>Теперь отправьте контент для публикации:</b>\n"
            "• Текст сообщения\n"
            "• Фото с подписью\n"
            "• Видео с подписью\n\n"
            "Для отмены отправьте /cancel",
            parse_mode=ParseMode.HTML
        )
        
    async def handle_tariff_purchase(self, query, data: str):
        """Обработка покупки тарифа"""
        tariff_name = data.replace("buy_", "")
        
        # Имитируем команду /buy
        context = ContextTypes.DEFAULT_TYPE
        context.args = [tariff_name]
        
        await self.buy_command(query.message, context)
        
    async def handle_admin_action(self, query, data: str):
        """Обработка админ действий"""
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Доступ запрещен.")
            return
            
        if data == "admin_stats":
            await self.stats_command(query.message, None)
        elif data == "admin_users":
            await self.show_admin_users(query)
        elif data == "admin_prices":
            await self.show_admin_prices(query)
        elif data == "admin_channels":
            await self.show_admin_channels(query)
        elif data == "admin_export":
            await self.export_command(query.message, None)
            
    async def show_admin_users(self, query):
        """Показать пользователей для админа"""
        users = await db.get_all_users(limit=20)
        
        text = "👥 <b>Последние 20 пользователей:</b>\n\n"
        
        for user in users:
            reg_date = datetime.fromisoformat(user['registered_at']).strftime('%d.%m.%Y')
            text += f"<b>ID:</b> {user['user_id']}\n"
            text += f"<b>Имя:</b> {user['first_name']}\n"
            text += f"<b>Тариф:</b> {user['tariff']}\n"
            text += f"<b>Зарегистрирован:</b> {reg_date}\n"
            text += "─" * 20 + "\n"
        
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        
    async def show_admin_prices(self, query):
        """Управление ценами для админа"""
        tariffs = await db.get_all_tariffs()
        
        text = "💰 <b>Управление ценами тарифов</b>\n\n"
        
        keyboard = []
        for tariff in tariffs:
            text += f"<b>{tariff['tariff_name'].upper()}</b>: {tariff['price']} звёзд\n"
            text += f"Каналов: {tariff['channels_limit']} | Постов: {tariff['posts_per_day']}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"Изменить {tariff['tariff_name']}",
                    callback_data=f"edit_price_{tariff['tariff_name']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    async def show_admin_channels(self, query):
        """Управление приватными каналами для админа"""
        tariffs = await db.get_all_tariffs()
        
        text = "🔗 <b>Управление приватными каналами</b>\n\n"
        
        keyboard = []
        for tariff in tariffs:
            private_channel = await db.get_private_channel(tariff['tariff_name'])
            status = "✅ Настроен" if private_channel else "❌ Не настроен"
            
            text += f"<b>{tariff['tariff_name'].upper()}</b>: {status}\n"
            if private_channel:
                text += f"Канал: {private_channel['channel_id']}\n"
            text += "\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{'Изменить' if private_channel else 'Добавить'} {tariff['tariff_name']}",
                    callback_data=f"edit_channel_{tariff['tariff_name']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    def is_valid_time_format(self, text: str) -> bool:
        """Проверка формата времени"""
        try:
            datetime.strptime(text, "%Y.%m.%d %H:%M")
            return True
        except ValueError:
            return False
            
    async def handle_time_input(self, update: Update, time_text: str):
        """Обработка ввода времени"""
        try:
            schedule_time = datetime.strptime(time_text, "%Y.%m.%d %H:%M")
            
            if schedule_time <= datetime.now():
                await update.message.reply_text("❌ Время должно быть в будущем!")
                return
                
            user_id = update.effective_user.id
            self.user_states[user_id] = {
                'state': 'waiting_for_content',
                'schedule_time': schedule_time
            }
            
            await update.message.reply_text(
                f"✅ <b>Время принято:</b> {schedule_time.strftime('%Y.%m.%d %H:%M')}\n\n"
                "📝 <b>Теперь отправьте контент для публикации:</b>\n"
                "• Текст сообщения\n"
                "• Фото с подписью\n"
                "• Видео с подписью\n\n"
                "Для отмены отправьте /cancel",
                parse_mode=ParseMode.HTML
            )
        except:
            await update.message.reply_text(
                "❌ Неверный формат времени!\n\n"
                "Используйте: <code>ГГГГ.ММ.ДД ЧЧ:ММ</code>\n"
                "<b>Пример:</b> <code>2025.12.31 15:30</code>",
                parse_mode=ParseMode.HTML
            )
            
    async def handle_channel_link(self, update: Update, link: str):
        """Обработка ссылки на канал"""
        try:
            # Извлекаем username из ссылки
            username = link.split("/")[-1].replace("@", "")
            channel_id = f"@{username}"
            
            user_id = update.effective_user.id
            
            # Пытаемся получить информацию о канале
            try:
                chat = await self.application.bot.get_chat(channel_id)
                success, message = await db.add_user_channel(user_id, channel_id, chat.title)
                
                if success:
                    await update.message.reply_text(f"✅ {message}")
                else:
                    await update.message.reply_text(f"❌ {message}")
            except:
                await update.message.reply_text(
                    "❌ Не удалось получить информацию о канале.\n\n"
                    "Убедитесь, что:\n"
                    "1. Ссылка правильная\n"
                    "2. Бот добавлен в канал как администратор\n"
                    "3. Вы указали публичный username канала"
                )
        except:
            await update.message.reply_text("❌ Неверный формат ссылки!")
            
    async def handle_user_state(self, update: Update, text: str):
        """Обработка состояния пользователя"""
        user_id = update.effective_user.id
        state = self.user_states[user_id]
        
        if state.get('state') == 'waiting_for_content':
            await self.handle_content_input(update, text)
            
    async def handle_content_input(self, update: Update, text: str = None):
        """Обработка ввода контента"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            await update.message.reply_text("❌ Сессия истекла. Начните заново командой /schedule")
            return
            
        state = self.user_states[user_id]
        schedule_time = state['schedule_time']
        
        # Получаем каналы пользователя
        channels = await db.get_user_channels(user_id)
        if not channels:
            await update.message.reply_text("❌ У вас нет добавленных каналов!")
            del self.user_states[user_id]
            return
            
        # Создаем клавиатуру с каналами
        keyboard = []
        for channel in channels:
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 {channel['channel_name']}",
                    callback_data=f"post_channel_{channel['channel_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Сохраняем контент
        if update.message.photo:
            media_id = update.message.photo[-1].file_id
            content_type = "photo"
            caption = update.message.caption or ""
            
            state['content_type'] = content_type
            state['content'] = caption
            state['media_id'] = media_id
            
            await update.message.reply_text(
                f"📸 <b>Фото получено!</b>\n\n"
                f"Подпись: {caption if caption else 'нет'}\n\n"
                f"<b>Выберите канал для публикации:</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
        elif update.message.video:
            media_id = update.message.video.file_id
            content_type = "video"
            caption = update.message.caption or ""
            
            state['content_type'] = content_type
            state['content'] = caption
            state['media_id'] = media_id
            
            await update.message.reply_text(
                f"🎥 <b>Видео получено!</b>\n\n"
                f"Подпись: {caption if caption else 'нет'}\n\n"
                f"<b>Выберите канал для публикации:</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
        elif text:
            content_type = "text"
            
            state['content_type'] = content_type
            state['content'] = text
            state['media_id'] = None
            
            await update.message.reply_text(
                f"📝 <b>Текст получен!</b>\n\n"
                f"Текст: {text[:100]}...\n\n"
                f"<b>Выберите канал для публикации:</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
    # ========== ОБРАБОТЧИК ОШИБОК ==========
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ошибок"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            if "Conflict" in str(context.error):
                logger.error("КОНФЛИКТ! Запущено несколько экземпляров бота!")
                
                if update and update.effective_message:
                    await update.effective_message.reply_text(
                        "⚠️ <b>Обнаружен конфликт!</b>\n\n"
                        "Запущено несколько экземпляров бота.\n"
                        "Пожалуйста, подождите 30 секунд.\n"
                        "Администратор уже устраняет проблему.",
                        parse_mode=ParseMode.HTML
                    )
            else:
                if update and update.effective_message:
                    await update.effective_message.reply_text(
                        "❌ <b>Произошла ошибка</b>\n\n"
                        "Попробуйте еще раз или обратитесь к администратору.",
                        parse_mode=ParseMode.HTML
                    )
        except:
            pass
            
    # ========== ФОНОВЫЕ ЗАДАЧИ ==========
    async def background_tasks(self):
        """Фоновые задачи"""
        while True:
            try:
                # Проверяем истекшие подписки
                expired_users = await db.check_expired_subscriptions()
                if expired_users:
                    logger.info(f"Обновлены тарифы для {len(expired_users)} пользователей")
                
                # Публикуем запланированные посты
                await self.publish_scheduled_posts()
                
                # Ждем 1 минуту
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Ошибка в фоновой задаче: {e}")
                await asyncio.sleep(60)
                
    async def publish_scheduled_posts(self):
        """Публикация запланированных постов"""
        pending_posts = await db.get_pending_posts(limit=10)
        
        for post in pending_posts:
            if datetime.fromisoformat(post['scheduled_time']) > datetime.now():
                continue
                
            try:
                if post['content_type'] == 'text':
                    await self.application.bot.send_message(
                        chat_id=post['channel_id'],
                        text=post['content'],
                        parse_mode=ParseMode.HTML
                    )
                elif post['content_type'] == 'photo':
                    await self.application.bot.send_photo(
                        chat_id=post['channel_id'],
                        photo=post['media_id'],
                        caption=post['content'],
                        parse_mode=ParseMode.HTML
                    )
                elif post['content_type'] == 'video':
                    await self.application.bot.send_video(
                        chat_id=post['channel_id'],
                        video=post['media_id'],
                        caption=post['content'],
                        parse_mode=ParseMode.HTML
                    )
                
                # Обновляем статус поста
                await db.update_post_status(post['id'], 'published')
                
                # Увеличиваем счетчик постов пользователя
                await db.increment_post_count(post['user_id'])
                
                logger.info(f"Опубликован пост {post['id']} в канал {post['channel_id']}")
                
            except Exception as e:
                logger.error(f"Ошибка публикации поста {post['id']}: {e}")
                await db.update_post_status(post['id'], 'failed')
                
# ========== ЗАПУСК БОТА ==========
async def main():
    """Основная функция запуска"""
    bot = SchedulerBot()
    
    try:
        await bot.setup()
        
        print("=" * 50)
        print("🤖 TELEGRAM SCHEDULER BOT")
        print("=" * 50)
        print(f"Bot Token: {BOT_TOKEN[:10]}...")
        print(f"Admin ID: {ADMIN_ID}")
        print(f"Port: {PORT}")
        print("=" * 50)
        print("✅ Бот запущен и готов к работе!")
        print("=" * 50)
        
        # Бесконечный цикл
        await asyncio.Future()
        
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
