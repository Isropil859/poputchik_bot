# file: handlers/my_trips/list_handler.py
"""
Мои поездки - список заявок пассажира с пагинацией.
Показывает по 5 заявок на странице с кнопками навигации.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime
import database

router = Router(name="my_trips")

ITEMS_PER_PAGE = 5  # Количество поездок на странице

def _format_datetime(dt_str: str) -> str:
    """Преобразует дату и время в формат: 01.11.2025г. 14:30"""
    try:
        dt_obj = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
        return dt_obj.strftime('%d.%m.%Yг. %H:%M')
    except:
        return dt_str

def _get_status_emoji(status: str) -> str:
    """Возвращает эмодзи для статуса"""
    if status == "pending":
        return "⏳ Ожидает подтверждения"
    elif status == "accepted":
        return "✅ Подтверждена"
    elif status == "rejected":
        return "❌ Отклонена"
    elif status == "cancelled":
        return "🚫 Отменена"
    else:
        return "❓ Неизвестно"

def _make_trip_keyboard(req_id: int, route_id: int, driver_id: int, status: str) -> InlineKeyboardMarkup:
    """Клавиатура для карточки поездки"""
    buttons = []
    
    # Кнопка "Написать" доступна только для подтверждённых поездок
    if status == "accepted":
        buttons.append(InlineKeyboardButton(
            text="💬 Написать",
            callback_data=f"route:chat:{route_id}"
        ))
    
    # Кнопка "Отменить" доступна только для pending и accepted
    if status in ["pending", "accepted"]:
        buttons.append(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"mytrips:cancel:{req_id}"
        ))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])

def _make_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура пагинации"""
    buttons = []
    
    # Кнопки навигации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text="← Назад",
            callback_data=f"mytrips:page:{page-1}"
        ))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперёд →",
            callback_data=f"mytrips:page:{page+1}"
        ))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопка "Главное меню"
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:home")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def _show_trips_page(call: CallbackQuery, page: int = 1) -> None:
    """Показать страницу поездок"""
    passenger_id = call.from_user.id
    
    # Получаем список всех поездок
    all_trips = database.get_passenger_trips(passenger_id, limit=100)
    
    if not all_trips:
        await call.message.edit_text(
            "🎫 <b>МОИ ПОЕЗДКИ</b>\n\n"
            "У вас пока нет поездок.\n\n"
            "Найдите маршрут и откликнитесь, чтобы отправиться в путь! 🚗",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:home")]
            ]),
            parse_mode="HTML"
        )
        return
    
    # Рассчитываем пагинацию
    total_trips = len(all_trips)
    total_pages = (total_trips + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(1, min(page, total_pages))  # Ограничиваем страницу
    
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_trips)
    page_trips = all_trips[start_idx:end_idx]
    
    # Отправляем заголовок
    await call.message.edit_text(
        f"🎫 <b>МОИ ПОЕЗДКИ</b>\n\n"
        f"Страница {page} из {total_pages}\n"
        f"Показано: {start_idx + 1}-{end_idx} из {total_trips}",
        parse_mode="HTML"
    )
    
    # Отправляем карточки поездок
    for trip in page_trips:
        from_city = trip.get('from_city', '?')
        to_city = trip.get('to_city', '?')
        departure_time = trip.get('departure_time', '?')
        price = trip.get('price', '?')
        driver_username = trip.get('driver_username', 'Неизвестен')
        status = trip.get('status', 'pending')
        req_id = trip.get('req_id')
        route_id = trip.get('route_id')
        driver_id = trip.get('driver_id')
        
        # Форматируем дату
        formatted_time = _format_datetime(departure_time)
        status_text = _get_status_emoji(status)
        
        # Формируем текст карточки
        card_text = (
            f"📍 <b>{from_city} → {to_city}</b>\n"
            f"🕐 {formatted_time}\n"
            f"💰 Цена: {price}₽\n"
            f"👤 Водитель: @{driver_username}\n"
            f"📊 Статус: {status_text}"
        )
        
        # Отправляем карточку
        await call.message.answer(
            card_text,
            reply_markup=_make_trip_keyboard(req_id, route_id, driver_id, status),
            parse_mode="HTML"
        )
    
    # Футер с навигацией
    await call.message.answer(
        "👋 <b>Выберите действие:</b>",
        reply_markup=_make_pagination_keyboard(page, total_pages),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu:my_trips")
async def show_my_trips(call: CallbackQuery, state: FSMContext) -> None:
    """Показать список поездок пассажира (первая страница)"""
    await _show_trips_page(call, page=1)
    await call.answer()

@router.callback_query(F.data.startswith("mytrips:page:"))
async def show_trips_page(call: CallbackQuery, state: FSMContext) -> None:
    """Показать конкретную страницу поездок"""
    page_str = call.data.split(":")[-1]
    try:
        page = int(page_str)
    except ValueError:
        await call.answer("❌ Ошибка: неверный номер страницы", show_alert=True)
        return
    
    await _show_trips_page(call, page=page)
    await call.answer()

@router.callback_query(F.data.startswith("mytrips:cancel:"))
async def cancel_trip(call: CallbackQuery, state: FSMContext) -> None:
    """Отменить поездку"""
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
    
    # Проверяем что заявка в статусе pending или accepted
    status = request.get("status")
    if status not in ["pending", "accepted"]:
        await call.answer("❌ Эту заявку нельзя отменить", show_alert=True)
        return
    
    route_id = request.get("route_id")
    passenger_id = request.get("passenger_id")
    
    # Проверяем что это заявка текущего пользователя
    if passenger_id != call.from_user.id:
        await call.answer("❌ Это не ваша заявка", show_alert=True)
        return
    
    # Получаем информацию о маршруте
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return
    
    driver_id = route.get("driver_id")
    from_city = route.get("from_city", "?")
    to_city = route.get("to_city", "?")
    
    # Обновляем статус заявки на cancelled
    database.update_request_status(req_id, "cancelled")
    
    # Если заявка была accepted, возвращаем место
    # TODO: нужна функция increase_seats в database.py
    
    # Уведомляем водителя
    driver_text = (
        f"🚫 <b>Пассажир отменил поездку</b>\n\n"
        f"📍 Маршрут: {from_city} → {to_city}\n"
        f"👤 Пассажир: @{call.from_user.username or 'Пассажир'}"
    )
    
    try:
        await call.bot.send_message(
            chat_id=driver_id,
            text=driver_text,
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    # Обновляем карточку у пассажира
    if call.message:
        try:
            await call.message.edit_text(
                f"{call.message.text}\n\n🚫 <b>Поездка отменена</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    await call.answer("✅ Поездка отменена. Водитель получил уведомление.")