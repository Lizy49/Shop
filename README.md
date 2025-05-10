```python
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

```python

```