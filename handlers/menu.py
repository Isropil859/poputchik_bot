from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import database

router = Router()

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

def get_welcome_keyboard():
    """Клавиатура приветствия с кнопкой продолжить"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Понятно, продолжить", callback_data="welcome:continue")]
    ])
    return keyboard

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or None
    
    # Создаём пользователя если его нет
    database.create_user(user_id, username)
    
    # Проверяем - первый раз пользователь запускает бота или нет
    user = database.get_user_by_id(user_id)
    profile = database.get_user_profile(user_id)
    
    # Если профиль не заполнен - показываем приветствие с описанием
    if not profile or not profile.get('display_name'):
        welcome_text = (
            "👋 <b>Добро пожаловать в бот Попутчик!</b>\n\n"
            "🚗 <b>Это НЕ коммерческое такси!</b>\n\n"
            "Каждый день тысячи людей ездят на работу на машинах, "
            "электричках и автобусах.\n\n"
            "💡 <b>Суть бота - взаимовыгодное попутчество:</b>\n\n"
            "🚙 <b>Для водителей:</b>\n"
            "• Вы едете на работу на своей машине\n"
            "• Разделите расходы на бензин с попутчиками\n"
            "• Это НЕ заработок - только покрытие расходов!\n\n"
            "🧳 <b>Для пассажиров:</b>\n"
            "• Платите ту же сумму, что тратите на транспорт\n"
            "• Но едете с комфортом на легковой машине\n"
            "• Экономите время и силы!\n\n"
            "🤝 <b>Принцип справедливости:</b>\n"
            "Водитель делит реальные расходы на дорогу между всеми "
            "попутчиками. Пассажир платит столько же, сколько потратил бы "
            "на общественный транспорт, но едет с комфортом.\n\n"
            "⚠️ <b>Важно:</b> Это взаимопомощь, а не бизнес!\n\n"
            "Готовы начать?"
        )
        
        await message.answer(
            welcome_text,
            reply_markup=get_welcome_keyboard(),
            parse_mode='HTML'
        )
    else:
        # Если профиль уже заполнен - сразу в меню
        await message.answer(
            "<b>👋 Главное меню                              </b>\n\n"
            "Выберите действие:                              ",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )

@router.callback_query(F.data == "welcome:continue")
async def continue_after_welcome(callback: CallbackQuery):
    """Продолжить после приветствия"""
    await callback.message.edit_text(
        "<b>👋 Главное меню                              </b>\n\n"
        "Выберите действие:                              ",
        reply_markup=get_main_menu_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Показать главное меню"""
    
    # Проверяем тип сообщения
    if callback.message.photo:
        # Если это фото (например из профиля) - удаляем и отправляем новое
        await callback.message.delete()
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="<b>👋 Главное меню                              </b>\n\n"
                 "Выберите действие:                              ",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
    else:
        # Если это текст - просто редактируем
        await callback.message.edit_text(
            "<b>👋 Главное меню                              </b>\n\n"
            "Выберите действие:                              ",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
    
    await callback.answer()

def register_handlers(dp):
    """Регистрация обработчиков меню"""
    dp.include_router(router)