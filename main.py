import json
import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    WebAppInfo, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject
from aiogram import F
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz

# Настройки
API_TOKEN = '7592882454:AAGGwkE47GC0NHZ1cBiPqwQrI76gPQifzh0'
MANAGER_CHAT_ID = -1002378282152
CHANNEL_USERNAME = '@olimpmagadan'
MANAGER_USERNAME = '@olimpshopmanager'
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
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                joined_channel BOOLEAN DEFAULT FALSE,
                discount INTEGER DEFAULT 0
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
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'new',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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

    def mark_as_joined(self, user_id: int):
        """Отметка что пользователь вступил в канал"""
        self.cursor.execute('''
            UPDATE users SET joined_channel = TRUE
            WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()

    def activate_referral(self, referral_id: int):
        """Активация реферала (после вступления в канал)"""
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
            SELECT username, full_name, joined_channel, discount FROM users WHERE user_id = ?
        ''', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'username': row[0],
                'full_name': row[1],
                'joined_channel': row[2],
                'discount': row[3]
            }
        return None

    def add_order(self, user_id: int, data: str):
        """Добавление заказа"""
        self.cursor.execute('''
            INSERT INTO orders (user_id, data)
            VALUES (?, ?)
        ''', (user_id, data))
        self.conn.commit()
        return self.cursor.lastrowid

    def update_user_discount(self, user_id: int, discount: int):
        """Обновление скидки пользователя"""
        self.cursor.execute('''
            UPDATE users SET discount = ?
            WHERE user_id = ?
        ''', (discount, user_id))
        self.conn.commit()

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

def get_channel_keyboard():
    """Кнопка для вступления в канал"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Вступить в канал", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]
        ]
    )

def get_order_keyboard(order_id: int):
    """Кнопки для обработки заказа"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{order_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")
            ]
        ]
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

async def check_channel_subscription(user_id: int) -> bool:
    """Проверка подписки на канал"""
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

@dp.message(Command("start", "restart"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    """Обработчик команд /start и /restart"""
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
    
    # Проверяем подписку на канал
    is_subscribed = await check_channel_subscription(user_id)
    if is_subscribed:
        db.mark_as_joined(user_id)
        # Активируем реферала если он пришел по ссылке
        user_info = db.get_user_info(user_id)
        if user_info and user_info.get('invited_by'):
            db.activate_referral(user_id)
    
    # Обновляем скидку
    ref_count = db.get_active_referrals_count(user_id)
    discount = calculate_discount(ref_count)
    db.update_user_discount(user_id, discount)
    
    if not is_subscribed:
        await message.answer(
            f"🔥 *Добро пожаловать в OlimpShop49, {full_name}!*\n\n"
            f"📢 Для продолжения работы подпишись на наш канал {CHANNEL_USERNAME}\n\n"
            f"💎 После подписки ты получишь:\n"
            f"- Реферальную ссылку для приглашения друзей\n"
            f"- Скидку до 50% за приглашенных друзей\n"
            f"- Доступ к эксклюзивным предложениям",
            reply_markup=get_channel_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
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

@dp.message(F.text == "📞 Контакты")
async def show_contacts(message: types.Message):
    """Показ контактов"""
    await message.answer(
        "📞 <b>КОНТАКТЫ OlimpShop49</b> 📞\n\n"
        "🔹 Телеграм: @olimpmagadan\n"
        "🔹 Менеджер: @olimpshopmanager\n"
        "🔹 Разработчик: киньте сколько вы оцениваете мое старание(Т-Банк:2200701015005249)\n\n"
        "⚡ <i>Зевс всегда на связи!</i> ⚡\n"
        "Пиши - не стесняйся, отвечаем быстрее молнии!",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "🕒 Режим работы")
async def show_schedule(message: types.Message):
    """Показ режима работы"""
    await message.answer(
        "⏰ <b>РЕЖИМ РАБОТЫ</b> ⏰\n\n"
        "▫️ Обычные дни: 10:00 - 23:00 (когда Зевс не пьёт амброзию)\n"
        "▫️ Праздничные дни: 12:00 - 22:00 (ночные молнии - наше всё)\n\n"
        "⚡ <i>Доставляем без выходных!</i> ⚡\n"
        "Даже если сам Геракл сказал, что сегодня выходной!",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )

@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    """Обработка данных из WebApp"""
    try:
        user_id = message.from_user.id
        data = json.loads(message.web_app_data.data)
        
        # Получаем информацию о пользователе и его скидке
        user_info = db.get_user_info(user_id)
        discount = user_info['discount'] if user_info else 0
        
        # Добавляем заказ в базу
        order_id = db.add_order(user_id, json.dumps(data, ensure_ascii=False))
        
        # Рассчитываем итоговую сумму со скидкой
        total = float(data.get('total', 0))
        discounted_total = total * (100 - discount) / 100
        
        # Формируем сообщение для менеджера
        manager_message = (
            f"⚡ <b>НОВЫЙ ЗАКАЗ! Готовь молнии!</b> ⚡\n\n"
        )
        
        # Добавляем товары
        for item in data.get('items', []):
            manager_message += (
                f"▫ {item.get('name', 'Неизвестный товар')} | "
                f"Вкус: {item.get('flavor', 'Не указан')} | "
                f"Кол-во: {item.get('quantity', 1)} | "
                f"Сумма: {item.get('price', 0)}₽\n"
            )
        
        # Добавляем информацию о доставке и оплате
        manager_message += (
            f"\n📍 <b>Район:</b> {data.get('district', 'Не указан')} ({data.get('delivery_price', 0)}₽)\n"
            f"🏠 <b>Адрес:</b> {data.get('address', 'Не указан')}\n"
            f"💰 <b>Сумма:</b> {total}₽\n"
        )
        
        if discount > 0:
            manager_message += f"💎 <b>Скидка {discount}%:</b> {discounted_total:.2f}₽\n"
        
        manager_message += (
            f"👤 <b>От:</b> @{message.from_user.username or message.from_user.full_name}\n\n"
            f"<i>Быстрее ветра, курьер! Клиент ждёт!</i>"
        )
        
        # Отправляем менеджеру
        await bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=manager_message,
            parse_mode=ParseMode.HTML,
            reply_markup=get_order_keyboard(order_id)
        )
        
        # Формируем сообщение для пользователя
        user_message = (
            f"⚡ <b>Ваш заказ #{order_id} принят!</b> ⚡\n\n"
            f"<b>Состав заказа:</b>\n"
        )
        
        for item in data.get('items', []):
            user_message += (
                f"▫ {item.get('name', 'Неизвестный товар')} | "
                f"{item.get('quantity', 1)}шт. | "
                f"{item.get('price', 0)}₽\n"
            )
        
        user_message += (
            f"\n<b>Доставка:</b> {data.get('district', 'Не указан')} ({data.get('delivery_price', 0)}₽)\n"
            f"<b>Адрес:</b> {data.get('address', 'Не указан')}\n"
            f"<b>Итого:</b> {total}₽\n"
        )
        
        if discount > 0:
            user_message += (
                f"<b>Ваша скидка:</b> {discount}%\n"
                f"<b>К оплате:</b> {discounted_total:.2f}₽\n"
            )
        
        user_message += (
            f"\nМенеджер @olimpshopmanager свяжется с вами для подтверждения.\n"
            f"Спасибо за заказ в OlimpShop49! ⚡"
        )
        
        # Отправляем пользователю
        await message.answer(
            user_message,
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logging.error(f"Ошибка обработки заказа: {e}")
        await message.answer(
            "⚠ Произошла ошибка при обработке вашего заказа. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_keyboard()
        )

@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    """Обработка принятия заказа"""
    try:
        order_id = int(callback.data.split("_")[1])
        
        # Обновляем сообщение у менеджера
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Заказ принят в работу!</b>",
            parse_mode=ParseMode.HTML
        )
        
        await callback.answer("Заказ принят")
    except Exception as e:
        logging.error(f"Ошибка принятия заказа: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: types.CallbackQuery):
    """Обработка отклонения заказа"""
    try:
        order_id = int(callback.data.split("_")[1])
        
        # Обновляем сообщение у менеджера
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>Заказ отклонен!</b>",
            parse_mode=ParseMode.HTML
        )
        
        await callback.answer("Заказ отклонен")
    except Exception as e:
        logging.error(f"Ошибка отклонения заказа: {e}")
        await callback.answer("Произошла ошибка")

async def main():
    """Запуск бота"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())