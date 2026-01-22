# coding: utf-8
"""
Отмена и восстановление маршрута водителем
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import database
import logging

router = Router(name="my_routes_cancel")

def _get_route_status(route_id: int, driver_id: int) -> str:
    """Определяет статус маршрута на основе заявок"""
    route = database.get_route_by_id(route_id)
    if not route:
        return "❌ Ошибка"
    
    # Проверяем is_active
    is_active = route.get('is_active', 1)
    if is_active == 0:
        return "❌ Отменена"
    
    # Получаем заявки
    requests = database.get_route_requests(route_id)
    
    # Проверяем есть ли принятые заявки
    accepted = any(r.get('status') == 'accepted' for r in requests)
    if accepted:
        return "✅ Заявка принята!"
    
    # Проверяем есть ли отклоненные заявки (и нет принятых)
    rejected = any(r.get('status') == 'rejected' for r in requests)
    if rejected:
        return "❌ Заявка отклонена"
    
    # По умолчанию - опубликована
    return "✅ Опубликована"

def _kb_route_actions_cancelled(route_id: int) -> InlineKeyboardMarkup:
    """Кнопки для ОТМЕНЁННОГО маршрута"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁️ Детали", callback_data=f"myroutes:details:{route_id}"),
            InlineKeyboardButton(text="🔄 Восстановить", callback_data=f"myroutes:restore:{route_id}")
        ]
    ])

def _kb_confirm(route_id: int) -> InlineKeyboardMarkup:
    """Кнопки подтверждения отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"myroutes:cancel_confirm:{route_id}"),
            InlineKeyboardButton(text="❌ Нет, оставить", callback_data=f"myroutes:cancel_no:{route_id}")
        ]
    ])

@router.callback_query(F.data.startswith("myroutes:cancel:"))
async def show_cancel_confirmation(call: CallbackQuery) -> None:
    """
    Показывает подтверждение отмены маршрута
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

    # Проверяем что это маршрут текущего водителя
    driver_id = call.from_user.id
    if route.get("user_id") != driver_id:
        await call.answer("❌ Это не ваш маршрут", show_alert=True)
        return

    # Получаем количество откликов (ПРИНЯТЫЕ + ОЖИДАЮЩИЕ)
    requests = database.get_route_requests(route_id)
    accepted_count = sum(1 for r in requests if r.get('status') == 'accepted')
    pending_count = sum(1 for r in requests if r.get('status') == 'pending')
    total_count = accepted_count + pending_count

    # Формируем текст подтверждения
    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")

    text = (
        f"⚠️ <b>Вы уверены?</b>\n\n"
        f"Маршрут: {from_location} → {to_location}\n"
        f"Дата: {date_dmy}г. {time_hm}\n\n"
    )

    if total_count > 0:
        text += f"Откликов: {total_count} человек(а)\n"
        if accepted_count > 0:
            text += f"Принято: {accepted_count}\n"
        if pending_count > 0:
            text += f"Ожидает: {pending_count}\n"
        text += "\nОни получат уведомление об отмене."
    else:
        text += "Пока нет откликов."

    # Отправляем подтверждение
    await call.message.edit_text(
        text,
        reply_markup=_kb_confirm(route_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("myroutes:cancel_confirm:"))
async def cancel_route(call: CallbackQuery) -> None:
    """
    БАГ #7: Отменяет маршрут и отправляет уведомления ВСЕМ пассажирам (accepted + pending)
    Карточка ОСТАЁТСЯ с изменёнными кнопками
    """
    # Получаем route_id из callback
    route_id_str = call.data.split(":")[-1]
    try:
        route_id = int(route_id_str)
    except ValueError:
        await call.answer("❌ Ошибка", show_alert=True)
        return

    # Получаем информацию о маршруте
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    # Проверяем что это маршрут текущего водителя
    driver_id = call.from_user.id
    if route.get("user_id") != driver_id:
        await call.answer("❌ Это не ваш маршрут", show_alert=True)
        return

    # Получаем данные маршрута для уведомления
    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "")

    # Получаем всех пассажиров с откликами (БАГ #7: ВКЛЮЧАЕМ И ПРИНЯТЫХ!)
    requests = database.get_route_requests(route_id)
    passengers_to_notify = [r for r in requests if r.get('status') in ['pending', 'accepted']]

    # Отменяем маршрут В БАЗЕ
    database.cancel_route(route_id)

    # Формируем уведомление для пассажиров
    notification_text = (
        f"❌ <b>МАРШРУТ {from_location} → {to_location} ОТМЕНЁН!</b>\n\n"
        f"Дата: {date_dmy}\n"
        f"Время: {time_hm}\n\n"
        f"К сожалению, водитель отменил этот маршрут.\n\n"
        f"📱 Попробуйте найти другой в разделе \"Найти маршрут\""
    )

    # Отправляем уведомления каждому пассажиру
    sent_count = 0
    for req in passengers_to_notify:
        passenger_id = req.get('passenger_id')
        try:
            await call.bot.send_message(
                chat_id=passenger_id,
                text=notification_text,
                parse_mode="HTML",
                disable_notification=False  # Звук уведомления ВКЛЮЧЁН
            )
            sent_count += 1
            logging.info(f"✅ Уведомление об отмене маршрута отправлено пассажиру {passenger_id}")
        except Exception as e:
            logging.error(f"❌ Не удалось уведомить пассажира {passenger_id}: {e}")

    # ВМЕСТО УДАЛЕНИЯ - ПОКАЗЫВАЕМ ОБНОВЛЁННУЮ КАРТОЧКУ
    card = (
        f"• {date_dmy}г. {time_hm} — {from_location} → {to_location} | "
        f"цена: {price}₽ | мест: {seats}\n"
    )

    if comment:
        card += f"💬 {comment}\n"

    # Статус ОТМЕНЕНА
    card += f"\n❌ Отменена"

    # Редактируем карточку с новыми кнопками
    await call.message.edit_text(
        card,
        reply_markup=_kb_route_actions_cancelled(route_id),
        parse_mode="HTML"
    )

    # Показываем уведомление водителю
    notification = f"✅ Маршрут отменен"
    if sent_count > 0:
        notification += f"\nПассажирам отправлены уведомления ({sent_count} чел.)"

    await call.answer(notification, show_alert=True)


@router.callback_query(F.data.startswith("myroutes:restore:"))
async def restore_route(call: CallbackQuery) -> None:
    """
    Восстанавливает отменённый маршрут и уведомляет пассажиров
    """
    # Получаем route_id из callback
    route_id_str = call.data.split(":")[-1]
    try:
        route_id = int(route_id_str)
    except ValueError:
        await call.answer("❌ Ошибка", show_alert=True)
        return

    # Получаем информацию о маршруте
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    # Проверяем что это маршрут текущего водителя
    driver_id = call.from_user.id
    if route.get("user_id") != driver_id:
        await call.answer("❌ Это не ваш маршрут", show_alert=True)
        return

    # Проверяем что маршрут отменён
    is_active = route.get("is_active", 1)
    if is_active == 1:
        await call.answer("⚠️ Маршрут уже активен", show_alert=True)
        return

    # Получаем данные маршрута для уведомления
    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "")

    # Восстанавливаем маршрут В БАЗЕ (is_active = 1)
    database.update_route(route_id, is_active=1)

    # ИСПРАВЛЕНИЕ: Уведомляем пассажиров с принятыми заявками о восстановлении
    requests = database.get_route_requests(route_id)
    accepted_passengers = [r for r in requests if r.get('status') == 'accepted']
    
    sent_count = 0
    if accepted_passengers:
        notification_text = (
            f"✅ <b>МАРШРУТ {from_location} → {to_location} ВОССТАНОВЛЕН!</b>\n\n"
            f"Дата: {date_dmy}\n"
            f"Время: {time_hm}\n\n"
            f"Водитель восстановил этот маршрут.\n\n"
            f"📱 Проверьте детали в \"Мои поездки\""
        )
        
        for req in accepted_passengers:
            passenger_id = req.get('passenger_id')
            try:
                await call.bot.send_message(
                    chat_id=passenger_id,
                    text=notification_text,
                    parse_mode="HTML",
                    disable_notification=False
                )
                sent_count += 1
                logging.info(f"✅ Уведомление о восстановлении отправлено пассажиру {passenger_id}")
            except Exception as e:
                logging.error(f"❌ Не удалось уведомить пассажира {passenger_id}: {e}")

    # Импортируем функцию с правильными кнопками для АКТИВНОГО маршрута
    from handlers.my_routes.details_handler import _kb_route_actions

    # Формируем карточку
    card = (
        f"• {date_dmy}г. {time_hm} — {from_location} → {to_location} | "
        f"цена: {price}₽ | мест: {seats}\n"
    )

    if comment:
        card += f"💬 {comment}\n"

    # Статус
    status = _get_route_status(route_id, driver_id)
    card += f"\n{status}"

    # Редактируем карточку с кнопками для АКТИВНОГО маршрута
    await call.message.edit_text(
        card,
        reply_markup=_kb_route_actions(route_id, 1),  # is_active=1
        parse_mode="HTML"
    )

    # Показываем уведомление водителю
    notification = "✅ Маршрут восстановлен"
    if sent_count > 0:
        notification += f"\nПассажирам отправлены уведомления ({sent_count} чел.)"

    await call.answer(notification, show_alert=True)


@router.callback_query(F.data.startswith("myroutes:cancel_no:"))
async def cancel_no(call: CallbackQuery) -> None:
    """
    Отказ от отмены - возвращает к карточке маршрута
    """
    # Получаем route_id из callback
    route_id_str = call.data.split(":")[-1]
    try:
        route_id = int(route_id_str)
    except ValueError:
        await call.answer("❌ Ошибка", show_alert=True)
        return

    # Получаем информацию о маршруте
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    driver_id = call.from_user.id

    # Восстанавливаем карточку (импортируем функции из details_handler)
    from handlers.my_routes.details_handler import _kb_route_actions

    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "")
    is_active = route.get("is_active", 1)

    # Карточка маршрута
    card = (
        f"• {date_dmy}г. {time_hm} — {from_location} → {to_location} | "
        f"цена: {price}₽ | мест: {seats}\n"
    )

    # Добавляем комментарий если есть
    if comment:
        card += f"💬 {comment}\n"

    # Статус
    status = _get_route_status(route_id, driver_id)
    card += f"\n{status}"

    # Редактируем сообщение обратно в карточку (передаём is_active)
    await call.message.edit_text(
        card,
        reply_markup=_kb_route_actions(route_id, is_active),
        parse_mode="HTML"
    )
    await call.answer("Отмена отменена 😉")