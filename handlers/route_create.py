from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database
from datetime import datetime, date, time
import calendar

router = Router()

class RouteCreate(StatesGroup):
    waiting_for_from = State()
    waiting_for_to = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_price = State()
    waiting_for_seats = State()
    waiting_for_comment = State()
    confirm = State()

def get_main_menu_keyboard():
    """Главное меню с inline кнопками"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Найти маршрут", callback_data="search_route"),
            InlineKeyboardButton(text="🚗 Создать маршрут", callback_data="create_route")
        ],
        [
            InlineKeyboardButton(text="🧳 Мои поездки", callback_data="my_trips"),
            InlineKeyboardButton(text="🗺 Мои маршруты", callback_data="my_routes")
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ]
    ])
    return keyboard

def get_navigation_kb(show_publish=False):
    """Кнопки навигации"""
    buttons = []
    if show_publish:
        buttons.append([
            InlineKeyboardButton(text="🔙 Назад     ", callback_data="route_back"),
            InlineKeyboardButton(text="✅ Опубликовать     ", callback_data="route_publish_now"),
            InlineKeyboardButton(text="❌ Отмена     ", callback_data="route_cancel")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🔙 Назад          ", callback_data="route_back"),
            InlineKeyboardButton(text="❌ Отмена          ", callback_data="route_cancel")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_summary(data):
    """БАГ #9: Форматирование сводки С КОММЕНТАРИЕМ"""
    summary = "\n\n📊 <b>Сводка:</b>"
    
    if data.get('from_location'):
        summary += f"\nОткуда: {data['from_location']}"
    if data.get('to_location'):
        summary += f"\nКуда: {data['to_location']}"
    if data.get('date_dmy'):
        summary += f"\nДата: {data['date_dmy']}"
    if data.get('time_hm'):
        summary += f"\nВремя: {data['time_hm']}"
    if data.get('price'):
        summary += f"\nЦена: {data['price']}₽"
    if data.get('seats'):
        summary += f"\nМест: {data['seats']}"
    
    # БАГ #9: ДОБАВЛЕН комментарий в сводку
    if data.get('comment'):
        summary += f"\n💬 Комментарий: {data['comment']}"
    
    return summary

def get_calendar_kb(year, month, current_date):
    """Генерация календаря с правильным количеством недель"""
    keyboard = []
    
    month_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    
    keyboard.append([
        InlineKeyboardButton(text="◀️", callback_data=f"month_prev_{year}_{month}"),
        InlineKeyboardButton(text=f"{month_names[month-1]} {year}", callback_data="ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"month_next_{year}_{month}")
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="Пн", callback_data="ignore"),
        InlineKeyboardButton(text="Вт", callback_data="ignore"),
        InlineKeyboardButton(text="Ср", callback_data="ignore"),
        InlineKeyboardButton(text="Чт", callback_data="ignore"),
        InlineKeyboardButton(text="Пт", callback_data="ignore"),
        InlineKeyboardButton(text="Сб", callback_data="ignore"),
        InlineKeyboardButton(text="Вс", callback_data="ignore"),
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
                    week.append(InlineKeyboardButton(text=f"·{day}", callback_data="ignore"))
                else:
                    week.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{prev_year}_{prev_month}_{day}"
                    ))
            except:
                week.append(InlineKeyboardButton(text=str(day), callback_data="ignore"))
        elif day_counter < days_in_current:
            day_counter += 1
            day = day_counter
            try:
                day_date = datetime(year, month, day)
                if day_date.date() < current_date.date():
                    week.append(InlineKeyboardButton(text=f"·{day}", callback_data="ignore"))
                else:
                    week.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{year}_{month}_{day}"
                    ))
            except:
                week.append(InlineKeyboardButton(text=str(day), callback_data="ignore"))
        else:
            day = next_month_day
            next_month_day += 1
            try:
                day_date = datetime(next_year, next_month, day)
                if day_date.date() < current_date.date():
                    week.append(InlineKeyboardButton(text=f"·{day}", callback_data="ignore"))
                else:
                    week.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{next_year}_{next_month}_{day}"
                    ))
            except:
                week.append(InlineKeyboardButton(text=str(day), callback_data="ignore"))
        
        if len(week) == 7:
            keyboard.append(week)
            week = []
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="route_back"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="route_cancel")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def parse_time(time_str):
    """Парсинг времени с валидацией"""
    time_str = time_str.strip().replace(" ", "")
    
    if ":" in time_str:
        formatted_time = time_str
    else:
        digits = ''.join(c for c in time_str if c.isdigit())
        
        if len(digits) == 3:
            formatted_time = f"0{digits[0]}:{digits[1:3]}"
        elif len(digits) == 4:
            formatted_time = f"{digits[0:2]}:{digits[2:4]}"
        elif len(digits) == 2:
            formatted_time = f"{digits}:00"
        elif len(digits) == 1:
            formatted_time = f"0{digits}:00"
        else:
            return None
    
    # Валидация времени
    if not validate_time(formatted_time):
        return None
    
    return formatted_time

def validate_time(time_str):
    """Валидация корректности времени (часы 0-23, минуты 0-59)"""
    try:
        hours, minutes = time_str.split(":")
        hours = int(hours)
        minutes = int(minutes)
        
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return True
        return False
    except:
        return False

def pad_text(text):
    """Фиксация ТОЛЬКО ширины окна (без изменения высоты)"""
    width_padding = "⠀" * 30
    return text + f"\n{width_padding}"

@router.callback_query(F.data.startswith("create_route"))
async def start_create_route(callback: CallbackQuery, state: FSMContext):
    """Начало создания маршрута - ПРОВЕРКА ПРОФИЛЯ"""
    await state.clear()
    
    # ПРОВЕРКА: Есть ли у водителя профиль?
    user_id = callback.from_user.id
    profile = database.get_user_profile(user_id)
    
    # Если профиль не зарегистрирован (нет display_name) - БЛОКИРУЕМ
    if not profile or not profile.get('display_name'):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Создать профиль", callback_data="profile")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(
            "⚠️ <b>ПРОФИЛЬ НЕ ЗАПОЛНЕН</b>\n\n"
            "Для создания маршрутов нужно заполнить профиль водителя!\n\n"
            "Пассажирам важно знать с кем они едут. "
            "Пожалуйста, добавьте имя и описание в профиле.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        await callback.answer()
        return
    
    # Профиль заполнен - разрешаем создавать маршрут
    # Определяем откуда пришли
    came_from = "main_menu"
    if "from_my_routes" in callback.data:
        came_from = "my_routes"
    
    text = pad_text("📍 <b>Откуда?</b>")
    
    msg = await callback.message.edit_text(
        text,
        reply_markup=get_navigation_kb(),
        parse_mode='HTML'
    )
    
    await state.update_data(bot_message_id=msg.message_id, came_from=came_from)
    await state.set_state(RouteCreate.waiting_for_from)
    await callback.answer()

@router.message(RouteCreate.waiting_for_from)
async def process_from(message: Message, state: FSMContext):
    """Обработка откуда"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    try:
        await message.delete()
    except:
        pass
    
    await state.update_data(from_location=message.text)
    data = await state.get_data()
    
    text = pad_text(f"📍 <b>Куда?</b>{format_summary(data)}")
    
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=bot_msg_id,
        text=text,
        reply_markup=get_navigation_kb(),
        parse_mode='HTML'
    )
    
    await state.set_state(RouteCreate.waiting_for_to)

@router.message(RouteCreate.waiting_for_to)
async def process_to(message: Message, state: FSMContext):
    """Обработка куда"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    try:
        await message.delete()
    except:
        pass
    
    await state.update_data(to_location=message.text)
    data = await state.get_data()
    
    now = datetime.now()
    text = pad_text(f"📅 <b>ДАТА поездки?</b>{format_summary(data)}")
    
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=bot_msg_id,
        text=text,
        reply_markup=get_calendar_kb(now.year, now.month, now),
        parse_mode='HTML'
    )
    
    await state.set_state(RouteCreate.waiting_for_date)

@router.callback_query(F.data.startswith("month_"))
async def navigate_month(callback: CallbackQuery, state: FSMContext):
    """Навигация по месяцам"""
    data = await state.get_data()
    _, direction, year, month = callback.data.split("_")
    year, month = int(year), int(month)
    
    if direction == "prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    else:
        month += 1
        if month > 12:
            month = 1
            year += 1
    
    now = datetime.now()
    text = pad_text(f"📅 <b>ДАТА поездки?</b>{format_summary(data)}")
    
    await callback.message.edit_text(
        text,
        reply_markup=get_calendar_kb(year, month, now),
        parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("date_"))
async def process_date(callback: CallbackQuery, state: FSMContext):
    """Выбор даты"""
    _, year, month, day = callback.data.split("_")
    date_str = f"{day.zfill(2)}.{month.zfill(2)}.{year}"
    
    # БАГ #24: Сохраняем дату в формате ISO для проверки времени
    selected_date = datetime(int(year), int(month), int(day)).date()
    
    await state.update_data(date_dmy=date_str, selected_date_iso=selected_date.isoformat())
    data = await state.get_data()
    
    text = pad_text(f"🕐 <b>ВРЕМЯ отправления?</b>\n\nФормат: 14:30 или 1430{format_summary(data)}")
    
    await callback.message.edit_text(
        text,
        reply_markup=get_navigation_kb(),
        parse_mode='HTML'
    )
    await state.set_state(RouteCreate.waiting_for_time)
    await callback.answer()

@router.message(RouteCreate.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    """БАГ #24 ИСПРАВЛЕН: Обработка времени с проверкой прошедшего времени"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    try:
        await message.delete()
    except:
        pass
    
    parsed_time = parse_time(message.text)
    
    if not parsed_time:
        text = pad_text(
            f"🕐 <b>ВРЕМЯ отправления?</b>\n\n"
            f"❌ Неверный формат времени!\n\n"
            f"Введите корректное время:\n"
            f"• Часы: 0-23\n"
            f"• Минуты: 0-59\n\n"
            f"Примеры: 14:30, 1430, 9:15{format_summary(data)}"
        )
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )
        return
    
    # БАГ #24 ИСПРАВЛЕН: Проверка прошедшего времени
    selected_date_iso = data.get('selected_date_iso')
    
    if selected_date_iso:
        selected_date = date.fromisoformat(selected_date_iso)
        today = date.today()
        
        # Если дата сегодня - проверяем что время не прошло
        if selected_date == today:
            current_time_obj = datetime.now().time()
            current_time_str = datetime.now().strftime('%H:%M')
            
            # Преобразуем введенное время в объект time для корректного сравнения
            hours, minutes = parsed_time.split(':')
            parsed_time_obj = time(int(hours), int(minutes))
            
            if parsed_time_obj < current_time_obj:
                text = pad_text(
                    f"🕐 <b>ВРЕМЯ отправления?</b>\n\n"
                    f"❌ Нельзя указать прошедшее время!\n\n"
                    f"Сейчас: {current_time_str}\n"
                    f"Введите время не раньше текущего.\n\n"
                    f"Примеры: {current_time_str}, 14:30, 1430{format_summary(data)}"
                )
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=bot_msg_id,
                    text=text,
                    reply_markup=get_navigation_kb(),
                    parse_mode='HTML'
                )
                return
    
    await state.update_data(time_hm=parsed_time)
    data = await state.get_data()
    
    text = pad_text(
        f"💰 <b>ЦЕНА с пассажира?</b>\n\n"
        f"Ориентировочный расчёт:\n"
        f"- 20 км ≈ 50-100₽ с пассажира\n"
        f"- 40 км ≈ 100-150₽ с пассажира\n"
        f"- 60 км ≈ 150-250₽ с пассажира\n\n"
        f"<b>⚠️ Важно: Цена должна ТОЛЬКО покрывать расходы на дорогу, это НЕ коммерческая перевозка!</b>"
        f"{format_summary(data)}"
    )
    
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=bot_msg_id,
        text=text,
        reply_markup=get_navigation_kb(),
        parse_mode='HTML'
    )
    await state.set_state(RouteCreate.waiting_for_price)

@router.message(RouteCreate.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    """Обработка цены"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    try:
        await message.delete()
    except:
        pass
    
    try:
        price = int(message.text)
        await state.update_data(price=price)
        data = await state.get_data()
        
        text = pad_text(f"👥 <b>Сколько МЕСТ?</b>{format_summary(data)}")
        
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_seats)
    except ValueError:
        text = pad_text(f"💰 <b>ЦЕНА с пассажира?</b>\n\n❌ Введите число! Например: 150{format_summary(data)}")
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )

@router.message(RouteCreate.waiting_for_seats)
async def process_seats(message: Message, state: FSMContext):
    """Обработка мест"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    try:
        await message.delete()
    except:
        pass
    
    try:
        seats = int(message.text)
        await state.update_data(seats=seats)
        data = await state.get_data()
        
        text = pad_text(f"💬 <b>КОММЕНТАРИЙ?</b>\n\n(необязательно){format_summary(data)}")
        
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=get_navigation_kb(show_publish=True),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_comment)
    except ValueError:
        text = pad_text(f"👥 <b>Сколько МЕСТ?</b>\n\n❌ Введите число! Например: 3{format_summary(data)}")
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )

@router.message(RouteCreate.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    """БАГ #9: Обработка комментария - ПОКАЗЫВАЕТСЯ СРАЗУ В СВОДКЕ"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    try:
        await message.delete()
    except:
        pass
    
    user_input = message.text.strip()
    
    if user_input.lower() in ["нет", "пропустить", "-"]:
        final_comment = ""
    else:
        final_comment = user_input
    
    await state.update_data(comment=final_comment)
    data = await state.get_data()
    
    # БАГ #9: Формируем текст подтверждения
    text = (
        f"✅ <b>ПОДТВЕРЖДЕНИЕ</b>\n\n"
        f"📍 Маршрут: {data['from_location']} → {data['to_location']}\n"
        f"📅 Дата: {data['date_dmy']}\n"
        f"🕐 Время: {data['time_hm']}\n"
        f"💰 Цена: {data['price']}₽\n"
        f"👥 Мест: {data['seats']}\n"
    )
    
    saved_comment = data.get('comment', '')
    
    if saved_comment:
        text += f"💬 Комментарий: {saved_comment}\n"
    
    text = pad_text(text)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 Назад     ", callback_data="route_back"),
            InlineKeyboardButton(text="✅ Опубликовать     ", callback_data="route_publish"),
            InlineKeyboardButton(text="❌ Отмена     ", callback_data="route_cancel")
        ]
    ])
    
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=bot_msg_id,
        text=text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(RouteCreate.confirm)

@router.callback_query(F.data == "route_publish_now")
async def publish_without_comment(callback: CallbackQuery, state: FSMContext):
    """БАГ #11 ИСПРАВЛЕН: Опубликовать без комментария"""
    data = await state.get_data()
    came_from = data.get('came_from', 'main_menu')
    
    await state.update_data(comment="")
    data = await state.get_data()
    
    route_id = database.create_route(
        user_id=callback.from_user.id,
        from_loc=data['from_location'],
        to_loc=data['to_location'],
        date_dmy=data['date_dmy'],
        time_hm=data['time_hm'],
        price=data['price'],
        seats=data['seats'],
        comment=""
    )
    
    await state.clear()
    
    if came_from == "my_routes":
        # БАГ #11 ИСПРАВЛЕН: Показываем сообщение вместо автоматического вызова списка
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Мои маршруты", callback_data="my_routes")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await callback.message.edit_text(
            "✅ <b>Маршрут опубликован!</b>\n\n"
            "Нажмите 'Мои маршруты' для просмотра.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        await callback.answer("Маршрут создан!")
    else:
        await callback.message.edit_text(
            "✅ Маршрут опубликован!\n\n"
            "<b>👋 Главное меню                              </b>\n\n"
            "Выберите действие:                              ",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        await callback.answer("Маршрут создан!")

@router.callback_query(F.data == "route_publish")
async def publish_route(callback: CallbackQuery, state: FSMContext):
    """БАГ #11 ИСПРАВЛЕН: Публикация маршрута"""
    data = await state.get_data()
    came_from = data.get('came_from', 'main_menu')
    
    route_id = database.create_route(
        user_id=callback.from_user.id,
        from_loc=data['from_location'],
        to_loc=data['to_location'],
        date_dmy=data['date_dmy'],
        time_hm=data['time_hm'],
        price=data['price'],
        seats=data['seats'],
        comment=data.get('comment', '')
    )
    
    await state.clear()
    
    if came_from == "my_routes":
        # БАГ #11 ИСПРАВЛЕН: Показываем сообщение вместо автоматического вызова списка
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Мои маршруты", callback_data="my_routes")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await callback.message.edit_text(
            "✅ <b>Маршрут опубликован!</b>\n\n"
            "Нажмите 'Мои маршруты' для просмотра.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        await callback.answer("Маршрут создан!")
    else:
        await callback.message.edit_text(
            "✅ Маршрут опубликован!\n\n"
            "<b>👋 Главное меню                              </b>\n\n"
            "Выберите действие:                              ",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        await callback.answer("Маршрут создан!")

@router.callback_query(F.data == "route_cancel")
async def cancel_route(callback: CallbackQuery, state: FSMContext):
    """БАГ #11 ИСПРАВЛЕН: Отмена"""
    data = await state.get_data()
    came_from = data.get('came_from', 'main_menu')
    
    await state.clear()
    
    if came_from == "my_routes":
        # БАГ #11 ИСПРАВЛЕН: Показываем сообщение вместо автоматического вызова списка
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Мои маршруты", callback_data="my_routes")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await callback.message.edit_text(
            "❌ Создание маршрута отменено.\n\n"
            "Нажмите 'Мои маршруты' для просмотра существующих маршрутов.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    else:
        await callback.message.edit_text(
            "<b>👋 Главное меню                              </b>\n\n"
            "Выберите действие:                              ",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
    await callback.answer()

@router.callback_query(F.data == "route_back")
async def back_step(callback: CallbackQuery, state: FSMContext):
    """БАГ #1 ИСПРАВЛЕН: Назад - комментарий очищается на всех шагах ДО комментария"""
    current_state = await state.get_state()
    data = await state.get_data()
    came_from = data.get('came_from', 'main_menu')
    
    if current_state == "RouteCreate:waiting_for_from":
        await state.clear()
        
        if came_from == "my_routes":
            # БАГ #11 ИСПРАВЛЕН: Показываем сообщение вместо автоматического вызова списка
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗺 Мои маршруты", callback_data="my_routes")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            await callback.message.edit_text(
                "❌ Создание маршрута отменено.\n\n"
                "Нажмите 'Мои маршруты' для просмотра существующих маршрутов.",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await callback.message.edit_text(
                "<b>👋 Главное меню                              </b>\n\n"
                "Выберите действие:                              ",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='HTML'
            )
    elif current_state == "RouteCreate:waiting_for_to":
        # БАГ #1 ИСПРАВЛЕН: Очищаем комментарий
        await state.update_data(comment="")
        data = await state.get_data()
        text = pad_text("📍 <b>Откуда?</b>")
        await callback.message.edit_text(
            text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_from)
    elif current_state == "RouteCreate:waiting_for_date":
        # БАГ #1 ИСПРАВЛЕН: Очищаем комментарий
        await state.update_data(to_location="", comment="")
        data = await state.get_data()
        text = pad_text(f"📍 <b>Куда?</b>{format_summary(data)}")
        await callback.message.edit_text(
            text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_to)
    elif current_state == "RouteCreate:waiting_for_time":
        # БАГ #1 + БАГ #24 ИСПРАВЛЕН: Очищаем комментарий и selected_date_iso
        await state.update_data(date_dmy="", selected_date_iso="", comment="")
        data = await state.get_data()
        now = datetime.now()
        text = pad_text(f"📅 <b>ДАТА поездки?</b>{format_summary(data)}")
        await callback.message.edit_text(
            text,
            reply_markup=get_calendar_kb(now.year, now.month, now),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_date)
    elif current_state == "RouteCreate:waiting_for_price":
        # БАГ #1 ИСПРАВЛЕН: Очищаем комментарий
        await state.update_data(time_hm="", comment="")
        data = await state.get_data()
        text = pad_text(f"🕐 <b>ВРЕМЯ отправления?</b>\n\nФормат: 14:30 или 1430{format_summary(data)}")
        await callback.message.edit_text(
            text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_time)
    elif current_state == "RouteCreate:waiting_for_seats":
        # БАГ #1 ИСПРАВЛЕН: Очищаем комментарий
        await state.update_data(price="", comment="")
        data = await state.get_data()
        text = pad_text(
            f"💰 <b>ЦЕНА с пассажира?</b>\n\n"
            f"Ориентировочный расчёт:\n"
            f"- 20 км ≈ 50-100₽ с пассажира\n"
            f"- 40 км ≈ 100-150₽ с пассажира\n"
            f"- 60 км ≈ 150-250₽ с пассажира\n\n"
            f"<b>⚠️ Важно: Цена должна ТОЛЬКО покрывать расходы на дорогу, это НЕ коммерческая перевозка!</b>"
            f"{format_summary(data)}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_price)
    elif current_state == "RouteCreate:waiting_for_comment":
        # БАГ #1 ИСПРАВЛЕН: Очищаем комментарий
        await state.update_data(seats="", comment="")
        data = await state.get_data()
        text = pad_text(f"👥 <b>Сколько МЕСТ?</b>{format_summary(data)}")
        await callback.message.edit_text(
            text,
            reply_markup=get_navigation_kb(),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_seats)
    elif current_state == "RouteCreate:confirm":
        # БАГ #1 ИСПРАВЛЕН: При возврате комментарий очищаем для повторного ввода
        await state.update_data(comment="")
        data = await state.get_data()
        text = pad_text(f"💬 <b>КОММЕНТАРИЙ?</b>\n\n(необязательно){format_summary(data)}")
        await callback.message.edit_text(
            text,
            reply_markup=get_navigation_kb(show_publish=True),
            parse_mode='HTML'
        )
        await state.set_state(RouteCreate.waiting_for_comment)
    
    await callback.answer()

def register_handlers(dp):
    """Регистрация обработчиков"""
    dp.include_router(router)