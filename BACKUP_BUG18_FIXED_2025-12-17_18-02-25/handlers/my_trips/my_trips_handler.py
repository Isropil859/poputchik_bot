from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database
import logging

router = Router()

def _get_trip_status(trip):
    """Определить статус заявки для отображения"""
    # Проверяем сначала is_active маршрута
    if trip['is_active'] == 0:
        return "маршрут отменен"
    
    # Потом статус заявки
    status = trip['status']
    if status == 'pending':
        return "заявка отправлена"
    elif status == 'accepted':
        return "заявка принята"
    elif status == 'rejected':
        return "заявка отклонена"
    elif status == 'cancelled':
        return "отменена"
    else:
        return "неизвестный статус"

def _format_trip_card(trip):
    """Форматирование карточки заявки С ПРОФИЛЕМ ВОДИТЕЛЯ"""
    # Получаем профиль водителя
    driver_id = trip.get('driver_id')
    driver_profile = database.get_user_profile(driver_id) if driver_id else None
    
    # Данные маршрута
    date = trip['date_dmy']
    time = trip['time_hm']
    from_loc = trip['from_location']
    to_loc = trip['to_location']
    price = trip['price']
    seats = trip['seats']
    comment = trip.get('comment', '').strip()
    
    # Формируем карточку С ПРОФИЛЕМ ВОДИТЕЛЯ
    card = ""
    
    # БЛОК ПРОФИЛЯ ВОДИТЕЛЯ
    if driver_profile:
        driver_name = driver_profile.get('display_name', 'Имя не указано')
        driver_bio = driver_profile.get('bio', '')
        
        card += "👤 <b>ВОДИТЕЛЬ:</b>\n"
        card += f"🆔 {driver_name}\n"
        
        if driver_bio:
            # Обрезаем описание если слишком длинное
            if len(driver_bio) > 60:
                driver_bio = driver_bio[:60] + "..."
            card += f"💬 {driver_bio}\n"
        
        card += "\n"
    
    # БЛОК МАРШРУТА
    card += f"📍 <b>Маршрут:</b> {from_loc} → {to_loc}\n"
    card += f"📅 {date} | 🕐 {time}\n"
    card += f"💰 {price}₽ | 💺 {seats} мест"
    
    # Комментарий к маршруту
    if comment:
        card += f"\n💬 <b>О поездке:</b> {comment}"
    
    # Добавляем статус
    status = _get_trip_status(trip)
    card += f"\n\n📊 <b>Статус:</b> {status}"
    
    return card

def _make_trip_card_keyboard(trip):
    """Клавиатура для карточки заявки"""
    buttons = []
    
    request_id = trip['request_id']
    driver_id = trip['driver_id']
    status = trip['status']
    is_active = trip['is_active']
    
    # Кнопка "Профиль водителя" - ТОЛЬКО если есть driver_id
    if driver_id:
        buttons.append(InlineKeyboardButton(
            text="👤 Профиль",
            callback_data=f"driver:profile:{driver_id}"
        ))
    
    # Кнопка "Отменить" - только для НЕотмененных заявок и активных маршрутов
    if status not in ['cancelled'] and is_active == 1:
        buttons.append(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"mytrips:cancel:{request_id}"
        ))
    
    # Кнопка "Чат" - ВСЕГДА показываем (даже для отмененных)
    driver = database.get_user_by_id(driver_id)
    driver_username = driver.get('tg_username') if driver else None
    
    # ИСПРАВЛЕНО: Строгая проверка username (не None, не пустой, не пробелы)
    if database.is_valid_telegram_username(driver_username):
        buttons.append(InlineKeyboardButton(
            text="💬 Чат",
            url=f"https://t.me/{driver_username.strip()}"
        ))
    else:
        buttons.append(InlineKeyboardButton(
            text="💬 Чат",
            callback_data=f"mytrips:chat:error:{request_id}"
        ))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

@router.callback_query(F.data == "my_trips")
async def show_my_trips(callback: CallbackQuery):
    """Показать список поездок пассажира"""
    await callback.answer()
    
    user_id = callback.from_user.id
    trips = database.get_user_trips(user_id)
    
    if not trips:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]])
        
        await callback.message.edit_text(
            "🚗 У вас пока нет заявок на поездки.\n\n"
            "Найдите маршрут в разделе 🔍 Найти маршрут",
            reply_markup=keyboard
        )
        return
    
    # Отправляем каждую карточку отдельным сообщением
    for trip in trips:
        card_text = _format_trip_card(trip)
        kb = _make_trip_card_keyboard(trip)
        
        if kb:
            await callback.message.answer(card_text, reply_markup=kb, parse_mode="HTML")
        else:
            # Если нет кнопок - показываем без кнопок
            await callback.message.answer(card_text, parse_mode="HTML")
    
    # Футер с кнопкой "Главное меню"
    footer_text = f"<b>🚗 Всего поездок: {len(trips)}</b>"
    footer_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]])
    
    await callback.message.answer(footer_text, reply_markup=footer_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("mytrips:cancel:"))
async def cancel_trip_request(callback: CallbackQuery):
    """Отменить заявку пассажира"""
    await callback.answer()
    
    request_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    
    # Получаем данные заявки для уведомления водителя
    request = database.get_request_by_id(request_id)
    if not request:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    route = database.get_route_by_id(request['route_id'])
    if not route:
        await callback.answer("❌ Маршрут не найден", show_alert=True)
        return
    
    # ВАЖНО: Проверяем что заявка была принята (accepted)
    # Только принятые заявки занимают место!
    was_accepted = request['status'] == 'accepted'
    
    # Отменяем заявку
    success = database.cancel_trip_request(request_id, user_id)
    
    if not success:
        await callback.answer("❌ Не удалось отменить заявку", show_alert=True)
        return
    
    # ИСПРАВЛЕНИЕ БАГ #16: Восстанавливаем место ТОЛЬКО если заявка была принята
    if was_accepted:
        current_seats = route.get('seats', 0)
        route_id = route.get('id')
        
        # Увеличиваем количество мест на 1
        database.update_route(route_id, seats=current_seats + 1)
        
        logging.info(f"Место восстановлено для маршрута {route_id}: {current_seats} → {current_seats + 1}")
    
    # Уведомляем водителя
    driver_id = route['user_id']
    passenger_name = callback.from_user.full_name or "Пассажир"
    
    notification_text = (
        f"❌ Пассажир {passenger_name} отменил заявку на маршрут:\n\n"
        f"• {route['date_dmy']} {route['time_hm']} — "
        f"{route['from_location']} → {route['to_location']}\n"
        f"цена: {route['price']}₽"
    )
    
    try:
        await callback.bot.send_message(driver_id, notification_text)
        logging.info(f"Уведомление об отмене отправлено водителю {driver_id}")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление водителю: {e}")
    
    await callback.answer("✅ Заявка отменена", show_alert=True)
    
    # Обновляем карточку - меняем текст и убираем кнопку "Отменить", оставляем "Чат" и "Профиль"
    try:
        # Получаем обновленные данные заявки
        trips = database.get_user_trips(user_id)
        cancelled_trip = next((t for t in trips if t['request_id'] == request_id), None)
        
        if cancelled_trip:
            new_text = _format_trip_card(cancelled_trip)
            new_kb = _make_trip_card_keyboard(cancelled_trip)
            
            if new_kb:
                await callback.message.edit_text(new_text, reply_markup=new_kb, parse_mode="HTML")
            else:
                await callback.message.edit_text(new_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не удалось обновить карточку: {e}")

@router.callback_query(F.data == "driver:profile:close")
async def close_driver_profile(callback: CallbackQuery):
    """Закрыть профиль водителя"""
    try:
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        # Если не удалось удалить - просто отвечаем
        await callback.answer("✅ Закрыто")

@router.callback_query(F.data.startswith("mytrips:chat:error:"))
async def chat_error(callback: CallbackQuery):
    """Ошибка при открытии чата"""
    await callback.answer(
        "❌ У водителя не указан username в Telegram.\n"
        "Чат недоступен.",
        show_alert=True
    )