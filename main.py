
import json
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram import F

API_TOKEN = '7592882454:AAGGwkE47GC0NHZ1cBiPqwQrI76gPQifzh0'
MANAGER_CHAT_ID = -1002378282152

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Оформить заказ", web_app=WebAppInfo(url="https://olimpshop49.netlify.app/"))],
            [KeyboardButton(text="📞 Контакты"), KeyboardButton(text="🕒 Режим работы")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    username = message.from_user.username or message.from_user.first_name
    await message.answer(
        f"🔥 *Добро пожаловать в OlimpShop49, {username}!* 🔥\n\n"
        "💎 Премиум товары с быстрой доставкой\n"
        "⚡ Лучшие цены в твоем районе\n"
        "🔐 Гарантия качества и анонимности\n\n"
        "Нажми кнопку ниже чтобы начать покупки!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📞 Контакты")
async def contacts(message: types.Message):
    await message.answer(
        "📞 *КОНТАКТЫ OlimpShop49* 📞\n\n"
        "🔹 Телеграм: @olimpmagadan\n"
        "🔹 Менеджер: @olimpshopmanager\n"
        "🔹 Разработчик: киньте сколько вы оцениваете мое старание(Т-Банк:2200701015005249)\n\n"
        "⚡ *Зевс всегда на связи!* ⚡\n"
        "Пиши - не стесняйся, отвечаем быстрее молнии!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🕒 Режим работы")
async def working_hours(message: types.Message):
    await message.answer(
        "⏰ *РЕЖИМ РАБОТЫ* ⏰\n\n"
        "▫️ Обычные дни: 10:00 - 23:00 (когда Зевс не пьёт амброзию)\n"
        "▫️ Праздничные дни: 12:00 - 22:00 (ночные молнии - наше всё)\n\n"
        "⚡ *Доставляем без выходных!* ⚡\n"
        "Даже если сам Геракл сказал, что сегодня выходной!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        items = data.get('items', [])

        if not items:
            await message.answer("❗ Ошибка: корзина пуста. Видимо, ты передумал тратить деньги, слабак!")
            return

        items_text = "\n".join(
            f"▫ {item['name']} | Вкус: *{item.get('flavor', 'не указан')}* | Кол-во: {item['qty']} | Сумма: {item['price'] * item['qty']}₽"
            for item in items
        )

        address = data.get('address', 'Не указан')
        district = data.get('district', 'Не указан')
        total = data.get('total', 0)
        username = message.from_user.username or message.from_user.first_name

        # Сообщение клиенту
        await message.answer(
            f"✅ *Твой заказ принят, смертный!*\n\n"
            f"{items_text}\n\n"
            f"📍 Район: {district}\n"
            f"🏠 Адрес: {address}\n"
            f"💰 Итого: *{total} ₽*\n\n"
            f"Гермес уже летит к тебе с посылкой! Ожидай сообщения от нашего курьера.",
            reply_markup=get_main_keyboard()
        )

        # Сообщение менеджеру
        await bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=(
                f"⚡ *НОВЫЙ ЗАКАЗ! Готовь молнии!* ⚡\n\n"
                f"{items_text}\n\n"
                f"📍 Район: {district}\n"
                f"🏠 Адрес: {address}\n"
                f"💰 Сумма: *{total} ₽*\n"
                f"👤 От: @{username}\n\n"
                f"Быстрее ветра, курьер! Клиент ждёт!"
            )
        )

    except Exception as e:
        logging.exception("Ошибка при обработке WebAppData")
        await message.answer(
            "⚠ Боги Олимпа разгневаны! Произошла ошибка при обработке заказа.\n"
            "Попробуй ещё раз или напиши нам в @olimpmagadan",
            reply_markup=get_main_keyboard()
        )

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())