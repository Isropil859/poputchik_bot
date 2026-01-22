# coding: utf-8
"""
Система откликов на маршруты.
Обрабатывает:
- Кнопку "Откликнуться" от пассажира
- Уведомление водителю с кнопками "Принять"/"Отклонить"
- Обновление количества мест
- Уведомление пассажиру о решении
- Автоматическое обновление карточек
- Кнопку "Чат" - показывает инструкцию для связи с водителем
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime
import database

router = Router(name="reply_system")

# ==== Вспомогательные функции ================================================

def _format_route_card(route: dict, passenger_id: int = None) -> str:
    """Форматирование карточки маршрута"""
    from_location = route.get('from_location', '—')
    to_location = route.get('to_location', '—')
    date_dmy = route.get('date_dmy', '—')
    time_hm = route.get('time_hm', '—')
    price = route.get('price', 0)
    seats = route.get('seats', 0)
    comment = route.get('comment', '')

    # Формируем карточку
    card = f"• {date_dmy}г. {time_hm} — {from_location} → {to_location} | цена: {price}₽ | мест: {seats}"

    if comment:
        card += f"\n💬 {comment}"

    # Проверяем статус заявки пассажира
    if passenger_id:
        route_id = route.get('id')
        if route_id:
            status = database.get_passenger_request_status(route_id, passenger_id)
            if status == 'pending':
                card += "\n\n⏳ <b>Заявка отправлена</b>"
            elif status == 'rejected':
                card += "\n\n❌ <b>Заявка отклонена</b>"
            elif status == 'accepted':
                card += "\n\n✅ <b>Заявка принята!</b>"

    return card

def _make_route_card_keyboard(route_id: int, driver_id: int = None) -> InlineKeyboardMarkup:
    """
    БАГ #18: Клавиатура карточки маршрута с кнопками Профиль/Откликнуться/Чат
    """
    buttons = []
    
    # Кнопка "Профиль водителя" - ТОЛЬКО если есть driver_id
    if driver_id:
        buttons.append(InlineKeyboardButton(
            text="👤 Профиль",
            callback_data=f"driver:profile:{driver_id}"
        ))
    
    # Кнопка "Откликнуться"
    buttons.append(InlineKeyboardButton(
        text="👋 Откликнуться",
        callback_data=f"rs:card:reply:{route_id}"
    ))
    
    # Кнопка "Чат" - получаем username из БД
    if driver_id:
        driver = database.get_user_by_id(driver_id)
        driver_username = driver.get('tg_username') if driver else None
        
        # Строгая проверка username
        if database.is_valid_telegram_username(driver_username):
            # URL-кнопка - сразу открывает чат
            buttons.append(InlineKeyboardButton(
                text="💬 Чат",
                url=f"https://t.me/{driver_username.strip()}"
            ))
        else:
            # Если нет username - показываем инструкцию
            buttons.append(InlineKeyboardButton(
                text="💬 Чат",
                callback_data=f"route:chat:open:{route_id}"
            ))
    else:
        # Если нет driver_id - показываем инструкцию
        buttons.append(InlineKeyboardButton(
            text="💬 Чат",
            callback_data=f"route:chat:open:{route_id}"
        ))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

# ==== Клавиатуры =============================================================

def _kb_driver_decision(req_id: int) -> InlineKeyboardMarkup:
    """Кнопки для водителя: Принять/Отклонить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"reply:accept:{req_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reply:reject:{req_id}")
        ]
    ])

def _footer_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура футера с навигацией"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
            InlineKeyboardButton(text="🔍 Поиск", callback_data="search:start")
        ]
    ])

# ==== Обработчики ============================================================

@router.callback_query(F.data.startswith("rs:card:reply:"))
async def on_passenger_reply(call: CallbackQuery, state: FSMContext) -> None:
    """
    Пассажир нажал "Откликнуться".
    1. Создаём заявку в БД
    2. Отправляем уведомление водителю
    3. РЕДАКТИРУЕМ текущую карточку - добавляем статус
    4. СОХРАНЯЕМ message_id карточки в БД
    """
    # Получаем route_id из callback
    route_id_str = call.data.split(":")[-1]
    try:
        route_id = int(route_id_str)
    except ValueError:
        await call.answer("❌ Ошибка: неверный ID маршрута", show_alert=True)
        return

    # Получаем информацию о маршруте
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    # Проверяем, активен ли маршрут
    if not route.get("is_active"):
        await call.answer("❌ Маршрут неактивен", show_alert=True)
        return

    # Проверяем, есть ли свободные места
    seats = route.get("seats", 0)
    if seats <= 0:
        await call.answer("❌ Мест больше нет", show_alert=True)
        return

    # ID пассажира
    passenger_id = call.from_user.id
    passenger_username = call.from_user.username or "Пассажир"

    # Получаем ID водителя
    driver_id = route.get("user_id")
    if not driver_id:
        await call.answer("❌ Водитель не найден", show_alert=True)
        return

    # ЗАКОММЕНТИРОВАНО ДЛЯ ТЕСТИРОВАНИЯ с одного устройства
    # Проверяем, не водитель ли сам откликается на свой маршрут
    # РАСКОММЕНТИРУЙ эти строки после тестирования!
    # if passenger_id == driver_id:
    #     await call.answer("❌ Вы не можете откликнуться на свой маршрут", show_alert=True)
    #     return

    # Сохраняем пользователя в БД
    database.create_user(passenger_id, passenger_username)

    # Создаём заявку в БД
    req_id = database.create_request(route_id, passenger_id)
    if not req_id:
        await call.answer("⚠️ Вы уже откликались на этот маршрут", show_alert=True)
        return

    # Формируем текст уведомления для водителя
    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", "?")

    driver_text = (
        f"🔔 <b>Новая заявка на маршрут!</b>\n\n"
        f"📍 Маршрут: {from_location} → {to_location}\n"
        f"📅 Дата: {date_dmy}г.\n"
        f"🕐 Время: {time_hm}\n"
        f"💰 Цена: {price}₽\n\n"
        f"👤 Пассажир: @{passenger_username}\n\n"
        f"Принять заявку?"
    )

    # Отправляем уведомление водителю
    try:
        await call.bot.send_message(
            chat_id=driver_id,
            text=driver_text,
            reply_markup=_kb_driver_decision(req_id),
            parse_mode="HTML"
        )
    except Exception as e:
        await call.answer("❌ Не удалось отправить уведомление водителю", show_alert=True)
        return

    await call.answer("✅ Заявка отправлена водителю!")

    # РЕДАКТИРУЕМ текущую карточку
    try:
        # Получаем обновленные данные маршрута
        route_updated = database.get_route_by_id(route_id)
        
        # Формируем карточку с новым статусом
        card_text = _format_route_card(route_updated, passenger_id=passenger_id)
        kb = _make_route_card_keyboard(route_id, driver_id)
        
        # РЕДАКТИРУЕМ текущее сообщение
        edited_msg = await call.message.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
        
        # СОХРАНЯЕМ message_id в БД для последующего обновления
        database.update_request_card_info(req_id, edited_msg.chat.id, edited_msg.message_id)
    except Exception as e:
        # Если редактирование не удалось
        pass


@router.callback_query(F.data.startswith("reply:accept:"))
async def on_driver_accept(call: CallbackQuery, state: FSMContext) -> None:
    """
    Водитель принял заявку.
    1. Обновляем статус заявки
    2. Уменьшаем количество мест
    3. Уведомляем пассажира
    4. АВТОМАТИЧЕСКИ ОБНОВЛЯЕМ карточку у пассажира
    """
    # Получаем req_id
    req_id_str = call.data.split(":")[-1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        await call.answer("❌ Ошибка: неверный ID заявки", show_alert=True)
        return

    # Получаем информацию о заявке
    request = database.get_request_by_id(req_id)
    if not request:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    # Проверяем статус заявки
    if request.get("status") != "pending":
        await call.answer("❌ Заявка уже обработана", show_alert=True)
        return

    route_id = request.get("route_id")
    passenger_id = request.get("passenger_id")

    # Получаем информацию о маршруте
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    # Проверяем, есть ли свободные места
    seats = route.get("seats", 0)
    if seats <= 0:
        await call.answer("❌ Мест больше нет", show_alert=True)
        return

    # Обновляем статус заявки
    database.update_request_status(req_id, "accepted")

    # Уменьшаем количество мест
    new_seats = seats - 1
    database.update_route(route_id, seats=new_seats)

    # Формируем текст уведомления для пассажира
    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", "?")

    # Получаем username водителя (тот кто нажал "Принять")
    driver_username = call.from_user.username

    # Добавляем строку с водителем
    driver_contact = ""
    if driver_username:
        driver_contact = f"👤 Водитель: @{driver_username}\n\n"

    passenger_text = (
        f"🎉 <b>Ваша заявка принята!</b>\n\n"
        f"📍 Маршрут: {from_location} → {to_location}\n"
        f"📅 Дата: {date_dmy}г.\n"
        f"🕐 Время: {time_hm}\n"
        f"💰 Цена: {price}₽\n\n"
        f"{driver_contact}"
        f"Водитель подтвердил вашу поездку. "
        f"Свяжитесь с ним для уточнения деталей."
    )

    # Отправляем уведомление пассажиру
    try:
        await call.bot.send_message(
            chat_id=passenger_id,
            text=passenger_text,
            parse_mode="HTML"
        )
    except Exception:
        pass

    # АВТОМАТИЧЕСКИ ОБНОВЛЯЕМ карточку у пассажира
    try:
        card_chat_id = request.get("card_chat_id")
        card_message_id = request.get("card_message_id")
        
        if card_chat_id and card_message_id:
            # Получаем обновленные данные маршрута
            route_updated = database.get_route_by_id(route_id)
            
            # Формируем карточку с новым статусом
            card_text = _format_route_card(route_updated, passenger_id=passenger_id)
            driver_id = route.get("user_id")
            kb = _make_route_card_keyboard(route_id, driver_id)
            
            # РЕДАКТИРУЕМ карточку у пассажира
            await call.bot.edit_message_text(
                chat_id=card_chat_id,
                message_id=card_message_id,
                text=card_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
    except Exception:
        pass

    # Обновляем сообщение водителя
    if call.message:
        try:
            await call.message.edit_text(
                f"{call.message.text}\n\n✅ <b>Заявка принята!</b>\n"
                f"Осталось мест: <b>{new_seats}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await call.answer("✅ Заявка принята! Пассажиру отправлено уведомление.")


@router.callback_query(F.data.startswith("reply:reject:"))
async def on_driver_reject(call: CallbackQuery, state: FSMContext) -> None:
    """
    БАГ #18: Водитель отклонил заявку - передаём driver_id в клавиатуру!
    1. Обновляем статус заявки
    2. Уведомляем пассажира
    3. АВТОМАТИЧЕСКИ ОБНОВЛЯЕМ карточку у пассажира
    """
    # Получаем req_id
    req_id_str = call.data.split(":")[-1]
    try:
        req_id = int(req_id_str)
    except ValueError:
        await call.answer("❌ Ошибка: неверный ID заявки", show_alert=True)
        return

    # Получаем информацию о заявке
    request = database.get_request_by_id(req_id)
    if not request:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return

    # Проверяем статус заявки
    if request.get("status") != "pending":
        await call.answer("❌ Заявка уже обработана", show_alert=True)
        return

    route_id = request.get("route_id")
    passenger_id = request.get("passenger_id")

    # Обновляем статус заявки
    database.update_request_status(req_id, "rejected")

    # Получаем информацию о маршруте для уведомления
    route = database.get_route_by_id(route_id)
    from_location = route.get("from_location", "?") if route else "?"
    to_location = route.get("to_location", "?") if route else "?"

    # Формируем текст уведомления для пассажира
    passenger_text = (
        f"😔 <b>Ваша заявка отклонена</b>\n\n"
        f"📍 Маршрут: {from_location} → {to_location}\n\n"
        f"К сожалению, водитель не смог принять вашу заявку. "
        f"Попробуйте найти другой маршрут."
    )

    # Отправляем уведомление пассажиру
    try:
        await call.bot.send_message(
            chat_id=passenger_id,
            text=passenger_text,
            parse_mode="HTML"
        )
    except Exception:
        pass

    # АВТОМАТИЧЕСКИ ОБНОВЛЯЕМ карточку у пассажира
    try:
        card_chat_id = request.get("card_chat_id")
        card_message_id = request.get("card_message_id")
        
        if card_chat_id and card_message_id:
            # Получаем обновленные данные маршрута
            route_updated = database.get_route_by_id(route_id)
            
            # Формируем карточку с новым статусом
            card_text = _format_route_card(route_updated, passenger_id=passenger_id)
            driver_id = route.get("user_id") if route else None
            kb = _make_route_card_keyboard(route_id, driver_id)
            
            # РЕДАКТИРУЕМ карточку у пассажира
            await call.bot.edit_message_text(
                chat_id=card_chat_id,
                message_id=card_message_id,
                text=card_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
    except Exception:
        pass

    # Обновляем сообщение водителя
    if call.message:
        try:
            await call.message.edit_text(
                f"{call.message.text}\n\n❌ <b>Заявка отклонена</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await call.answer("❌ Заявка отклонена. Пассажиру отправлено уведомление.")


@router.callback_query(F.data.startswith("route:chat:open:"))
async def on_open_chat(call: CallbackQuery) -> None:
    """
    БАГ #11-12: Показывает инструкцию по открытию чата с водителем.
    Работает и на телефоне, и на компьютере!
    """
    route_id_str = call.data.split(":")[-1]
    try:
        route_id = int(route_id_str)
    except ValueError:
        await call.answer("❌ Ошибка", show_alert=True)
        return
    
    # Получаем маршрут
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return
    
    driver_id = route.get("user_id")
    if not driver_id:
        await call.answer("❌ Водитель не найден", show_alert=True)
        return
    
    # Получаем username водителя
    driver = database.get_user_by_id(driver_id)
    driver_username = driver.get('tg_username') if driver else None
    
    if not driver_username:
        await call.answer(
            "❌ У водителя не указан username в Telegram.\n"
            "Попросите водителя добавить username в настройках.",
            show_alert=True
        )
        return
    
    # Показываем инструкцию
    instruction = (
        f"💬 <b>Как написать водителю:</b>\n\n"
        f"1️⃣ Откройте поиск в Telegram\n"
        f"2️⃣ Введите: <code>@{driver_username}</code>\n"
        f"3️⃣ Нажмите на профиль водителя\n"
        f"4️⃣ Начните диалог\n\n"
        f"<i>Скопируйте username водителя:</i>\n"
        f"<code>@{driver_username}</code>"
    )
    
    await call.answer()
    await call.bot.send_message(
        chat_id=call.from_user.id,
        text=instruction,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("route:chat:error:"))
async def on_chat_error(call: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик ошибки - у водителя нет username.
    """
    await call.answer(
        "❌ У водителя не указан username в Telegram.\n"
        "Попросите водителя добавить username в настройках Telegram.",
        show_alert=True
    )


@router.callback_query(F.data == "driver:profile:close")
async def close_driver_profile(callback: CallbackQuery):
    """БАГ #18: Закрыть профиль водителя - ПЕРВЫЙ обработчик (точное совпадение)"""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("driver:profile:"))
async def show_driver_profile(callback: CallbackQuery):
    """БАГ #18: Показать ПОЛНЫЙ профиль водителя - ВТОРОЙ обработчик (начинается с)"""
    driver_id_str = callback.data.split(":")[-1]
    
    if not driver_id_str or driver_id_str == "None":
        await callback.answer("❌ Ошибка: водитель не найден", show_alert=True)
        return
    
    try:
        driver_id = int(driver_id_str)
    except (ValueError, TypeError):
        await callback.answer("❌ Ошибка: неверный ID водителя", show_alert=True)
        return
    
    # Получаем профиль водителя
    profile = database.get_user_profile(driver_id)
    
    if not profile:
        await callback.answer("❌ Профиль водителя не найден", show_alert=True)
        return
    
    # Формируем текст профиля
    driver_name = profile.get('display_name', 'Имя не указано')
    driver_bio = profile.get('bio', 'Описание не указано')
    routes_count = profile.get('routes_count', 0)
    photo_file_id = profile.get('photo_file_id')
    
    text = (
        f"👤 <b>ПРОФИЛЬ ВОДИТЕЛЯ</b>\n\n"
        f"🆔 Имя: {driver_name}\n"
        f"⭐ Рейтинг: Пока нет отзывов\n"
        f"🚗 Маршрутов создано: {routes_count}\n"
        f"💬 Описание: {driver_bio}"
    )
    
    # Клавиатура
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data="driver:profile:close")]
    ])
    
    # Отправляем профиль
    if photo_file_id:
        try:
            await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback.answer()
        except Exception:
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback.answer()
    else:
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()