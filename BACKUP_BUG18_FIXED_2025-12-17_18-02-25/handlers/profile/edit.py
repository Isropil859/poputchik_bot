# file: handlers/profile/edit.py
"""
Редактирование профиля: имя, описание, фото.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database

router = Router(name="profile_edit")


class EditProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_bio = State()
    waiting_for_photo = State()


def _make_edit_menu_keyboard(is_registered: bool = True) -> InlineKeyboardMarkup:
    """Меню редактирования"""
    if is_registered:
        # ЗАРЕГИСТРИРОВАННЫЙ - кнопки "Изменить"
        buttons = [
            [InlineKeyboardButton(text="✏️ Изменить имя", callback_data="profile:edit:name")],
            [InlineKeyboardButton(text="📝 Изменить описание", callback_data="profile:edit:bio")],
            [InlineKeyboardButton(text="📷 Изменить фото", callback_data="profile:edit:photo")],
            [InlineKeyboardButton(text="🔙 Назад к профилю", callback_data="profile")]
        ]
    else:
        # НЕЗАРЕГИСТРИРОВАННЫЙ - кнопки "Добавить"
        buttons = [
            [InlineKeyboardButton(text="📝 Добавить имя", callback_data="profile:edit:name")],
            [InlineKeyboardButton(text="💬 Добавить описание", callback_data="profile:edit:bio")],
            [InlineKeyboardButton(text="📷 Добавить фото", callback_data="profile:edit:photo")],
            [InlineKeyboardButton(text="🔙 Назад к профилю", callback_data="profile")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _make_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="profile:edit:cancel")]
    ])


@router.callback_query(F.data == "profile:edit")
async def show_edit_menu(call: CallbackQuery, state: FSMContext) -> None:
    """Показать меню редактирования"""
    user_id = call.from_user.id
    profile = database.get_user_profile(user_id)
    
    if not profile:
        await call.answer("❌ Профиль не найден", show_alert=True)
        return
    
    # ПРОВЕРКА РЕГИСТРАЦИИ: есть ли display_name
    is_registered = profile.get('display_name') is not None
    
    # Удаляем текущее сообщение (может быть фото)
    try:
        await call.message.delete()
    except Exception:
        pass
    
    if is_registered:
        # ЗАРЕГИСТРИРОВАННЫЙ
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        # НЕЗАРЕГИСТРИРОВАННЫЙ
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    # Отправляем новое текстовое сообщение
    await call.bot.send_message(
        chat_id=call.message.chat.id,
        text=text,
        reply_markup=_make_edit_menu_keyboard(is_registered=is_registered),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "profile:edit:name")
async def edit_name_start(call: CallbackQuery, state: FSMContext) -> None:
    """Начать редактирование имени"""
    await state.set_state(EditProfileStates.waiting_for_name)
    
    # Получаем текущее имя из профиля
    user_id = call.from_user.id
    profile = database.get_user_profile(user_id)
    
    current_name = profile.get('display_name') if profile else None
    
    # Формируем текст с текущим именем
    if current_name:
        text = (
            "✏️ <b>ИЗМЕНИТЬ ИМЯ</b>\n\n"
            f"Текущее имя: <b>{current_name}</b>\n\n"
            "Отправьте новое имя (до 50 символов):"
        )
    else:
        text = (
            "✏️ <b>ДОБАВИТЬ ИМЯ</b>\n\n"
            "Отправьте имя (до 50 символов):"
        )
    
    try:
        await call.message.edit_text(
            text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await call.message.delete()
        await call.bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    await call.answer()


@router.message(EditProfileStates.waiting_for_name)
async def edit_name_process(message: Message, state: FSMContext) -> None:
    """Обработать новое имя"""
    new_name = message.text.strip()
    
    if len(new_name) > 50:
        await message.answer(
            "❌ Имя слишком длинное. Максимум 50 символов.\n"
            "Попробуйте ещё раз:",
            reply_markup=_make_cancel_keyboard()
        )
        return
    
    if len(new_name) < 1:
        await message.answer(
            "❌ Имя не может быть пустым.\n"
            "Попробуйте ещё раз:",
            reply_markup=_make_cancel_keyboard()
        )
        return
    
    # Сохраняем в БД используя универсальную функцию
    database.update_user_profile(message.from_user.id, display_name=new_name)
    
    await state.clear()
    await message.answer(
        f"✅ Имя изменено на: <b>{new_name}</b>",
        parse_mode="HTML"
    )
    
    # Проверяем статус регистрации ПОСЛЕ сохранения
    profile = database.get_user_profile(message.from_user.id)
    is_registered = profile.get('display_name') is not None
    
    # Возвращаемся в меню редактирования
    if is_registered:
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    await message.answer(
        text,
        reply_markup=_make_edit_menu_keyboard(is_registered=is_registered),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "profile:edit:bio")
async def edit_bio_start(call: CallbackQuery, state: FSMContext) -> None:
    """Начать редактирование описания"""
    await state.set_state(EditProfileStates.waiting_for_bio)
    
    # Получаем текущее описание из профиля
    user_id = call.from_user.id
    profile = database.get_user_profile(user_id)
    
    current_bio = profile.get('bio') if profile else None
    
    # Формируем текст с текущим описанием
    if current_bio:
        text = (
            "📝 <b>ИЗМЕНИТЬ ОПИСАНИЕ</b>\n\n"
            f"Текущее описание: <i>{current_bio}</i>\n\n"
            "Отправьте новое описание (до 500 символов):"
        )
    else:
        text = (
            "📝 <b>ДОБАВИТЬ ОПИСАНИЕ</b>\n\n"
            "Отправьте описание (до 500 символов):"
        )
    
    try:
        await call.message.edit_text(
            text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await call.message.delete()
        await call.bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    await call.answer()


@router.message(EditProfileStates.waiting_for_bio)
async def edit_bio_process(message: Message, state: FSMContext) -> None:
    """Обработать новое описание"""
    new_bio = message.text.strip()
    
    if len(new_bio) > 500:
        await message.answer(
            "❌ Описание слишком длинное. Максимум 500 символов.\n"
            "Попробуйте ещё раз:",
            reply_markup=_make_cancel_keyboard()
        )
        return
    
    # Сохраняем в БД используя универсальную функцию
    database.update_user_profile(message.from_user.id, bio=new_bio)
    
    await state.clear()
    await message.answer("✅ Описание изменено")
    
    # Проверяем статус регистрации
    profile = database.get_user_profile(message.from_user.id)
    is_registered = profile.get('display_name') is not None
    
    # Возвращаемся в меню редактирования
    if is_registered:
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    await message.answer(
        text,
        reply_markup=_make_edit_menu_keyboard(is_registered=is_registered),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "profile:edit:photo")
async def edit_photo_start(call: CallbackQuery, state: FSMContext) -> None:
    """Начать редактирование фото"""
    await state.set_state(EditProfileStates.waiting_for_photo)
    
    try:
        await call.message.edit_text(
            "📷 <b>ИЗМЕНИТЬ ФОТО</b>\n\n"
            "Отправьте новое фото:",
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await call.message.delete()
        await call.bot.send_message(
            chat_id=call.message.chat.id,
            text="📷 <b>ИЗМЕНИТЬ ФОТО</b>\n\n"
                 "Отправьте новое фото:",
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    await call.answer()


@router.message(EditProfileStates.waiting_for_photo, F.photo)
async def edit_photo_process(message: Message, state: FSMContext) -> None:
    """Обработать новое фото"""
    photo_file_id = message.photo[-1].file_id
    
    # Сохраняем в БД используя универсальную функцию
    database.update_user_profile(message.from_user.id, photo_file_id=photo_file_id)
    
    await state.clear()
    await message.answer("✅ Фото изменено")
    
    # Проверяем статус регистрации
    profile = database.get_user_profile(message.from_user.id)
    is_registered = profile.get('display_name') is not None
    
    # Возвращаемся в меню редактирования
    if is_registered:
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    await message.answer(
        text,
        reply_markup=_make_edit_menu_keyboard(is_registered=is_registered),
        parse_mode="HTML"
    )


@router.message(EditProfileStates.waiting_for_photo)
async def edit_photo_invalid(message: Message, state: FSMContext) -> None:
    """Неправильный формат фото"""
    await message.answer(
        "❌ Пожалуйста, отправьте фото.\n"
        "Или нажмите кнопку Отмена:",
        reply_markup=_make_cancel_keyboard()
    )


@router.callback_query(F.data == "profile:edit:cancel")
async def edit_cancel(call: CallbackQuery, state: FSMContext) -> None:
    """Отменить редактирование"""
    await state.clear()
    
    # Показываем меню редактирования
    await show_edit_menu(call, state)