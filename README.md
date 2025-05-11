```
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

@dp.message(F.text == "🏆 Топ рефералов")
async def show_top_referrals(message: types.Message):
    """Показ топа рефералов"""
    try:
        # Проверяем подписку на канал
        is_subscribed = await check_channel_subscription(message.from_user.id)
        if not is_subscribed:
            await message.answer(
                "📢 Для просмотра топа необходимо подписаться на наш канал!",
                reply_markup=get_channel_keyboard()
            )
            return
            
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

@dp.message(F.text == "💎 Моя скидка")
async def show_my_discount(message: types.Message):
    """Показ текущей скидки пользователя"""
    try:
        # Проверяем подписку на канал
        is_subscribed = await check_channel_subscription(message.from_user.id)
        if not is_subscribed:
            await message.answer(
                "📢 Для просмотра скидки необходимо подписаться на наш канал!",
                reply_markup=get_channel_keyboard()
            )
            return
            
        user_id = message.from_user.id
        ref_count = db.get_active_referrals_count(user_id)
        discount = calculate_discount(ref_count)
        
        await message.answer(
            f"💎 *Ваша текущая скидка:* {discount}%\n"
            f"👥 *Приглашено друзей:* {ref_count}\n\n"
            f"🔗 *Ваша реферальная ссылка:*\n"
            f"`https://t.me/{(await bot.get_me()).username}?start=ref={user_id}`\n\n"
            f"Приводите друзей и увеличивайте свою скидку!",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logging.error(f"Ошибка при показе скидки: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при получении информации о скидке. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )

@dp.message(F.text == "📞 Контакты")
async def show_contacts(message: types.Message):
    """Показ контактов"""
    await message.answer(
        "📞 *Контакты OlimpShop49*\n\n"
        "📍 Магадан, ул. Ленина, 49\n"
        "☎️ Телефон: +7 (914) 123-45-67\n"
        "🕒 Режим работы: 10:00 - 22:00 без выходных\n\n"
        "По всем вопросам пишите в личные сообщения",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@dp.message(F.text == "🕒 Режим работы")
async def show_schedule(message: types.Message):
    """Показ режима работы"""
    await message.answer(
        "🕒 *Режим работы OlimpShop49*\n\n"
        "Понедельник - Пятница: 10:00 - 22:00\n"
        "Суббота - Воскресенье: 11:00 - 20:00\n\n"
        "Без перерывов и выходных!",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    """Обработка данных из WebApp"""
    try:
        user_id = message.from_user.id
        data = json.loads(message.web_app_data.data)
        
        # Добавляем заказ в базу
        order_id = db.add_order(user_id, json.dumps(data, ensure_ascii=False))
        
        # Получаем информацию о пользователе
        user_info = db.get_user_info(user_id)
        discount = user_info['discount'] if user_info else 0
        
        # Формируем сообщение для менеджера
        order_text = (
            f"🆕 *Новый заказ #`{order_id}`*\n\n"
            f"👤 *Клиент:* @{message.from_user.username or message.from_user.full_name} (ID: `{user_id}`)\n"
            f"💎 *Скидка:* {discount}%\n"
            f"📅 *Дата:* {get_magadan_time()} (МСК+8)\n\n"
            f"📦 *Состав заказа:*\n"
        )
        
        # Добавляем товары из заказа
        for item in data.get('items', []):
            order_text += f"- {item.get('name', 'Неизвестный товар')} x{item.get('quantity', 1)} - {item.get('price', 0)}₽\n"
        
        order_text += f"\n💵 *Итого:* {data.get('total', 0)}₽"
        if discount > 0:
            discounted_total = data.get('total', 0) * (100 - discount) / 100
            order_text += f" (со скидкой {discount}%: {discounted_total:.2f}₽)"
        
        order_text += f"\n\n📍 *Адрес доставки:* {data.get('address', 'Не указан')}"
        order_text += f"\n📞 *Телефон:* {data.get('phone', 'Не указан')}"
        order_text += f"\n💬 *Комментарий:* {data.get('comment', 'Нет комментария')}"
        
        # Отправляем менеджеру
        await bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=order_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_order_keyboard(order_id)
        )
        
        # Подтверждение пользователю
        await message.answer(
            "✅ *Ваш заказ принят!*\n\n"
            "Спасибо за покупку в OlimpShop49!\n"
            "Менеджер свяжется с вами в ближайшее время для подтверждения заказа.",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logging.error(f"Ошибка обработки заказа: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке вашего заказа. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_keyboard()
        )

@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    """Обработка принятия заказа"""
    try:
        order_id = int(callback.data.split("_")[1])
        
        # Обновляем статус заказа (в реальном проекте нужно добавить поле статуса)
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ *Заказ принят в работу*",
            parse_mode=ParseMode.MARKDOWN
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
        
        # Обновляем статус заказа
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ *Заказ отклонен*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await callback.answer("Заказ отклонен")
    except Exception as e:
        logging.error(f"Ошибка отклонения заказа: {e}")
        await callback.answer("Произошла ошибка")

@dp.chat_join_request()
async def handle_join_request(update: types.ChatJoinRequest):
    """Обработка вступления в канал"""
    try:
        user_id = update.from_user.id
        db.mark_as_joined(user_id)
        
        # Активируем реферала если он пришел по ссылке
        user_info = db.get_user_info(user_id)
        if user_info and user_info.get('invited_by'):
            db.activate_referral(user_id)
            
            # Уведомляем пригласившего
            inviter_id = user_info['invited_by']
            inviter_ref_count = db.get_active_referrals_count(inviter_id)
            inviter_discount = calculate_discount(inviter_ref_count)
            
            try:
                await bot.send_message(
                    chat_id=inviter_id,
                    text=f"🎉 *Ваш друг присоединился к каналу!*\n\n"
                         f"👤 @{update.from_user.username or update.from_user.full_name}\n"
                         f"💰 Ваша текущая скидка: {inviter_discount}%\n"
                         f"👥 Всего приглашено: {inviter_ref_count}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
        
        # Принимаем запрос на вступление
        await update.approve()
    except Exception as e:
        logging.error(f"Ошибка обработки вступления в канал: {e}")

async def check_subscriptions():
    """Периодическая проверка подписок"""
    while True:
        try:
            # Получаем всех пользователей, которые якобы подписаны
            db.cursor.execute('SELECT user_id FROM users WHERE joined_channel = TRUE')
            users = db.cursor.fetchall()
            
            for (user_id,) in users:
                try:
                    is_subscribed = await check_channel_subscription(user_id)
                    if not is_subscribed:
                        db.cursor.execute('UPDATE users SET joined_channel = FALSE WHERE user_id = ?', (user_id,))
                        db.conn.commit()
                except Exception as e:
                    logging.error(f"Ошибка проверки подписки для {user_id}: {e}")
            
            await asyncio.sleep(3600)  # Проверка каждый час
        except Exception as e:
            logging.error(f"Ошибка в check_subscriptions: {e}")
            await asyncio.sleep(60)

async def on_startup():
    """Действия при запуске бота"""
    asyncio.create_task(check_subscriptions())

async def main():
    """Запуск бота"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    dp.startup.register(on_startup)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
