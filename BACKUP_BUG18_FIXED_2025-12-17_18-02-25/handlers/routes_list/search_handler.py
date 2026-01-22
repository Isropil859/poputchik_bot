# file: handlers/routes_list/search_handler.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database

router = Router(name="routes_search")

# Состояния для поиска
class SearchStates(StatesGroup):
    waiting_from = State()
    waiting_to = State()

def _make_search_keyboard(show_apply: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для поиска"""
    buttons = [[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]]

    if show_apply:
        buttons[0].append(InlineKeyboardButton(text="✅ Применить", callback_data="search:apply"))
    else:
        buttons[0].append(InlineKeyboardButton(text="🔍 Поиск", callback_data="search:start"))

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def _format_route_card(route: dict, passenger_id: int = None) -> str:
    """Форматирование карточки маршрута С ПРОФИЛЕМ ВОДИТЕЛЯ"""
    # Получаем данные водителя
    driver_id = route.get('user_id')
    driver_profile = database.get_user_profile(driver_id) if driver_id else None
    
    # Данные маршрута
    from_location = route.get('from_location', '—')
    to_location = route.get('to_location', '—')
    date_dmy = route.get('date_dmy', '—')
    time_hm = route.get('time_hm', '—')
    price = route.get('price', 0)
    seats = route.get('seats', 0)
    comment = route.get('comment', '')

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
    card += f"📍 <b>Маршрут:</b> {from_location} → {to_location}\n"
    card += f"📅 {date_dmy} | 🕐 {time_hm}\n"
    card += f"💰 {price}₽ | 💺 {seats} мест"

    # Комментарий к маршруту
    if comment:
        card += f"\n💬 <b>О поездке:</b> {comment}"

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
    Клавиатура карточки маршрута с кнопкой "Профиль водителя"
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
        
        # ИСПРАВЛЕНО: Строгая проверка username (не None, не пустой, не пробелы)
        if database.is_valid_telegram_username(driver_username):
            # URL-кнопка - сразу открывает чат
            buttons.append(InlineKeyboardButton(
                text="💬 Чат",
                url=f"https://t.me/{driver_username.strip()}"
            ))
        else:
            # Если нет username - показываем ошибку
            buttons.append(InlineKeyboardButton(
                text="💬 Чат",
                callback_data=f"route:chat:error:{route_id}"
            ))
    else:
        # Если нет driver_id - показываем ошибку
        buttons.append(InlineKeyboardButton(
            text="💬 Чат",
            callback_data=f"route:chat:error:{route_id}"
        ))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

@router.callback_query(F.data == "search_route")
async def show_all_routes(c: CallbackQuery, state: FSMContext):
    """ГЛАВНЫЙ ОБРАБОТЧИК: показать ВСЕ маршруты сразу"""
    await state.clear()

    # Получаем ID пассажира
    passenger_id = c.from_user.id

    # Получаем ВСЕ активные маршруты (используем search_routes без фильтров)
    all_routes = database.search_routes()

    if not all_routes:
        await c.message.edit_text(
            "🔭 <b>Маршруты не найдены</b>\n\n"
            "Пока нет активных маршрутов. Создайте свой!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
                InlineKeyboardButton(text="🚗 Создать маршрут", callback_data="create_route")
            ]]),
            parse_mode="HTML"
        )
        await c.answer()
        return

    # Показываем все маршруты
    for route in all_routes:
        card_text = _format_route_card(route, passenger_id=passenger_id)
        route_id = route.get('id')
        driver_id = route.get('user_id')
        kb = _make_route_card_keyboard(route_id, driver_id)

        await c.message.answer(card_text, reply_markup=kb, parse_mode="HTML")

    # Футер с кнопками
    footer_text = f"<b>🔍 Найдено маршрутов: {len(all_routes)}</b>"
    footer_kb = _make_search_keyboard(show_apply=False)

    await c.message.answer(footer_text, reply_markup=footer_kb, parse_mode="HTML")
    await c.answer()

@router.callback_query(F.data == "search:start")
async def start_search(c: CallbackQuery, state: FSMContext):
    """Начало ФИЛЬТРАЦИИ - запрос 'откуда'"""
    await state.set_state(SearchStates.waiting_from)
    await state.update_data(search_from=None, search_to=None)

    text = "❓ <b>Откуда?</b>\n\nВведите город отправления:"

    try:
        await c.message.edit_text(text, reply_markup=_make_search_keyboard(show_apply=False), parse_mode="HTML")
    except Exception:
        await c.message.answer(text, reply_markup=_make_search_keyboard(show_apply=False), parse_mode="HTML")

    await c.answer()

@router.message(SearchStates.waiting_from)
async def process_from(message: Message, state: FSMContext):
    """Обработка ответа 'откуда'"""
    from_city = message.text.strip()

    if not from_city:
        await message.answer("⚠️ Пожалуйста, введите город отправления.")
        return

    await state.update_data(search_from=from_city)
    await state.set_state(SearchStates.waiting_to)

    text = (
        f"❓ <b>Куда?</b>\n\n"
        f"🔍 Откуда: {from_city}\n\n"
        f"Введите город назначения или нажмите <b>Применить</b> чтобы показать все маршруты из {from_city}:"
    )

    await message.answer(text, reply_markup=_make_search_keyboard(show_apply=True), parse_mode="HTML")

@router.message(SearchStates.waiting_to)
async def process_to(message: Message, state: FSMContext):
    """Обработка ответа 'куда'"""
    to_city = message.text.strip()

    if not to_city:
        await message.answer("⚠️ Пожалуйста, введите город назначения.")
        return

    data = await state.get_data()
    from_city = data.get('search_from', '—')

    await state.update_data(search_to=to_city)

    text = (
        f"✅ <b>Готово к поиску!</b>\n\n"
        f"🔍 Откуда: {from_city}\n"
        f"🔍 Куда: {to_city}\n\n"
        f"Нажмите <b>Применить</b> для поиска маршрутов:"
    )

    await message.answer(text, reply_markup=_make_search_keyboard(show_apply=True), parse_mode="HTML")

@router.callback_query(F.data == "search:apply")
async def apply_search(c: CallbackQuery, state: FSMContext):
    """Применение фильтра и показ результатов"""
    data = await state.get_data()
    from_city = data.get('search_from')
    to_city = data.get('search_to')

    if not from_city:
        await c.answer("⚠️ Сначала укажите город отправления", show_alert=True)
        return

    # Используем search_routes с фильтрами
    filtered = database.search_routes(from_loc=from_city, to_loc=to_city)

    # Очищаем состояние
    await state.clear()

    if not filtered:
        search_info = f"{from_city}"
        if to_city:
            search_info += f" → {to_city}"

        await c.message.edit_text(
            f"🔭 <b>Маршруты не найдены</b>\n\n"
            f"По направлению: {search_info}\n\n"
            f"Попробуйте другие города или создайте свой маршрут!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
                InlineKeyboardButton(text="🔍 Новый поиск", callback_data="search:start")
            ]]),
            parse_mode="HTML"
        )
        await c.answer()
        return

    # Получаем ID пассажира
    passenger_id = c.from_user.id

    # Показываем результаты
    for route in filtered:
        card_text = _format_route_card(route, passenger_id=passenger_id)
        route_id = route.get('id')
        driver_id = route.get('user_id')
        kb = _make_route_card_keyboard(route_id, driver_id)

        await c.message.answer(card_text, reply_markup=kb, parse_mode="HTML")

    # Футер
    footer_text = f"<b>🔍 Найдено маршрутов: {len(filtered)}</b>"
    footer_kb = _make_search_keyboard(show_apply=False)

    await c.message.answer(footer_text, reply_markup=footer_kb, parse_mode="HTML")
    await c.answer()

@router.callback_query(F.data == "driver:profile:close")
async def close_driver_profile(callback: CallbackQuery):
    """БАГ #18: Закрыть профиль водителя - просто удаляем сообщение"""
    try:
        await callback.message.delete()
        await callback.answer()
    except Exception:
        await callback.answer("✅ Профиль закрыт")

@router.callback_query(F.data.startswith("driver:profile:"))
async def show_driver_profile(callback: CallbackQuery):
    """Показать ПОЛНЫЙ профиль водителя с фото"""
    driver_id_str = callback.data.split(":")[-1]
    
    # ИСПРАВЛЕНО: Проверка что driver_id не пустой и не None
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
        # С фото
        try:
            await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback.answer()
        except Exception as e:
            # Если фото не загрузилось - отправляем без фото
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback.answer()
    else:
        # Без фото
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

@router.callback_query(F.data.startswith("route:chat:error:"))
async def chat_error(callback: CallbackQuery):
    """Обработка ошибки чата"""
    await callback.answer(
        "❌ У водителя не указан username в Telegram.\n"
        "Чат недоступен.",
        show_alert=True
    )