import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "scheduler.db"):
        self.db_path = db_path
        
    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Пользователи
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    tariff TEXT DEFAULT 'free',
                    subscription_end DATETIME,
                    channels_count INTEGER DEFAULT 0,
                    posts_today INTEGER DEFAULT 0,
                    last_post_date DATE,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Каналы пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id TEXT UNIQUE,
                    channel_name TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Запланированные посты
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id TEXT,
                    content_type TEXT,
                    content TEXT,
                    media_id TEXT,
                    scheduled_time DATETIME,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Платежи
            await db.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    tariff TEXT,
                    amount INTEGER,
                    status TEXT DEFAULT 'pending',
                    payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Настройки тарифов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tariff_settings (
                    tariff_name TEXT PRIMARY KEY,
                    price INTEGER,
                    channels_limit INTEGER,
                    posts_per_day INTEGER,
                    duration_days INTEGER,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Приватные каналы для тарифов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS private_channels (
                    tariff_name TEXT PRIMARY KEY,
                    channel_id TEXT UNIQUE,
                    invite_link TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Статистика
            await db.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    date DATE PRIMARY KEY,
                    new_users INTEGER DEFAULT 0,
                    total_posts INTEGER DEFAULT 0,
                    revenue INTEGER DEFAULT 0
                )
            ''')
            
            # Инициализируем тарифы по умолчанию
            default_tariffs = [
                ('basic', 299, 2, 5, 30),
                ('premium', 599, 5, 20, 30),
                ('vip', 999, 10, 50, 30)
            ]
            
            for tariff in default_tariffs:
                await db.execute('''
                    INSERT OR IGNORE INTO tariff_settings 
                    (tariff_name, price, channels_limit, posts_per_day, duration_days)
                    VALUES (?, ?, ?, ?, ?)
                ''', tariff)
            
            await db.commit()
            logger.info("База данных инициализирована")
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = ""):
        """Добавление нового пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_user_tariff(self, user_id: int, tariff: str):
        """Обновление тарифа пользователя"""
        tariff_info = await self.get_tariff_info(tariff)
        if not tariff_info:
            return False
        
        subscription_end = datetime.now() + timedelta(days=tariff_info['duration_days'])
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users 
                SET tariff = ?, subscription_end = ?
                WHERE user_id = ?
            ''', (tariff, subscription_end.isoformat(), user_id))
            await db.commit()
            return True
    
    async def get_user_channels(self, user_id: int) -> List[Dict]:
        """Получение каналов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM user_channels WHERE user_id = ? ORDER BY added_at DESC',
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def add_user_channel(self, user_id: int, channel_id: str, channel_name: str) -> Tuple[bool, str]:
        """Добавление канала пользователя"""
        # Проверяем лимит каналов
        user = await self.get_user(user_id)
        if not user:
            return False, "Пользователь не найден"
        
        tariff_info = await self.get_tariff_info(user['tariff'])
        if not tariff_info:
            return False, "Тариф не найден"
        
        current_channels = await self.get_user_channels(user_id)
        if len(current_channels) >= tariff_info['channels_limit']:
            return False, f"Лимит каналов ({tariff_info['channels_limit']}) достигнут"
        
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''
                    INSERT INTO user_channels (user_id, channel_id, channel_name)
                    VALUES (?, ?, ?)
                ''', (user_id, channel_id, channel_name))
                
                await db.execute('''
                    UPDATE users SET channels_count = channels_count + 1 
                    WHERE user_id = ?
                ''', (user_id,))
                
                await db.commit()
                return True, "Канал успешно добавлен"
            except aiosqlite.IntegrityError:
                return False, "Этот канал уже добавлен"
    
    async def remove_user_channel(self, user_id: int, channel_id: str) -> bool:
        """Удаление канала пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'DELETE FROM user_channels WHERE user_id = ? AND channel_id = ?',
                (user_id, channel_id)
            )
            await db.execute('''
                UPDATE users SET channels_count = channels_count - 1 
                WHERE user_id = ?
            ''', (user_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    # ========== ТАРИФЫ ==========
    async def get_tariff_info(self, tariff_name: str) -> Optional[Dict]:
        """Получение информации о тарифе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM tariff_settings WHERE tariff_name = ?',
                (tariff_name,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_all_tariffs(self) -> List[Dict]:
        """Получение всех тарифов"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM tariff_settings ORDER BY price')
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_tariff_price(self, tariff_name: str, price: int) -> bool:
        """Обновление цены тарифа"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                UPDATE tariff_settings SET price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tariff_name = ?
            ''', (price, tariff_name))
            await db.commit()
            return cursor.rowcount > 0
    
    async def add_private_channel(self, tariff_name: str, channel_id: str, invite_link: str) -> bool:
        """Добавление приватного канала для тарифа"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''
                    INSERT OR REPLACE INTO private_channels (tariff_name, channel_id, invite_link)
                    VALUES (?, ?, ?)
                ''', (tariff_name, channel_id, invite_link))
                await db.commit()
                return True
            except:
                return False
    
    async def get_private_channel(self, tariff_name: str) -> Optional[Dict]:
        """Получение приватного канала для тарифа"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM private_channels WHERE tariff_name = ?',
                (tariff_name,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    # ========== ПОСТЫ ==========
    async def add_scheduled_post(self, user_id: int, channel_id: str, content_type: str,
                                content: str, media_id: str, scheduled_time: datetime) -> int:
        """Добавление запланированного поста"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO scheduled_posts 
                (user_id, channel_id, content_type, content, media_id, scheduled_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, channel_id, content_type, content, media_id, scheduled_time.isoformat()))
            await db.commit()
            return cursor.lastrowid
    
    async def get_pending_posts(self, limit: int = 100) -> List[Dict]:
        """Получение ожидающих публикаций"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM scheduled_posts 
                WHERE status = 'pending' AND scheduled_time <= datetime('now', '+1 hour')
                ORDER BY scheduled_time
                LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_post_status(self, post_id: int, status: str):
        """Обновление статуса поста"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE scheduled_posts SET status = ? WHERE id = ?
            ''', (status, post_id))
            await db.commit()
    
    async def get_user_posts(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Получение постов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM scheduled_posts 
                WHERE user_id = ?
                ORDER BY scheduled_time DESC
                LIMIT ?
            ''', (user_id, limit))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def check_post_limit(self, user_id: int) -> Tuple[bool, str]:
        """Проверка лимита постов на сегодня"""
        user = await self.get_user(user_id)
        if not user:
            return False, "Пользователь не найден"
        
        tariff_info = await self.get_tariff_info(user['tariff'])
        if not tariff_info:
            return False, "Тариф не найден"
        
        today = datetime.now().date()
        last_post_date = user.get('last_post_date')
        
        if last_post_date:
            last_post_date = datetime.fromisoformat(last_post_date).date() if isinstance(last_post_date, str) else last_post_date
            if last_post_date == today:
                if user['posts_today'] >= tariff_info['posts_per_day']:
                    return False, f"Лимит постов на сегодня ({tariff_info['posts_per_day']}) достигнут"
        
        return True, ""
    
    async def increment_post_count(self, user_id: int):
        """Увеличение счетчика постов"""
        today = datetime.now().date().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users 
                SET posts_today = CASE 
                    WHEN last_post_date = date(?) THEN posts_today + 1 
                    ELSE 1 
                END,
                last_post_date = date(?)
                WHERE user_id = ?
            ''', (today, today, user_id))
            await db.commit()
    
    # ========== ПЛАТЕЖИ ==========
    async def add_payment(self, user_id: int, tariff: str, amount: int, status: str = 'completed') -> int:
        """Добавление платежа"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO payments (user_id, tariff, amount, status)
                VALUES (?, ?, ?, ?)
            ''', (user_id, tariff, amount, status))
            
            # Обновляем статистику
            await db.execute('''
                INSERT OR REPLACE INTO statistics (date, revenue)
                VALUES (date('now'), COALESCE((SELECT revenue FROM statistics WHERE date = date('now')), 0) + ?)
                ON CONFLICT(date) DO UPDATE SET revenue = revenue + ?
            ''', (amount, amount))
            
            await db.commit()
            return cursor.lastrowid
    
    async def get_user_payments(self, user_id: int) -> List[Dict]:
        """Получение платежей пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM payments 
                WHERE user_id = ? 
                ORDER BY payment_date DESC
            ''', (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ========== АДМИН СТАТИСТИКА ==========
    async def get_statistics(self) -> Dict:
        """Получение статистики"""
        async with aiosqlite.connect(self.db_path) as db:
            # Общее количество пользователей
            cursor = await db.execute('SELECT COUNT(*) FROM users')
            total_users = (await cursor.fetchone())[0]
            
            # Пользователи по тарифам
            cursor = await db.execute('''
                SELECT tariff, COUNT(*) as count FROM users GROUP BY tariff
            ''')
            tariff_stats = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Общая прибыль
            cursor = await db.execute('''
                SELECT SUM(amount) FROM payments WHERE status = 'completed'
            ''')
            total_revenue = (await cursor.fetchone())[0] or 0
            
            # Запланированные публикации
            cursor = await db.execute('''
                SELECT COUNT(*) FROM scheduled_posts WHERE status = 'pending'
            ''')
            pending_posts = (await cursor.fetchone())[0]
            
            # Активные пользователи за последние 7 дней
            cursor = await db.execute('''
                SELECT COUNT(DISTINCT user_id) FROM scheduled_posts 
                WHERE created_at >= datetime('now', '-7 days')
            ''')
            active_users = (await cursor.fetchone())[0]
            
            return {
                'total_users': total_users,
                'tariff_stats': tariff_stats,
                'total_revenue': total_revenue,
                'pending_posts': pending_posts,
                'active_users': active_users
            }
    
    async def get_all_users(self, limit: int = 1000) -> List[Dict]:
        """Получение всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM users ORDER BY registered_at DESC LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def export_users_csv(self) -> str:
        """Экспорт пользователей в CSV"""
        users = await self.get_all_users()
        
        csv_lines = ["ID,Username,First Name,Last Name,Tariff,Channels,Posts Today,Registered"]
        for user in users:
            csv_lines.append(
                f"{user['user_id']},"
                f"{user['username'] or ''},"
                f"{user['first_name']},"
                f"{user['last_name'] or ''},"
                f"{user['tariff']},"
                f"{user['channels_count']},"
                f"{user['posts_today']},"
                f"{user['registered_at']}"
            )
        
        return "\n".join(csv_lines)
    
    async def check_expired_subscriptions(self):
        """Проверка истекших подписок"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT user_id FROM users 
                WHERE subscription_end < datetime('now') 
                AND tariff != 'free'
            ''')
            expired_users = await cursor.fetchall()
            
            for (user_id,) in expired_users:
                await db.execute('''
                    UPDATE users SET tariff = 'free' WHERE user_id = ?
                ''', (user_id,))
            
            await db.commit()
            return [user_id for (user_id,) in expired_users]
