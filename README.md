```python
import json
import logging
import asyncio
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject
from aiogram import F
import asyncpg
from typing import List, Dict, Optional

# Настройки
API_TOKEN = '7592882454:AAGGwkE47GC0NHZ1cBiPqwQrI76gPQifzh0'
MANAGER_CHAT_ID = -1002378282152
DATABASE_URL = "postgresql://user:password@localhost/dbname"  # Замени на свои, кретин

# Инициализация бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

# Класс для работы с базой
class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self._create_tables()

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    invited_by BIGINT,
                    registered_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    inviter_id BIGINT REFERENCES users(user_id),
                    referral_id BIGINT UNIQUE REFERENCES users(user_id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    activated BOOLEAN DEFAULT FALSE
                )
            """)

    async def add_user(self, user_id: int, username: str, invited_by: Optional[int] = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, invited_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET username = $2
            """, user_id, username, invited_by)

    async def add_referral(self, inviter_id: int, referral_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO referrals (inviter_id, referral_id)
                VALUES ($1, $2)
                ON CONFLICT (referral_id) DO NOTHING
            """, inviter_id, referral_id)

    async def activate_referral(self, referral_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE referrals SET activated = TRUE
                WHERE referral_id = $1
            """, referral_id)

    async def get_user_referrals(self, user_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT r.referral_id, u.username, r.created_at, r.activated
                FROM referrals r
                JOIN users u ON r.referral_id = u.user_id
                WHERE r.inviter_id = $1
                ORDER BY r.created_at DESC
            """, user_id)

    async def get_active_referrals_count(self, user_id: int) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT COUNT(*) FROM referrals
                WHERE inviter_id = $1 AND activated = TRUE
            """, user_id)

    async def get_top_referrals(self, limit: int = 10) -> List[Dict]:
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT u.user_id, u.username, COUNT(r.id) as referrals_count
                FROM users u
                JOIN referrals r ON u.user_id = r.inviter_id
                WHERE r.activated = TRUE
                GROUP BY u.user_id, u.username
                ORDER BY referrals_count DESC
                LIMIT $1
            """, limit)

db = Database()

def get_main_keyboard():
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
    """Вычисляет скидку по твоей тупой схеме"""
    if referrals_count >= 40:
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

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Обработка реферальной ссылки
    if command and command.args and command.args.startswith("ref="):
        try:
            inviter_id = int(command.args.split("=")[1])
            if inviter_id != user_id:  # Нельзя приглашать себя, дебил
                await db.add_user(inviter_id, "unknown")  # На случай если приглашающий ещё не в базе
                await db.add_user(user_id, username, inviter_id)
                await db.add_referral(inviter_id, user_id)
                
                # Уведомляем менеджера о новом реферале
                inviter_username = (await db.pool.fetchval(
                    "SELECT username FROM users WHERE user_id = $1", inviter_id
                )) or "unknown"
                
                await bot.send_message(
                    chat_id=MANAGER_CHAT_ID,
                    text=f"🆕 *Новый реферал!*\n\n"
                         f"👤 Пригласил: @{inviter_username} (ID: {inviter_id})\n"
                         f"👥 Приведён: @{username} (ID: {user_id})\n"
                         f"📅 Дата: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
            else:
                await db.add_user(user_id, username)
        except (ValueError, IndexError, Exception) as e:
            logging.error(f"Ошибка обработки реферальной ссылки: {e}")
            await db.add_user(user_id, username)
    else:
        await db.add_user(user_id, username)
    
    # Получаем количество активных рефералов
    ref_count = await db.get_active_referrals_count(user_id)
    discount = calculate_discount(ref_count)
    
    await message.answer(
        f"🔥 *Добро пожаловать в OlimpShop49, {username}!* 🔥\n\n"
        f"💎 Твоя реферальная ссылка: `https://t.me/{(await bot.get_me()).username}?start=ref={user_id}`\n"
        f"💰 Текущая скидка: *{discount}%* (приведено {ref_count} друзей)\n\n"
        "Приводи друзей - получай скидки до 45%!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🏆 Топ рефералов")
async def show_top_referrals(message: types.Message):
    top = await db.get_top_referrals()
    if not top:
        await message.answer("🏆 Пока никто никого не привел. Ты можешь быть первым, лузер!")
        return
    
    top_text = "\n".join(
        f"{i+1}. @{user['username']} — {user['referrals_count']} чел. (скидка {calculate_discount(user['referrals_count'])}%)"
        for i, user in enumerate(top)
    )
    
    await message.answer(
        f"🏆 *ТОП РЕФЕРАЛОВ* 🏆\n\n"
        f"{top_text}\n\n"
        "Приводи друзей и поднимайся в топе!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "💎 Моя скидка")
async def show_my_discount(message: types.Message):
    user_id = message.from_user.id
    ref_count = await db.get_active_referrals_count(user_id)
    discount = calculate_discount(ref_count)
    
    referrals = await db.get_user_referrals(user_id)
    refs_text = "\n".join(
        f"▫️ {ref['created_at'].strftime('%d.%m.%Y')} — @{ref['username']} "
        f"({'✅' if ref['activated'] else '❌'})"
        for ref in referrals
    ) if referrals else "Пока никого не привел"
    
    await message.answer(
        f"💎 *Твоя скидка: {discount}%* (приведено {ref_count} друзей)\n\n"
        f"📊 Твои рефералы:\n{refs_text}\n\n"
        f"🔗 Твоя реф-ссылка: `https://t.me/{(await bot.get_me()).username}?start=ref={user_id}`",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        items = data.get('items', [])
        user_id = message.from_user.id

        if not items:
            await message.answer("❗️ Ошибка: корзина пуста. Видимо, ты передумал тратить деньги, слабак!")
            return

        # Активируем реферала если он был приглашен
        await db.activate_referral(user_id)
        
        # Получаем скидку
        ref_count = await db.get_active_referrals_count(user_id)
        discount = calculate_discount(ref_count)
        
        items_text = "\n".join(
            f"▫️ {item['name']} | Вкус: *{item.get('flavor', 'не указан')}* | Кол-во: {item['qty']} | Сумма: {item['price'] * item['qty']}₽"
            for item in items
        )

        total = data.get('total', 0)
        final_total = total * (1 - discount / 100)
        address = data.get('address', 'Не указан')
        district = data.get('district', 'Не указан')
        username = message.from_user.username or message.from_user.first_name

        # Сообщение клиенту
        await message.answer(
            f"✅ *Твой заказ принят!*\n\n"
            f"{items_text}\n\n"
            f"📍 Район: {district}\n"
            f"🏠 Адрес: {address}\n"
            f"💎 Твоя скидка: *{discount}%* (привел {ref_count} друзей)\n"
            f"💰 Итого к оплате: *{final_total:.2f}₽* (без скидки {total}₽)\n\n"
            f"Гермес уже летит к тебе с посылкой!",
            reply_markup=get_main_keyboard()
        )

        # Сообщение менеджеру
        await bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=(
                f"⚡️ *НОВЫЙ ЗАКАЗ!* ⚡️\n\n"
                f"{items_text}\n\n"
                f"📍 Район: {district}\n"
                f"🏠 Адрес: {address}\n"
                f"💰 Сумма: *{final_total:.2f}₽* (скидка {discount}%)\n"
                f"👤 От: @{username} (привел {ref_count} друзей)\n\n"
                f"Быстрее ветра, курьер!"
            )
        )

    except Exception as e:
        logging.exception("Ошибка при обработке WebAppData")
        await message.answer(
            "⚠️ Боги Олимпа разгневаны! Произошла ошибка.\n"
            "Попробуй ещё раз или напиши нам в @olimpmagadan",
            reply_markup=get_main_keyboard()
        )

# Оставшиеся хендлеры из твоего исходного кода
@dp.message(F.text == "📞 Контакты")
async def contacts(message: types.Message):
    await message.answer(
        "📞 *КОНТАКТЫ OlimpShop49* 📞\n\n"
        "🔹 Телеграм: @olimpmagadan\n"
        "🔹 Менеджер: @olimpshopmanager\n"
        "🔹 Разработчик: киньте сколько вы оцениваете мое старание(Т-Банк:2200701015005249)\n\n"
        "⚡️ *Зевс всегда на связи!* ⚡️\n"
        "Пиши - не стесняйся, отвечаем быстрее молнии!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🕒 Режим работы")
async def working_hours(message: types.Message):
    await message.answer(
        "⏰ *РЕЖИМ РАБОТЫ* ⏰\n\n"
        "▫️ Обычные дни: 10:00 - 23:00 (когда Зевс не пьёт амброзию)\n"
        "▫️ Праздничные дни: 12:00 - 22:00 (ночные молнии - наше всё)\n\n"
        "⚡️ *Доставляем без выходных!* ⚡️\n"
        "Даже если сам Геракл сказал, что сегодня выходной!",
        reply_markup=get_main_keyboard()
    )

async def on_startup():
    await db.connect()
    logging.info("Бот запущен и подключен к базе данных")

async def on_shutdown():
    await db.pool.close()
    logging.info("Бот остановлен, соединение с базой закрыто")

async def main():
    await on_startup()
    await dp.start_polling(bot)
    await on_shutdown()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```
