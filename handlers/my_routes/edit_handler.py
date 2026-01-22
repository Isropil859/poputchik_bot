# coding: utf-8
"""
Изменение маршрута водителем - пошаговый мастер
БАГ #13 ИСПРАВЛЕН: Добавлены задержки между уведомлениями
БАГ #18 ИСПРАВЛЕН: Изменения сохраняются ТОЛЬКО при нажатии "Готово"
БАГ #27 ИСПРАВЛЕН: Уведомления показывают "было → стало"
БАГ #27.1 ИСПРАВЛЕН: Убрано дублирование "Откуда/Куда" в заголовке
БАГ #22 ИСПРАВЛЕН: Всегда показывается полный маршрут + формат "с X на Y" + эмодзи
БАГ #17 ИСПРАВЛЕН: Валидация времени - поддержка 1-2 цифр
БАГ #19 ИСПРАВЛЕН: Кнопка "Назад" в комментариях возвращает в меню комментария
БАГ #24 ИСПРАВЛЕН: Проверка прошедшего времени при редактировании + проверка при сохранении
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, date, time
import calendar
import database
import logging
import asyncio

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
    БАГ #17 ИСПРАВЛЕН: Умный парсинг времени с поддержкой 1-2 цифр:
    1 → 01:00
    9 → 09:00
    15 → 15:00
    735 → 07:35
    0850 → 08:50
    14:30 → 14:30
    """
    time_str = time_str.strip().replace(":", "").replace(".", "").replace(" ", "")

    if time_str.isdigit():
        # БАГ #17: 1 цифра (0-9) → 0X:00
        if len(time_str) == 1:
            hours = time_str
            return f"0{hours}:00"
        # БАГ #17: 2 цифры (10-23) → XX:00
        elif len(time_str) == 2:
            hours = time_str
            return f"{hours}:00"
        # 3 цифры: 735 → 07:35
        elif len(time_str) == 3:
            hours = time_str[0]
            minutes = time_str[1:3]
            return f"0{hours}:{minutes}"
        # 4 цифры: 0850 → 08:50
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
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"editcal:back:{route_id}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"myroutes:edit_cancel:{route_id}")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def _notify_passengers_about_change(route_id: int, bot, changed_fields: list, original_route: dict):
    """
    БАГ #6 + БАГ #13 + БАГ #27 + БАГ #27.1 + БАГ #22 ИСПРАВЛЕН
    Уведомляет пассажиров с принятыми заявками об изменении маршрута
    
    НОВАЯ ЛОГИКА БАГ #22:
    - ВСЕГДА показывает полный старый маршрут
    - Формат для маршрута: "📍 Маршрут: A → B" и "📍 На: C → D"
    - Формат для других полей: "с X на Y" с эмодзи
    """
    requests = database.get_route_requests(route_id)
    accepted_requests = [r for r in requests if r.get('status') == 'accepted']
    
    if not accepted_requests:
        logging.info(f"БАГ #13: Нет принятых заявок для маршрута {route_id}")
        return
    
    if not changed_fields:
        logging.info(f"БАГ #13: Нет изменений для уведомления по маршруту {route_id}")
        return
    
    route = database.get_route_by_id(route_id)
    if not route:
        return
    
    # БАГ #22: Проверяем изменился ли маршрут (Откуда и/или Куда)
    from_changed = any(c['field'] == 'from_location' for c in changed_fields)
    to_changed = any(c['field'] == 'to_location' for c in changed_fields)
    route_changed = from_changed or to_changed
    
    # БАГ #22: Если маршрут НЕ изменился - добавляем его в заголовок
    if not route_changed:
        from_loc = route['from_location']
        to_loc = route['to_location']
        notification_text = f"⚠️ <b>МАРШРУТ {from_loc} → {to_loc} ИЗМЕНЁН!</b>\n\n"
    else:
        notification_text = "⚠️ <b>МАРШРУТ ИЗМЕНЁН!</b>\n\n"
    
    notification_text += "Водитель изменил:\n"
    
    # БАГ #22: Если маршрут изменился - показываем старый и новый ПОЛНОСТЬЮ с эмодзи
    if route_changed:
        old_from = original_route.get('from_location', '?')
        old_to = original_route.get('to_location', '?')
        new_from = route['from_location']
        new_to = route['to_location']
        
        notification_text += f"📍 Маршрут: {old_from} → {old_to}\n"
        notification_text += f"📍 На: {new_from} → {new_to}\n"
    
    # БАГ #22: Остальные изменения показываем в формате "с X на Y" с эмодзи
    for change in changed_fields:
        field = change['field']
        new_value = change['value']
        
        # Пропускаем маршрут - он уже показан выше
        if field in ['from_location', 'to_location']:
            continue
        
        if field == 'date':
            old_value = original_route.get('date_dmy', '?')
            notification_text += f"📅 Дату: с {old_value} на {new_value}\n"
        elif field == 'time':
            old_value = original_route.get('time_hm', '?')
            notification_text += f"🕐 Время: с {old_value} на {new_value}\n"
        elif field == 'price':
            old_value = original_route.get('price', 0)
            notification_text += f"💰 Цену: со {old_value}₽ на {new_value}₽\n"
        elif field == 'seats':
            old_value = original_route.get('seats', 0)
            notification_text += f"👥 Количество мест: с {old_value} на {new_value}\n"
        elif field == 'comment':
            old_value = original_route.get('comment', '')
            if new_value and old_value:
                notification_text += f"💬 Комментарий: с {old_value} на {new_value}\n"
            elif new_value:
                notification_text += f"💬 Комментарий добавлен: {new_value}\n"
            else:
                notification_text += f"💬 Комментарий удалён\n"
    
    notification_text += "\n📱 Проверьте детали в \"Мои поездки\""
    
    # БАГ #13: Счётчики для логирования
    sent_count = 0
    failed_count = 0
    total_passengers = len(accepted_requests)
    
    logging.info(f"БАГ #13: Начало отправки уведомлений {total_passengers} пассажирам по маршруту {route_id}")
    
    for req in accepted_requests:
        passenger_id = req.get('passenger_id')
        try:
            await bot.send_message(
                passenger_id, 
                notification_text,
                parse_mode="HTML",
                disable_notification=False
            )
            sent_count += 1
            logging.info(f"✅ БАГ #13: Уведомление отправлено пассажиру {passenger_id} ({sent_count}/{total_passengers})")
            
            # БАГ #13 ИСПРАВЛЕН: Добавляем задержку между отправками (0.3 секунды)
            await asyncio.sleep(0.3)
            
        except Exception as e:
            failed_count += 1
            logging.error(f"❌ БАГ #13: Не удалось уведомить пассажира {passenger_id}: {e}")
    
    # Итоговое логирование
    logging.info(f"БАГ #13: Завершено. Отправлено: {sent_count}, Ошибок: {failed_count}, Всего: {total_passengers}")

def _get_pending_value(changed_fields: list, field_name: str, original_value):
    """
    БАГ #18: Получить значение из списка изменений или оригинальное значение
    """
    for change in changed_fields:
        if change['field'] == field_name:
            return change['value']
    return original_value

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

    # БАГ #18 + БАГ #24: Инициализируем changed_fields и сохраняем дату маршрута в ISO формате
    selected_date_iso = None
    try:
        # Парсим дату маршрута из формата "DD.MM.YYYY"
        date_dmy = route.get("date_dmy", "")
        if date_dmy:
            day, month, year = date_dmy.split('.')
            route_date = date(int(year), int(month), int(day))
            selected_date_iso = route_date.isoformat()
    except:
        pass
    
    await state.update_data(
        route_id=route_id,
        edit_message_id=call.message.message_id,
        changed_fields=[],
        original_route=dict(route),
        selected_date_iso=selected_date_iso  # БАГ #24: Сохраняем дату для проверки времени
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

    data = await state.get_data()
    original_route = data.get('original_route', {})
    
    # БАГ #18: Используем оригинальные данные
    route = original_route if original_route else database.get_route_by_id(route_id)
    
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
    """БАГ #18 + БАГ #19 ИСПРАВЛЕН: Возврат в меню редактирования или меню комментария"""
    route_id = int(call.data.split(":")[-1])
    
    data = await state.get_data()
    changed_fields = data.get('changed_fields', [])
    original_route = data.get('original_route', {})
    edit_message_id = call.message.message_id
    field_name = data.get('field_name')
    selected_date_iso = data.get('selected_date_iso')  # БАГ #24
    
    # БАГ #19 ИСПРАВЛЕН: Если мы в режиме редактирования комментария - возвращаемся в меню комментария
    if field_name == 'comment':
        route = original_route if original_route else database.get_route_by_id(route_id)
        
        if not route:
            await call.answer("❌ Маршрут не найден", show_alert=True)
            return
        
        # БАГ #19: Показываем меню комментария с текущим значением
        current_comment = _get_pending_value(changed_fields, 'comment', route.get("comment", ""))
        
        if current_comment:
            text = (
                f"💬 <b>Текущий комментарий:</b>\n"
                f"{current_comment}\n\n"
                f"Что хотите сделать?"
            )
        else:
            text = "💬 <b>Комментарий отсутствует</b>\n\nЧто хотите сделать?"
        
        # Очищаем состояние ввода но сохраняем changed_fields
        await state.clear()
        await state.update_data(
            route_id=route_id,
            edit_message_id=edit_message_id,
            changed_fields=changed_fields,
            original_route=original_route,
            selected_date_iso=selected_date_iso  # БАГ #24: Сохраняем дату
        )
        
        await call.message.edit_text(
            text,
            reply_markup=_kb_comment_action(route_id),
            parse_mode="HTML"
        )
        await call.answer()
        return
    
    # Иначе возвращаемся в главное меню редактирования
    # БАГ #18: Сохраняем changed_fields при возврате
    await state.clear()
    await state.update_data(
        route_id=route_id,
        edit_message_id=edit_message_id,
        changed_fields=changed_fields,
        original_route=original_route,
        selected_date_iso=selected_date_iso  # БАГ #24: Сохраняем дату
    )
    
    # БАГ #18: Используем оригинальные данные + изменения
    route = original_route if original_route else database.get_route_by_id(route_id)
    
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    driver_id = call.from_user.id
    if route.get("user_id") != driver_id:
        await call.answer("❌ Это не ваш маршрут", show_alert=True)
        return

    # БАГ #18: Показываем ВРЕМЕННЫЕ значения из changed_fields
    from_location = _get_pending_value(changed_fields, 'from_location', route.get("from_location", "?"))
    to_location = _get_pending_value(changed_fields, 'to_location', route.get("to_location", "?"))
    date_dmy = _get_pending_value(changed_fields, 'date', route.get("date_dmy", "?"))
    time_hm = _get_pending_value(changed_fields, 'time', route.get("time_hm", "?"))
    price = _get_pending_value(changed_fields, 'price', route.get("price", 0))
    seats = _get_pending_value(changed_fields, 'seats', route.get("seats", 0))
    comment = _get_pending_value(changed_fields, 'comment', route.get("comment", "Нет"))
    if comment == "":
        comment = "Нет"

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
        new_date_dmy = selected_date.strftime('%d.%m.%Y')
        
        # БАГ #18 + БАГ #24: НЕ сохраняем в БД, только в changed_fields + обновляем selected_date_iso
        data = await state.get_data()
        changed_fields = data.get('changed_fields', [])
        original_route = data.get('original_route', {})
        
        # Удаляем старое значение даты если есть
        changed_fields = [c for c in changed_fields if c['field'] != 'date']
        changed_fields.append({'field': 'date', 'value': new_date_dmy})
        
        await state.update_data(
            route_id=route_id,
            edit_message_id=edit_message_id,
            changed_fields=changed_fields,
            original_route=original_route,
            selected_date_iso=selected_date.isoformat()  # БАГ #24: Обновляем дату
        )

        await show_edit_menu_after_update(call.message, route_id, state)
        await call.answer(f"✅ Дата: {new_date_dmy}")


@router.callback_query(F.data.startswith("myroutes:comment_"))
async def handle_comment_action(call: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает действия с комментарием"""
    action = call.data.split(":")[1].replace("comment_", "")
    route_id = int(call.data.split(":")[-1])

    data = await state.get_data()
    original_route = data.get('original_route', {})
    route = original_route if original_route else database.get_route_by_id(route_id)
    
    if not route:
        await call.answer("❌ Маршрут не найден", show_alert=True)
        return

    if action == "delete":
        # БАГ #18 ИСПРАВЛЕН: НЕ сохраняем в БД, только в changed_fields
        changed_fields = data.get('changed_fields', [])
        
        # Удаляем старое значение комментария если есть
        changed_fields = [c for c in changed_fields if c['field'] != 'comment']
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
    """БАГ #18 + БАГ #24 ИСПРАВЛЕН: Обрабатывает введенное новое значение БЕЗ сохранения в БД + проверка прошедшего времени"""
    data = await state.get_data()
    route_id = data.get("route_id")
    field_name = data.get("field_name")
    edit_message_id = data.get("edit_message_id")
    error_count = data.get("error_count", 0)
    changed_fields = data.get("changed_fields", [])
    original_route = data.get("original_route", {})
    selected_date_iso = data.get("selected_date_iso")  # БАГ #24
    new_value = message.text.strip()

    if not route_id or not field_name:
        await message.answer("❌ Ошибка: данные потеряны")
        await state.clear()
        return

    try:
        await message.delete()
    except:
        pass

    route = original_route if original_route else database.get_route_by_id(route_id)
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
            # БАГ #18 ИСПРАВЛЕН: НЕ сохраняем в БД!
            changed_fields = [c for c in changed_fields if c['field'] != 'from_location']
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
            # БАГ #18 ИСПРАВЛЕН: НЕ сохраняем в БД!
            changed_fields = [c for c in changed_fields if c['field'] != 'to_location']
            changed_fields.append({'field': 'to_location', 'value': new_value})

        elif field_name == "time":
            try:
                parsed_time = _parse_time(new_value)
                time_obj = datetime.strptime(parsed_time, '%H:%M')
                new_time_hm = time_obj.strftime('%H:%M')
                
                # БАГ #24 ИСПРАВЛЕН: Проверка прошедшего времени
                if selected_date_iso:
                    route_date = date.fromisoformat(selected_date_iso)
                    today = date.today()
                    
                    # Если дата сегодня - проверяем что время не прошло
                    if route_date == today:
                        current_time_obj = datetime.now().time()
                        current_time_str = datetime.now().strftime('%H:%M')
                        
                        # Преобразуем введенное время в объект time для корректного сравнения
                        hours, minutes = new_time_hm.split(':')
                        parsed_time_obj = time(int(hours), int(minutes))
                        
                        if parsed_time_obj < current_time_obj:
                            error_count += 1
                            await state.update_data(error_count=error_count)
                            await message.bot.edit_message_text(
                                f"❌ Нельзя указать прошедшее время! (попытка {error_count})\n\n"
                                f"🕐 <b>ВРЕМЯ</b>\n\nТекущее значение: {current_time}\n\n"
                                f"Сейчас: {current_time_str}\n"
                                f"Введите время не раньше текущего.\n\n"
                                f"Примеры: {current_time_str}, 14:30, 1430",
                                chat_id=message.chat.id,
                                message_id=edit_message_id,
                                reply_markup=_kb_back_and_cancel(route_id),
                                parse_mode="HTML"
                            )
                            return
                
                # БАГ #18 ИСПРАВЛЕН: НЕ сохраняем в БД!
                changed_fields = [c for c in changed_fields if c['field'] != 'time']
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
                # БАГ #18 ИСПРАВЛЕН: НЕ сохраняем в БД!
                changed_fields = [c for c in changed_fields if c['field'] != 'price']
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
                # БАГ #18 ИСПРАВЛЕН: НЕ сохраняем в БД!
                changed_fields = [c for c in changed_fields if c['field'] != 'seats']
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

            # БАГ #18 ИСПРАВЛЕН: НЕ сохраняем в БД!
            changed_fields = [c for c in changed_fields if c['field'] != 'comment']
            changed_fields.append({'field': 'comment', 'value': new_value})

        else:
            await message.answer("❌ Неизвестное поле")
            await state.clear()
            return

        # БАГ #18: Сохраняем changed_fields в state
        await state.update_data(
            route_id=route_id,
            edit_message_id=edit_message_id,
            changed_fields=changed_fields,
            original_route=original_route,
            selected_date_iso=selected_date_iso  # БАГ #24: Сохраняем дату
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
    """БАГ #18: Показывает меню редактирования с ВРЕМЕННЫМИ значениями"""
    data = await state.get_data()
    edit_message_id = data.get("edit_message_id")
    changed_fields = data.get("changed_fields", [])
    original_route = data.get("original_route", {})
    
    route = original_route if original_route else database.get_route_by_id(route_id)
    if not route:
        return

    # БАГ #18: Показываем ВРЕМЕННЫЕ значения из changed_fields
    from_location = _get_pending_value(changed_fields, 'from_location', route.get("from_location", "?"))
    to_location = _get_pending_value(changed_fields, 'to_location', route.get("to_location", "?"))
    date_dmy = _get_pending_value(changed_fields, 'date', route.get("date_dmy", "?"))
    time_hm = _get_pending_value(changed_fields, 'time', route.get("time_hm", "?"))
    price = _get_pending_value(changed_fields, 'price', route.get("price", 0))
    seats = _get_pending_value(changed_fields, 'seats', route.get("seats", 0))
    comment = _get_pending_value(changed_fields, 'comment', route.get("comment", "Нет"))
    if comment == "":
        comment = "Нет"

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
    """БАГ #18 + БАГ #24 + БАГ #27 ИСПРАВЛЕН: Завершает редактирование - ПРИМЕНЯЕТ ВСЕ ИЗМЕНЕНИЯ + проверка прошедшего времени"""
    route_id = int(call.data.split(":")[-1])
    
    data = await state.get_data()
    changed_fields = data.get('changed_fields', [])
    original_route = data.get('original_route', {})
    selected_date_iso = data.get('selected_date_iso')
    
    # БАГ #24 ИСПРАВЛЕН: ПЕРЕД сохранением проверяем что время не прошедшее
    if selected_date_iso:
        # Получаем финальные значения времени и даты
        final_time = None
        final_date_iso = selected_date_iso
        
        for change in changed_fields:
            if change['field'] == 'time':
                final_time = change['value']
            elif change['field'] == 'date':
                # Парсим новую дату
                try:
                    day, month, year = change['value'].split('.')
                    new_date = date(int(year), int(month), int(day))
                    final_date_iso = new_date.isoformat()
                except:
                    pass
        
        # Если время НЕ изменилось - берем старое время
        if not final_time:
            final_time = original_route.get('time_hm')
        
        # Проверяем: если дата = сегодня И время прошло -> ОШИБКА
        if final_time and final_date_iso:
            try:
                route_date = date.fromisoformat(final_date_iso)
                today = date.today()
                
                if route_date == today:
                    current_time_obj = datetime.now().time()
                    current_time_str = datetime.now().strftime('%H:%M')
                    
                    hours, minutes = final_time.split(':')
                    parsed_time_obj = time(int(hours), int(minutes))
                    
                    if parsed_time_obj < current_time_obj:
                        # БАГ #24: БЛОКИРУЕМ сохранение с прошедшим временем!
                        await call.answer(
                            f"❌ Нельзя сохранить прошедшее время!\n\n"
                            f"Дата: сегодня ({route_date.strftime('%d.%m.%Y')})\n"
                            f"Время: {final_time}\n"
                            f"Сейчас: {current_time_str}\n\n"
                            f"Измените время на текущее или будущее.",
                            show_alert=True
                        )
                        return
            except Exception as e:
                logging.error(f"БАГ #24: Ошибка проверки времени: {e}")
    
    # БАГ #18 ИСПРАВЛЕН: Применяем ВСЕ изменения ОДНИМ РАЗОМ при нажатии "Готово"
    if changed_fields:
        updates = {}
        for change in changed_fields:
            field = change['field']
            value = change['value']
            
            if field == 'from_location':
                updates['from_location'] = value
            elif field == 'to_location':
                updates['to_location'] = value
            elif field == 'date':
                updates['date_dmy'] = value
            elif field == 'time':
                updates['time_hm'] = value
            elif field == 'price':
                updates['price'] = value
            elif field == 'seats':
                updates['seats'] = value
            elif field == 'comment':
                updates['comment'] = value
        
        # ОДИН РАЗ сохраняем ВСЕ изменения
        if updates:
            database.update_route(route_id, **updates)
            logging.info(f"БАГ #18: Маршрут {route_id} обновлён: {updates}")
    
    # БАГ #27: Отправляем уведомления ПОСЛЕ сохранения с передачей original_route
    await _notify_passengers_about_change(route_id, call.bot, changed_fields, original_route)
    
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
    """БАГ #18 ИСПРАВЛЕН: Отмена редактирования - БЕЗ сохранения изменений"""
    route_id = int(call.data.split(":")[-1])
    
    # БАГ #18: Очищаем state - изменения НЕ сохранятся!
    await state.clear()
    
    logging.info(f"БАГ #18: Отмена редактирования маршрута {route_id} - изменения НЕ сохранены")

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