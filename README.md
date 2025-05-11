```
import json
import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject
from aiogram import F
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz

# Настройки
API_TOKEN = '7592882454:AAGGwkE47GC0NHZ1cBiPqwQrI76gPQifzh0'
MANAGER_CHAT_ID = -1002378282152
DATABASE_FILE = 'database.db'
MAGADAN_TIMEZONE = pytz.timezone('Asia/Magadan')

# Инициализация бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        """Инициализация таблиц в базе данных"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                invited_by INTEGER,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id INTEGER,
                referral_id INTEGER UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                activated BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (inviter_id) REFERENCES users(user_id),
                FOREIGN KEY (referral_id) REFERENCES users(user_id)
            )
        ''')
        self.conn.commit()

    def add_user(self, user_id: int, username: str, full_name: str, invited_by: Optional[int] = None):
        """Добавление нового пользователя"""
        self.cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, full_name, invited_by)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, full_name, invited_by))
        self.conn.commit()

    def add_referral(self, inviter_id: int, referral_id: int):
        """Добавление реферала"""
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO referrals (inviter_id, referral_id)
                VALUES (?, ?)
            ''', (inviter_id, referral_id))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def activate_referral(self, referral_id: int):
        """Активация реферала (после заказа)"""
        self.cursor.execute('''
            UPDATE referrals SET activated = TRUE
            WHERE referral_id = ?
        ''', (referral_id,))
        self.conn.commit()

    def get_user_referrals(self, user_id: int) -> List[Dict]:
        """Получение списка рефералов пользователя"""
        self.cursor.execute('''
            SELECT r.referral_id, u.username, u.full_name, r.created_at, r.activated
            FROM referrals r
            JOIN users u ON r.referral_id = u.user_id
            WHERE r.inviter_id = ?
            ORDER BY r.created_at DESC
        ''', (user_id,))
        columns = [col[0] for col in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def get_active_referrals_count(self, user_id: int) -> int:
        """Получение количества активных рефералов"""
        self.cursor.execute('''
            SELECT COUNT(*) FROM referrals
            WHERE inviter_id = ? AND activated = TRUE
        ''', (user_id,))
        return self.cursor.fetchone()[0]

    def get_top_referrals(self, limit: int = 10) -> List[Dict]:
        """Получение топа рефералов"""
        self.cursor.execute('''
            SELECT 
                u.user_id, 
                COALESCE(u.username, u.full_name) as display_name,
                COUNT(r.id) as referrals_count
            FROM users u
            JOIN referrals r ON u.user_id = r.inviter_id
            WHERE r.activated = TRUE
            GROUP BY u.user_id, u.username, u.full_name
            ORDER BY referrals_count DESC
            LIMIT ?
        ''', (limit,))
        columns = [col[0] for col in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def get_user_info(self, user_id: int) -> Dict:
        """Получение информации о пользователе"""
        self.cursor.execute('''
            SELECT username, full_name FROM users WHERE user_id = ?
        ''', (user_id,))
        row = self.cursor.fetchone()
        return {'username': row[0], 'full_name': row[1]} if row else None

# Инициализация базы данных
db = Database()

def get_main_keyboard():
    """Клавиатура главного меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Оформить заказ", web_app=WebAppInfo(url="https://olimpshop49.netlify.app/"))],
            [
                KeyboardButton(text="📞 Контакты"),
                KeyboardButton(text="🕒 Режим работы"),
                KeyboardButton(text="🏆 Топ рефералов")
            ],
            [KeyboardButton(text="💎 Моя скидка")]
        ],
        resize_keyboard=True
    )

def calculate_discount(referrals_count: int) -> int:
    """Расчет скидки по количеству рефералов"""
    if referrals_count >= 50:
        return 50
    elif referrals_count >= 40:
        return 45
    elif referrals_count >= 35:
        return 40
    elif referrals_count >= 30:
        return 35
    elif referrals_count >= 25:
        return 30
    elif referrals_count >= 20:
        return 25
    elif referrals_count >= 15:
        return 20
    elif referrals_count >= 10:
        return 15
    elif referrals_count >= 5:
        return 10
    elif referrals_count >= 1:
        return 5
    return 0

def get_magadan_time():
    """Получение текущего времени по Магаданскому часовому поясу"""
    return datetime.now(MAGADAN_TIMEZONE).strftime('%d.%m.%Y %H:%M')

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Обработка реферальной ссылки
    if command and command.args and command.args.startswith("ref="):
        try:
            inviter_id = int(command.args.split("=")[1])
            if inviter_id != user_id:  # Защита от самоприглашения
                # Добавляем пользователей в базу
                db.add_user(inviter_id, 
                           username or "unknown", 
                           full_name or "Неизвестно")
                db.add_user(user_id, username, full_name, inviter_id)
                db.add_referral(inviter_id, user_id)
                
                # Получаем информацию о пригласившем
                inviter_info = db.get_user_info(inviter_id)
                inviter_username = inviter_info['username'] if inviter_info else "unknown"
                inviter_name = inviter_info['full_name'] if inviter_info else "Неизвестно"
                
                # Формируем текст для пригласившего
                inviter_text = (f"@{inviter_username}" if inviter_username != "unknown" 
                              else inviter_name)
                
                # Уведомление менеджера
                await bot.send_message(
                    chat_id=MANAGER_CHAT_ID,
                    text=f"🆕 *Новый реферал!*\n\n"
                         f"👤 *Пригласил:* {inviter_text} (ID: `{inviter_id}`)\n"
                         f"👥 *Приведён:* @{username if username else full_name} (ID: `{user_id}`)\n"
                         f"📅 *Дата:* {get_magadan_time()} (МСК+8)\n"
                         f"#реферал #{user_id} #{inviter_id}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                db.add_user(user_id, username, full_name)
        except Exception as e:
            logging.error(f"Ошибка обработки реферальной ссылки: {e}")
            db.add_user(user_id, username, full_name)
    else:
        db.add_user(user_id, username, full_name)
    
    # Получение скидки
    ref_count = db.get_active_referrals_count(user_id)
    discount = calculate_discount(ref_count)
    
    await message.answer(
        f"🔥 *Добро пожаловать в OlimpShop49, {full_name}!*\n\n"
        f"💎 *Твоя реферальная ссылка:* \n`https://t.me/{(await bot.get_me()).username}?start=ref={user_id}`\n"
        f"💰 *Текущая скидка:* {discount}% (приведено {ref_count} друзей)\n\n"
        f"Приводи друзей - получай скидки до 50%!\n\n"
        f"А также заказывайте у нас жижи, одноразки, подики, испарители\n"
        f"Соревнуйтесь, ведь кто больше приведет, у того большая скидка. Удачи!",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@dp.message(F.text == "🏆 Топ рефералов")
async def show_top_referrals(message: types.Message):
    """Показ топа рефералов"""
    try:
        top = db.get_top_referrals(10)  # Получаем топ-10
        if not top:
            await message.answer("🏆 Пока никто никого не привел. Ты можешь быть первым!")
            return
        
        top_text = "\n".join(
            f"{i+1}. {user['display_name']} — {user['referrals_count']} чел. "
            f"(скидка {calculate_discount(user['referrals_count'])}%)"
            for i, user in enumerate(top)
        )
        
        await message.answer(
            f"🏆 *ТОП РЕФЕРАЛОВ* 🏆\n\n"
            f"{top_text}\n\n"
            f"*Приводи друзей и поднимайся в топе!*",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logging.error(f"Ошибка при показе топа рефералов: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при получении топа рефералов. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )

# Остальные обработчики остаются без изменений...

async def main():
    """Запуск бота"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
```
