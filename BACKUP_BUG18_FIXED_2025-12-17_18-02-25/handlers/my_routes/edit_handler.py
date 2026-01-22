# coding: utf-8
"""
Изменение маршрута водителем - пошаговый мастер
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, date
import calendar
import database
import logging

router = Router(name="my_routes_edit")

class EditRoute(StatesGroup):
    """Состояния для редактирования маршрута"""
    waiting_for_value = State()

# Русские названия месяцев
MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

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

def _parse_time(time_str: str) -> str:
    """
    Умный парсинг времени:
    735 → 07:35
    0850 → 08:50
    14:30 → 14:30
    """
    time_str = time_str.strip().replace(":", "").replace(".", "").replace(" ", "")

    if time_str.isdigit():
        if len(time_str) == 3:
            hours = time_str[0]
            minutes = time_str[1:3]
            return f"0{hours}:{minutes}"
        elif len(time_str) == 4:
            hours = time_str[0:2]
            minutes = time_str[2:4]
            return f"{hours}:{minutes}"

    return time_str

def _build_calendar(year: int, month: int, current_date, route_id: int) -> InlineKeyboardMarkup:
    """Генерация календаря с правильным количеством недель (С ДНЯМИ СЛЕДУЮЩЕГО МЕСЯЦА)"""
    keyboard = []
    
    month_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    
    keyboard.append([
        InlineKeyboardButton(text="◀️", callback_data=f"editcal:prev:{year}:{month}"),
        InlineKeyboardButton(text=f"{month_names[month-1]} {year}", callback_data="editcal:ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"editcal:next:{year}:{month}")
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="Пн", callback_data="editcal:ignore"),
        InlineKeyboardButton(text="Вт", callback_data="editcal:ignore"),
        InlineKeyboardButton(text="Ср", callback_data="editcal:ignore"),
        InlineKeyboardButton(text="Чт", callback_data="editcal:ignore"),
        InlineKeyboardButton(text="Пт", callback_data="editcal:ignore"),
        InlineKeyboardButton(text="Сб", callback_data="editcal:ignore"),
        InlineKeyboardButton(text="Вс", callback_data="editcal:ignore"),
    ])
    
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    days_in_prev = calendar.monthrange(prev_year, prev_month)[1]
    days_in_current = calendar.monthrange(year, month)[1]
    
    first_day = datetime(year, month, 1).weekday()
    
    total_days = first_day + days_in_current
    num_weeks = (total_days + 6) // 7
    
    week = []
    day_counter = 0
    prev_month_start = days_in_prev - first_day + 1
    next_month_day = 1
    
    for i in range(num_weeks * 7):
        if i < first_day:
            day = prev_month_start + i
            try:
                day_date = datetime(prev_year, prev_month, day)
                if day_date.date() < current_date.date():
                    week.append(InlineKeyboardButton(text=f"·{day}", callback_data="editcal:ignore"))
                else:
                    week.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"editcal:day:{prev_year}:{prev_month}:{day}"
                    ))
            except:
                week.append(InlineKeyboardButton(text=str(day), callback_data="editcal:ignore"))
        elif day_counter < days_in_current:
            day_counter += 1
            day = day_counter
            try:
                day_date = datetime(year, month, day)
                if day_date.date() < current_date.date():
                    week.append(InlineKeyboardButton(text=f"·{day}", callback_data="editcal:ignore"))
                else:
                    week.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"editcal:day:{year}:{month}:{day}"
                    ))
            except:
                week.append(InlineKeyboardButton(text=str(day), callback_data="editcal:ignore"))
        else:
            day = next_month_day
            next_month_day += 1
            try:
                day_date = datetime(next_year, next_month, day)
                if day_date.date() < current_date.date():
                    week.append(InlineKeyboardButton(text=f"·{day}", callback_data="editcal:ignore"))
                else:
                    week.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"editcal:day:{next_year}:{next_month}:{day}"
                    ))
            except:
                week.append(InlineKeyboardButton(text=str(day), callback_data="editcal:ignore"))
        
        if len(week) == 7:
            keyboard.append(week)
            week = []
    
    # БАГ #10: Добавляем кнопку "Назад" в календарь
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"editcal:back:{route_id}")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def _notify_passengers_about_change(route_id: int, bot, changed_fields: list):
    """
    БАГ #6: Уведомляет пассажиров с принятыми заявками об изменении маршрута
    Вызывается ТОЛЬКО при нажатии кнопки "✅ Готово"
    """
    requests = database.get_route_requests(route_id)
    accepted_requests = [r for r in requests if r.get('status') == 'accepted']
    
    if not accepted_requests:
        return
    
    if not changed_fields:
        return
    
    route = database.get_route_by_id(route_id)
    if not route:
        return
    
    from_loc = route['from_location']
    to_loc = route['to_location']
    
    notification_text = f"⚠️ <b>МАРШРУТ {from_loc} → {to_loc} ИЗМЕНЁН!</b>\n\n"
    notification_text += "Водитель изменил:\n"
    
    for change in changed_fields:
        field = change['field']
        value = change['value']
        
        if field == 'from_location':
            notification_text += f"• Откуда: {value}\n"
        elif field == 'to_location':
            notification_text += f"• Куда: {value}\n"
        elif field == 'date':
            notification_text += f"• Дату: {value}\n"
        elif field == 'time':
            notification_text += f"• Время: {value}\n"
        elif field == 'price':
            notification_text += f"• Цену: {value}₽\n"
        elif field == 'seats':
            notification_text += f"• Количество мест: {value}\n"
        elif field == 'comment':
            if value:
                notification_text += f"• Комментарий: {value}\n"
            else:
                notification_text += f"• Комментарий удалён\n"
    
    notification_text += "\n📱 Проверьте детали в \"Мои поездки\""
    
    for req in accepted_requests:
        passenger_id = req.get('passenger_id')
        try:
            await bot.send_message(
                passenger_id, 
                notification_text,
                parse_mode="HTML",
                disable_notification=False
            )
            logging.info(f"✅ Уведомление об изменении отправлено пассажиру {passenger_id}")
        except Exception as e:
            logging.error(f"❌ Не удалось уведомить пассажира {passenger_id}: {e}")

def _kb_edit_menu(route_id: int) -> InlineKeyboardMarkup:
    """Меню выбора параметра для изменения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📍 Откуда", callback_data=f"myroutes:edit_field:{route_id}:from_location"),
            InlineKeyboardButton(text="📍 Куда", callback_data=f"myroutes:edit_field:{route_id}:to_location")
        ],
        [
            InlineKeyboardButton(text="📅 Дата", callback_data=f"myroutes:edit_field:{route_id}:date"),
            InlineKeyboardButton(text="🕐 Время", callback_data=f"myroutes:edit_field:{route_id}:time")
        ],
        [
            InlineKeyboardButton(text="💰 Цена", callback_data=f"myroutes:edit_field:{route_id}:price"),
            InlineKeyboardButton(text="👥 Мест", callback_data=f"myroutes:edit_field:{route_id}:seats")
        ],
        [
            InlineKeyboardButton(text="💬 Комментарий", callback_data=f"myroutes:edit_field:{route_id}:comment")
        ],
        [
            InlineKeyboardButton(text="✅ Готово", callback_data=f"myroutes:edit_done:{route_id}")
        ]
    ])

def _kb_back_and_cancel(route_id: int) -> InlineKeyboardMarkup:
    """БАГ #10: Кнопки Назад и Отменить"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"myroutes:edit_back:{route_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"myroutes:edit_cancel:{route_id}")
        ]
    ])

def _kb_comment_action(route_id: int) -> InlineKeyboardMarkup:
    """БАГ #10: Кнопки для комментария с Назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Заменить", callback_data=f"myroutes:comment_replace:{route_id}"),
            InlineKeyboardButton(text="➕ Дописать", callback_data=f"myroutes:comment_append:{route_id}")
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"myroutes:comment_delete:{route_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"myroutes:edit_back:{route_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"myroutes:edit_cancel:{route_id}")
        ]
    ])

@router.callback_query(F.data.startswith("myroutes:edit:"))
async def show_edit_menu(call: CallbackQuery, state: FSMContext) -> None:
    """Показывает меню выбора параметра для изменения"""
    route_id_str = call.data.split(":")[-1]
    try:
        route_id = int(route_id_str)
    except ValueError:
        await call.answer("❌ Ошибка: неверный ID маршрута", show_alert=True)
        return

    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    driver_id = call.from_user.id
    if route.get("user_id") != driver_id:
        await call.answer("❌ Это не ваш маршрут", show_alert=True)
        return

    await state.update_data(
        route_id=route_id,
        edit_message_id=call.message.message_id,
        changed_fields=[]
    )

    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "Нет")

    text = (
        f"✏️ <b>Изменение маршрута</b>\n\n"
        f"<b>Текущие данные:</b>\n"
        f"📍 Откуда: {from_location}\n"
        f"📍 Куда: {to_location}\n"
        f"📅 Дата: {date_dmy}\n"
        f"🕐 Время: {time_hm}\n"
        f"💰 Цена: {price}₽\n"
        f"👥 Мест: {seats}\n"
        f"💬 Комментарий: {comment}\n\n"
        f"Выберите что хотите изменить:"
    )

    await call.message.edit_text(
        text,
        reply_markup=_kb_edit_menu(route_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("myroutes:edit_field:"))
async def start_field_edit(call: CallbackQuery, state: FSMContext) -> None:
    """Начинает редактирование выбранного поля"""
    parts = call.data.split(":")
    route_id_str = parts[2]
    field_name = parts[3]

    try:
        route_id = int(route_id_str)
    except ValueError:
        await call.answer("❌ Ошибка", show_alert=True)
        return

    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    if field_name == "date":
        await state.update_data(
            route_id=route_id,
            field_name="date",
            edit_message_id=call.message.message_id
        )

        today = datetime.now()
        calendar_kb = _build_calendar(today.year, today.month, today, route_id)

        current_date = route.get("date_dmy", "?")
        
        await call.message.edit_text(
            f"📅 <b>ДАТА</b>\n\nТекущее значение: {current_date}\n\nВыберите новую дату:",
            reply_markup=calendar_kb,
            parse_mode="HTML"
        )
        await call.answer()
        return

    if field_name == "comment":
        current_comment = route.get("comment", "")

        if current_comment:
            text = (
                f"💬 <b>Текущий комментарий:</b>\n"
                f"{current_comment}\n\n"
                f"Что хотите сделать?"
            )
            await call.message.edit_text(
                text,
                reply_markup=_kb_comment_action(route_id),
                parse_mode="HTML"
            )
        else:
            await state.update_data(
                route_id=route_id,
                field_name="comment",
                comment_mode="replace",
                edit_message_id=call.message.message_id
            )
            await state.set_state(EditRoute.waiting_for_value)

            await call.message.edit_text(
                "💬 Введите комментарий:",
                reply_markup=_kb_back_and_cancel(route_id),
                parse_mode="HTML"
            )
        await call.answer()
        return

    await state.update_data(
        route_id=route_id,
        field_name=field_name,
        edit_message_id=call.message.message_id,
        error_count=0
    )
    await state.set_state(EditRoute.waiting_for_value)

    current_from = route.get('from_location', '?')
    current_to = route.get('to_location', '?')
    current_time = route.get('time_hm', '?')
    current_price = route.get('price', 0)
    current_seats = route.get('seats', 0)

    field_prompts = {
        "from_location": f"📍 <b>ОТКУДА</b>\n\nТекущее значение: {current_from}\n\nВведите новое значение:",
        "to_location": f"📍 <b>КУДА</b>\n\nТекущее значение: {current_to}\n\nВведите новое значение:",
        "time": f"🕐 <b>ВРЕМЯ</b>\n\nТекущее значение: {current_time}\n\nВведите новое время:\nФормат: ЧЧ:ММ или ЧЧММ\nНапример: 14:30 или 1430",
        "price": f"💰 <b>ЦЕНА</b>\n\nТекущее значение: {current_price}₽\n\nВведите новую цену:\nНапример: 500",
        "seats": f"👥 <b>КОЛИЧЕСТВО МЕСТ</b>\n\nТекущее значение: {current_seats}\n\nВведите новое количество мест:"
    }

    prompt = field_prompts.get(field_name, "Введите новое значение:")

    await call.message.edit_text(
        prompt,
        reply_markup=_kb_back_and_cancel(route_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("myroutes:edit_back:"))
async def back_to_edit_menu(call: CallbackQuery, state: FSMContext) -> None:
    """БАГ #10: Возврат в меню редактирования (кнопка Назад)"""
    route_id = int(call.data.split(":")[-1])
    
    # Очищаем state
    await state.clear()
    
    # Напрямую вызываем логику show_edit_menu
    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    driver_id = call.from_user.id
    if route.get("user_id") != driver_id:
        await call.answer("❌ Это не ваш маршрут", show_alert=True)
        return

    await state.update_data(
        route_id=route_id,
        edit_message_id=call.message.message_id,
        changed_fields=[]
    )

    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "Нет")

    text = (
        f"✏️ <b>Изменение маршрута</b>\n\n"
        f"<b>Текущие данные:</b>\n"
        f"📍 Откуда: {from_location}\n"
        f"📍 Куда: {to_location}\n"
        f"📅 Дата: {date_dmy}\n"
        f"🕐 Время: {time_hm}\n"
        f"💰 Цена: {price}₽\n"
        f"👥 Мест: {seats}\n"
        f"💬 Комментарий: {comment}\n\n"
        f"Выберите что хотите изменить:"
    )

    await call.message.edit_text(
        text,
        reply_markup=_kb_edit_menu(route_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("editcal:"))
async def process_calendar(call: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает клики по календарю"""
    data = await state.get_data()
    route_id = data.get("route_id")
    edit_message_id = data.get("edit_message_id")

    action = call.data.split(":")[1]

    if action == "ignore":
        await call.answer()
        return
    
    # БАГ #10: Обработка кнопки "Назад" в календаре
    elif action == "back":
        route_id = int(call.data.split(":")[-1])
        await back_to_edit_menu(call, state)
        return

    elif action == "prev":
        year = int(call.data.split(":")[2])
        month = int(call.data.split(":")[3])

        month -= 1
        if month < 1:
            month = 12
            year -= 1

        today = datetime.now()
        calendar_kb = _build_calendar(year, month, today, route_id)
        await call.message.edit_reply_markup(reply_markup=calendar_kb)
        await call.answer()

    elif action == "next":
        year = int(call.data.split(":")[2])
        month = int(call.data.split(":")[3])

        month += 1
        if month > 12:
            month = 1
            year += 1

        today = datetime.now()
        calendar_kb = _build_calendar(year, month, today, route_id)
        await call.message.edit_reply_markup(reply_markup=calendar_kb)
        await call.answer()

    elif action == "day":
        year = int(call.data.split(":")[2])
        month = int(call.data.split(":")[3])
        day = int(call.data.split(":")[4])

        selected_date = date(year, month, day)

        route = database.get_route_by_id(route_id)
        if not route:
            await call.answer("❌ Маршрут не найден", show_alert=True)
            await state.clear()
            return

        new_date_dmy = selected_date.strftime('%d.%m.%Y')
        database.update_route(route_id, date_dmy=new_date_dmy)
        
        data = await state.get_data()
        changed_fields = data.get('changed_fields', [])
        changed_fields.append({'field': 'date', 'value': new_date_dmy})
        
        await state.clear()
        await state.update_data(
            route_id=route_id,
            edit_message_id=edit_message_id,
            changed_fields=changed_fields
        )

        await show_edit_menu_after_update(call.message, route_id, state)
        await call.answer(f"✅ Дата: {new_date_dmy}")


@router.callback_query(F.data.startswith("myroutes:comment_"))
async def handle_comment_action(call: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает действия с комментарием"""
    action = call.data.split(":")[1].replace("comment_", "")
    route_id = int(call.data.split(":")[-1])

    route = database.get_route_by_id(route_id)
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    if action == "delete":
        database.update_route(route_id, comment="")
        
        data = await state.get_data()
        changed_fields = data.get('changed_fields', [])
        changed_fields.append({'field': 'comment', 'value': ''})

        await state.update_data(
            route_id=route_id,
            edit_message_id=call.message.message_id,
            changed_fields=changed_fields
        )

        await show_edit_menu_after_update(call.message, route_id, state)
        await call.answer("✅ Комментарий удален")

    else:
        # БАГ #10: Показываем старый комментарий
        current_comment = route.get("comment", "")
        
        await state.update_data(
            route_id=route_id,
            field_name="comment",
            comment_mode=action,
            edit_message_id=call.message.message_id,
            current_comment=current_comment
        )
        await state.set_state(EditRoute.waiting_for_value)

        if action == "replace":
            prompt = f"✏️ <b>ЗАМЕНИТЬ комментарий</b>\n\n<b>Текущий:</b>\n{current_comment}\n\nВведите новый комментарий:"
        else:  # append
            prompt = f"➕ <b>ДОПИСАТЬ к комментарию</b>\n\n<b>Текущий:</b>\n{current_comment}\n\nВведите текст для добавления:"

        await call.message.edit_text(
            prompt,
            reply_markup=_kb_back_and_cancel(route_id),
            parse_mode="HTML"
        )
        await call.answer()


@router.message(EditRoute.waiting_for_value)
async def process_new_value(message: Message, state: FSMContext) -> None:
    """Обрабатывает введенное новое значение"""
    data = await state.get_data()
    route_id = data.get("route_id")
    field_name = data.get("field_name")
    edit_message_id = data.get("edit_message_id")
    error_count = data.get("error_count", 0)
    changed_fields = data.get("changed_fields", [])
    new_value = message.text.strip()

    if not route_id or not field_name:
        await message.answer("❌ Ошибка: данные потеряны")
        await state.clear()
        return

    try:
        await message.delete()
    except:
        pass

    route = database.get_route_by_id(route_id)
    if not route:
        try:
            await message.bot.edit_message_text(
                "❌ Маршрут не найден",
                chat_id=message.chat.id,
                message_id=edit_message_id
            )
        except:
            await message.answer("❌ Маршрут не найден")
        await state.clear()
        return

    current_from = route.get('from_location', '?')
    current_to = route.get('to_location', '?')
    current_time = route.get('time_hm', '?')
    current_price = route.get('price', 0)
    current_seats = route.get('seats', 0)

    try:
        if field_name == "from_location":
            if len(new_value) < 2:
                error_count += 1
                await state.update_data(error_count=error_count)
                await message.bot.edit_message_text(
                    f"❌ Слишком короткое название (попытка {error_count})\n\n"
                    f"📍 <b>ОТКУДА</b>\n\nТекущее значение: {current_from}\n\nВведите новое значение:",
                    chat_id=message.chat.id,
                    message_id=edit_message_id,
                    reply_markup=_kb_back_and_cancel(route_id),
                    parse_mode="HTML"
                )
                return
            database.update_route(route_id, from_location=new_value)
            changed_fields.append({'field': 'from_location', 'value': new_value})

        elif field_name == "to_location":
            if len(new_value) < 2:
                error_count += 1
                await state.update_data(error_count=error_count)
                await message.bot.edit_message_text(
                    f"❌ Слишком короткое название (попытка {error_count})\n\n"
                    f"📍 <b>КУДА</b>\n\nТекущее значение: {current_to}\n\nВведите новое значение:",
                    chat_id=message.chat.id,
                    message_id=edit_message_id,
                    reply_markup=_kb_back_and_cancel(route_id),
                    parse_mode="HTML"
                )
                return
            database.update_route(route_id, to_location=new_value)
            changed_fields.append({'field': 'to_location', 'value': new_value})

        elif field_name == "time":
            try:
                parsed_time = _parse_time(new_value)
                time_obj = datetime.strptime(parsed_time, '%H:%M')
                new_time_hm = time_obj.strftime('%H:%M')
                database.update_route(route_id, time_hm=new_time_hm)
                changed_fields.append({'field': 'time', 'value': new_time_hm})
            except ValueError:
                error_count += 1
                await state.update_data(error_count=error_count)
                await message.bot.edit_message_text(
                    f"❌ Неверный формат (попытка {error_count})\n\n"
                    f"🕐 <b>ВРЕМЯ</b>\n\nТекущее значение: {current_time}\n\n"
                    f"Введите новое время:\nФормат: ЧЧ:ММ или ЧЧММ\nНапример: 14:30 или 1430",
                    chat_id=message.chat.id,
                    message_id=edit_message_id,
                    reply_markup=_kb_back_and_cancel(route_id),
                    parse_mode="HTML"
                )
                return

        elif field_name == "price":
            try:
                price_value = int(new_value)
                if price_value < 0:
                    error_count += 1
                    await state.update_data(error_count=error_count)
                    await message.bot.edit_message_text(
                        f"❌ Цена не может быть отрицательной (попытка {error_count})\n\n"
                        f"💰 <b>ЦЕНА</b>\n\nТекущее значение: {current_price}₽\n\n"
                        f"Введите новую цену:\nНапример: 500",
                        chat_id=message.chat.id,
                        message_id=edit_message_id,
                        reply_markup=_kb_back_and_cancel(route_id),
                        parse_mode="HTML"
                    )
                    return
                database.update_route(route_id, price=price_value)
                changed_fields.append({'field': 'price', 'value': price_value})
            except ValueError:
                error_count += 1
                await state.update_data(error_count=error_count)
                await message.bot.edit_message_text(
                    f"❌ Введите только число (попытка {error_count})\n\n"
                    f"💰 <b>ЦЕНА</b>\n\nТекущее значение: {current_price}₽\n\n"
                    f"Введите новую цену:\nНапример: 500",
                    chat_id=message.chat.id,
                    message_id=edit_message_id,
                    reply_markup=_kb_back_and_cancel(route_id),
                    parse_mode="HTML"
                )
                return

        elif field_name == "seats":
            try:
                seats_value = int(new_value)
                if seats_value < 1:
                    error_count += 1
                    await state.update_data(error_count=error_count)
                    await message.bot.edit_message_text(
                        f"❌ Минимум 1 место (попытка {error_count})\n\n"
                        f"👥 <b>КОЛИЧЕСТВО МЕСТ</b>\n\nТекущее значение: {current_seats}\n\n"
                        f"Введите новое количество мест:",
                        chat_id=message.chat.id,
                        message_id=edit_message_id,
                        reply_markup=_kb_back_and_cancel(route_id),
                        parse_mode="HTML"
                    )
                    return
                database.update_route(route_id, seats=seats_value)
                changed_fields.append({'field': 'seats', 'value': seats_value})
            except ValueError:
                error_count += 1
                await state.update_data(error_count=error_count)
                await message.bot.edit_message_text(
                    f"❌ Введите положительное число (попытка {error_count})\n\n"
                    f"👥 <b>КОЛИЧЕСТВО МЕСТ</b>\n\nТекущее значение: {current_seats}\n\n"
                    f"Введите новое количество мест:",
                    chat_id=message.chat.id,
                    message_id=edit_message_id,
                    reply_markup=_kb_back_and_cancel(route_id),
                    parse_mode="HTML"
                )
                return

        elif field_name == "comment":
            comment_mode = data.get("comment_mode", "replace")

            if comment_mode == "append":
                current_comment = route.get("comment", "")
                new_value = f"{current_comment}, {new_value}".strip()

            database.update_route(route_id, comment=new_value)
            changed_fields.append({'field': 'comment', 'value': new_value})

        else:
            await message.answer("❌ Неизвестное поле")
            await state.clear()
            return

        saved_message_id = edit_message_id
        await state.clear()
        await state.update_data(
            route_id=route_id,
            edit_message_id=saved_message_id,
            changed_fields=changed_fields
        )

        await show_edit_menu_after_update(message, route_id, state)

    except Exception as e:
        try:
            await message.bot.edit_message_text(
                f"❌ Ошибка: {e}",
                chat_id=message.chat.id,
                message_id=edit_message_id
            )
        except:
            await message.answer(f"❌ Ошибка: {e}")
        await state.clear()


async def show_edit_menu_after_update(message: Message, route_id: int, state: FSMContext) -> None:
    """Показывает меню редактирования после обновления"""
    route = database.get_route_by_id(route_id)
    if not route:
        return

    data = await state.get_data()
    edit_message_id = data.get("edit_message_id")
    changed_fields = data.get("changed_fields", [])

    await state.update_data(
        route_id=route_id,
        edit_message_id=edit_message_id,
        changed_fields=changed_fields
    )

    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "Нет")

    text = (
        f"✏️ <b>Изменение маршрута</b>\n\n"
        f"<b>Текущие данные:</b>\n"
        f"📍 Откуда: {from_location}\n"
        f"📍 Куда: {to_location}\n"
        f"📅 Дата: {date_dmy}\n"
        f"🕐 Время: {time_hm}\n"
        f"💰 Цена: {price}₽\n"
        f"👥 Мест: {seats}\n"
        f"💬 Комментарий: {comment}\n\n"
        f"Выберите что хотите изменить:"
    )

    try:
        await message.bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=edit_message_id,
            reply_markup=_kb_edit_menu(route_id),
            parse_mode="HTML"
        )
    except:
        pass


@router.callback_query(F.data.startswith("myroutes:edit_done:"))
async def finish_edit(call: CallbackQuery, state: FSMContext) -> None:
    """Завершает редактирование - возврат к карточке"""
    route_id = int(call.data.split(":")[-1])
    
    data = await state.get_data()
    changed_fields = data.get('changed_fields', [])
    
    await _notify_passengers_about_change(route_id, call.bot, changed_fields)
    
    await state.clear()

    route = database.get_route_by_id(route_id)

    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    driver_id = call.from_user.id
    is_active = route.get('is_active', 1)

    from handlers.my_routes.details_handler import _kb_route_actions

    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "")

    card = (
        f"• {date_dmy}г. {time_hm} — {from_location} → {to_location} | "
        f"цена: {price}₽ | мест: {seats}\n"
    )

    if comment:
        card += f"💬 {comment}\n"

    status = _get_route_status(route_id, driver_id)
    card += f"\n{status}"

    await call.message.edit_text(
        card,
        reply_markup=_kb_route_actions(route_id, is_active),
        parse_mode="HTML"
    )
    await call.answer("Изменения сохранены ✅")


@router.callback_query(F.data.startswith("myroutes:edit_cancel:"))
async def cancel_edit(call: CallbackQuery, state: FSMContext) -> None:
    """Отмена редактирования - возврат к карточке"""
    await state.clear()

    route_id = int(call.data.split(":")[-1])
    route = database.get_route_by_id(route_id)

    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    driver_id = call.from_user.id
    is_active = route.get('is_active', 1)

    from handlers.my_routes.details_handler import _kb_route_actions

    from_location = route.get("from_location", "?")
    to_location = route.get("to_location", "?")
    date_dmy = route.get("date_dmy", "?")
    time_hm = route.get("time_hm", "?")
    price = route.get("price", 0)
    seats = route.get("seats", 0)
    comment = route.get("comment", "")

    card = (
        f"• {date_dmy}г. {time_hm} — {from_location} → {to_location} | "
        f"цена: {price}₽ | мест: {seats}\n"
    )

    if comment:
        card += f"💬 {comment}\n"

    status = _get_route_status(route_id, driver_id)
    card += f"\n{status}"

    await call.message.edit_text(
        card,
        reply_markup=_kb_route_actions(route_id, is_active),
        parse_mode="HTML"
    )
    await call.answer("Отменено")