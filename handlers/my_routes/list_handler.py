# coding: utf-8
"""
Показ списка маршрутов водителя в разделе "Мои маршруты"
"""
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import database

router = Router(name="my_routes_list")

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

def _kb_footer() -> InlineKeyboardMarkup:
    """Общий футер"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚗 Создать маршрут", callback_data="create_route:from_my_routes"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
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

@router.callback_query(F.data == "my_routes")
async def show_my_routes(call: CallbackQuery) -> None:
    """
    Показывает список активных маршрутов водителя
    """
    driver_id = call.from_user.id

    # Получаем все маршруты водителя
    my_routes = database.get_user_routes(driver_id)

    # Если нет маршрутов
    if not my_routes:
        text = (
            "🚗 <b>Мои маршруты:</b>\n\n"
            "У вас пока нет активных маршрутов."
        )
        await call.message.edit_text(text, reply_markup=_kb_footer(), parse_mode="HTML")
        await call.answer()
        return

    # Удаляем старое сообщение
    await call.message.delete()

    # Отправляем карточки для каждого маршрута
    for route in my_routes:
        route_id = route.get('id')
        from_location = route.get('from_location', '?')
        to_location = route.get('to_location', '?')
        date_dmy = route.get('date_dmy', '?')
        time_hm = route.get('time_hm', '?')
        price = route.get('price', 0)
        seats = route.get('seats', 0)
        comment = route.get('comment', '')
        is_active = route.get('is_active', 1)

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

        # Отправляем карточку с кнопками (передаём is_active)
        await call.message.answer(
            card,
            reply_markup=_kb_route_actions(route_id, is_active),
            parse_mode="HTML"
        )

    # Отправляем общий футер
    await call.message.answer(
        "<b>👋 Выберите действие:</b>",
        reply_markup=_kb_footer(),
        parse_mode="HTML"
    )

    await call.answer()