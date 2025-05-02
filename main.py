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

API_TOKEN = '7592882454:AAEbeRBkrtGNK41HcyVOVZ8PYIHLuYoGD1g'  # 🔁 Вставь токен
MANAGER_CHAT_ID = 1812480625   # 🔁 Вставь ID менеджера

# Бот с настройками по умолчанию
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    username = message.from_user.username or message.from_user.first_name
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Сделать заказ", web_app=WebAppInfo(url="https://olimpshop49.netlify.app/"))]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"Добро пожаловать в OlimpShop49, {username} ⚡\nНажми кнопку ниже, чтобы перейти в магазин.",
        reply_markup=keyboard
    )

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        items_text = "\n".join(
            f"{i['name']} x{i['qty']} — {i['price'] * i['qty']}₽" for i in data['items']
        )
        address = data['address']
        total = data['total']
        username = message.from_user.username or message.from_user.first_name

        await message.answer(
            f"✅ *Ваш заказ принят!*\n\n"
            f"{items_text}\n"
            f"📍 Адрес: {address}\n"
            f"💰 Итого: {total} ₽\n\n"
            f"Скоро с вами свяжется менеджер!"
        )

        await bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=(
                f"📦 *Новый заказ!*\n\n"
                f"{items_text}\n"
                f"📍 Адрес: {address}\n"
                f"💰 Сумма: {total} ₽\n"
                f"👤 От: @{username}"
            )
        )

    except Exception as e:
        logging.exception("Ошибка при обработке WebAppData")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
