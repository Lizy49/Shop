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

API_TOKEN = '7592882454:AAEbeRBkrtGNK41HcyVOVZ8PYIHLuYoGD1g'
MANAGER_CHAT_ID = 1812480625

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    username = message.from_user.username or message.from_user.first_name
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Оформить заказ", web_app=WebAppInfo(url="https://olimpshop49.netlify.app/"))]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"🔥 *Добро пожаловать в OlimpShop49, {username}!* 🔥\n\n"
        "💎 Премиум товары с быстрой доставкой\n"
        "⚡ Лучшие цены в твоем районе\n"
        "🔐 Гарантия качества и анонимности\n\n"
        "Нажми кнопку ниже чтобы начать покупки!",
        reply_markup=keyboard
    )

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        items = data.get('items', [])

        if not items:
            await message.answer("❗ Не удалось получить товары из заказа.")
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
            f"✅ *Ваш заказ принят!*\n\n"
            f"{items_text}\n\n"
            f"📍 Район: {district}\n"
            f"🏠 Адрес: {address}\n"
            f"💰 Итого: *{total} ₽*\n\n"
            f"Скоро с вами свяжется менеджер!"
        )

        # Сообщение менеджеру
        await bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=(
                f"📦 *Новый заказ!*\n\n"
                f"{items_text}\n\n"
                f"📍 Район: {district}\n"
                f"🏠 Адрес: {address}\n"
                f"💰 Сумма: *{total} ₽*\n"
                f"👤 От: @{username}"
            )
        )

    except Exception as e:
        logging.exception("Ошибка при обработке WebAppData")
        await message.answer("⚠ Произошла ошибка при обработке заказа. Попробуйте еще раз.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
