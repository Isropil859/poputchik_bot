# coding: utf-8
"""
Показ деталей маршрута: список откликов от пассажиров
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import database

router = Router(name="my_routes_details")

def _kb_route_actions(route_id: int, is_active: int) -> InlineKeyboardMarkup:
    """
    Кнопки для каждого маршрута - РАЗНЫЕ для активных и отменённых
    """
    if is_active == 1:
        # Активный маршрут: [✏️ Изменить] [❌ Отменить] [👁️ Детали]
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"myroutes:edit:{route_id}"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"myroutes:cancel:{route_id}"),
                InlineKeyboardButton(text="👁️ Детали", callback_data=f"myroutes:details:{route_id}")
            ]
        ])
    else:
        # Отменённый маршрут: [👁️ Детали] [🔄 Восстановить]
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👁️ Детали", callback_data=f"myroutes:details:{route_id}"),
                InlineKeyboardButton(text="🔄 Восстановить", callback_data=f"myroutes:restore:{route_id}")
            ]
        ])

def _kb_back(route_id: int) -> InlineKeyboardMarkup:
    """Кнопка назад к маршрутам"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 Назад к маршрутам", callback_data=f"myroutes:back:{route_id}")
        ]
    ])

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

@router.callback_query(F.data.startswith("myroutes:details:"))
async def show_route_details(call: CallbackQuery) -> None:
    """
    Показывает детали маршрута: список откликов
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

    # Получаем все заявки на этот маршрут
    requests = database.get_route_requests(route_id)

    # Формируем текст
    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    
    # ИСПРАВЛЕНИЕ: Проверяем статус маршрута
    is_active = route.get("is_active", 1)
    status_text = "❌ <b>МАРШРУТ ОТМЕНЁН</b>\n\n" if is_active == 0 else ""

    text = (
        f"👥 <b>Заявки на маршрут:</b>\n\n"
        f"{status_text}"
        f"{from_location} → {to_location}\n"
        f"{date_dmy} {time_hm}\n\n"
    )

    # Если нет заявок
    if not requests:
        text += "Пока нет откликов."
    else:
        # Счётчики
        total = len(requests)
        accepted = sum(1 for r in requests if r.get('status') == 'accepted')
        pending = sum(1 for r in requests if r.get('status') == 'pending')
        rejected = sum(1 for r in requests if r.get('status') == 'rejected')

        # Список заявок
        for req in requests:
            req_id = req.get('id')
            passenger_id = req.get('passenger_id')
            status = req.get('status')
            username = req.get('tg_username')

            # Иконка статуса
            if status == 'accepted':
                icon = "✅"
                status_text = "Принят"
            elif status == 'pending':
                icon = "⏳"
                status_text = "Ожидает ответа"
            else:  # rejected
                icon = "❌"
                status_text = "Отклонен"

            # Имя пассажира
            passenger_name = f"@{username}" if username else f"ID{passenger_id}"

            text += f"{icon} {passenger_name} - {status_text}\n"

        text += f"\nВсего откликов: {total}\n"
        text += f"Принято: {accepted}\n"
        text += f"Ожидает: {pending}\n"
        text += f"Отклонено: {rejected}"

    # Отправляем
    await call.message.edit_text(
        text,
        reply_markup=_kb_back(route_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("myroutes:back:"))
async def back_to_card(call: CallbackQuery) -> None:
    """
    Возврат к карточке маршрута (восстанавливает карточку)
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

    # Восстанавливаем карточку
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
    await call.answer()