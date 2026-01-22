# file: handlers/profile/edit.py
"""
Редактирование профиля: имя, описание, фото.
БАГ #10 ИСПРАВЛЕН: Кнопка "Удалить фото" показывается ТОЛЬКО если фото есть
БАГ #15 ИСПРАВЛЕН: Все действия происходят в одном окне
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


def _make_edit_menu_keyboard(is_registered: bool = True, has_photo: bool = False) -> InlineKeyboardMarkup:
    """
    БАГ #10 ИСПРАВЛЕН: Меню редактирования с динамическими кнопками
    - has_photo = True → "Изменить фото" + кнопка "Удалить"
    - has_photo = False → "Добавить фото" (БЕЗ кнопки "Удалить")
    """
    if is_registered:
        # ЗАРЕГИСТРИРОВАННЫЙ - кнопки "Изменить"
        photo_text = "📷 Изменить фото" if has_photo else "📷 Добавить фото"
        
        # БАГ #10 ИСПРАВЛЕН: Кнопка "Удалить фото" ТОЛЬКО если фото есть
        if has_photo:
            photo_row = [
                InlineKeyboardButton(text=photo_text, callback_data="profile:edit:photo"),
                InlineKeyboardButton(text="🗑 Удалить фото", callback_data="profile:delete:photo")
            ]
        else:
            photo_row = [
                InlineKeyboardButton(text=photo_text, callback_data="profile:edit:photo")
            ]
        
        buttons = [
            [InlineKeyboardButton(text="✏️ Изменить имя", callback_data="profile:edit:name")],
            [InlineKeyboardButton(text="📝 Изменить описание", callback_data="profile:edit:bio")],
            photo_row,
            [InlineKeyboardButton(text="✅ Готово", callback_data="profile")]
        ]
    else:
        # НЕЗАРЕГИСТРИРОВАННЫЙ - кнопки "Добавить"
        photo_text = "📷 Добавить фото"
        
        # БАГ #10 ИСПРАВЛЕН: Кнопка "Удалить фото" ТОЛЬКО если фото есть
        if has_photo:
            photo_row = [
                InlineKeyboardButton(text=photo_text, callback_data="profile:edit:photo"),
                InlineKeyboardButton(text="🗑 Удалить фото", callback_data="profile:delete:photo")
            ]
        else:
            photo_row = [
                InlineKeyboardButton(text=photo_text, callback_data="profile:edit:photo")
            ]
        
        buttons = [
            [InlineKeyboardButton(text="📝 Добавить имя", callback_data="profile:edit:name")],
            [InlineKeyboardButton(text="💬 Добавить описание", callback_data="profile:edit:bio")],
            photo_row,
            [InlineKeyboardButton(text="✅ Готово", callback_data="profile")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _make_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="profile:edit:cancel")]
    ])


def _make_delete_photo_confirm_keyboard() -> InlineKeyboardMarkup:
    """БАГ #10: Подтверждение удаления фото"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data="profile:delete:photo:confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="profile:edit")
        ]
    ])


@router.callback_query(F.data == "profile:edit")
async def show_edit_menu(call: CallbackQuery, state: FSMContext) -> None:
    """БАГ #15 ИСПРАВЛЕН: Показать меню редактирования"""
    user_id = call.from_user.id
    profile = database.get_user_profile(user_id)
    
    if not profile:
        await call.answer("❌ Профиль не найден", show_alert=True)
        return
    
    # ПРОВЕРКА РЕГИСТРАЦИИ: есть ли display_name
    is_registered = profile.get('display_name') is not None
    
    # БАГ #10: Проверяем есть ли фото
    has_photo = profile.get('photo_file_id') is not None
    
    if is_registered:
        # ЗАРЕГИСТРИРОВАННЫЙ
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        # НЕЗАРЕГИСТРИРОВАННЫЙ
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    # БАГ #15: Редактируем существующее сообщение или создаём новое
    try:
        msg = await call.message.edit_text(
            text,
            reply_markup=_make_edit_menu_keyboard(is_registered=is_registered, has_photo=has_photo),
            parse_mode="HTML"
        )
        # БАГ #15: Сохраняем message_id
        await state.update_data(bot_message_id=msg.message_id)
    except Exception:
        # Если не удалось отредактировать, удаляем и создаём новое
        try:
            await call.message.delete()
        except:
            pass
        msg = await call.bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            reply_markup=_make_edit_menu_keyboard(is_registered=is_registered, has_photo=has_photo),
            parse_mode="HTML"
        )
        # БАГ #15: Сохраняем message_id
        await state.update_data(bot_message_id=msg.message_id)
    
    await call.answer()


@router.callback_query(F.data == "profile:edit:name")
async def edit_name_start(call: CallbackQuery, state: FSMContext) -> None:
    """БАГ #15 ИСПРАВЛЕН: Начать редактирование имени"""
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
    
    # БАГ #15: Редактируем существующее сообщение
    try:
        msg = await call.message.edit_text(
            text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(bot_message_id=msg.message_id)
    except Exception:
        try:
            await call.message.delete()
        except:
            pass
        msg = await call.bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(bot_message_id=msg.message_id)
    
    await call.answer()


@router.message(EditProfileStates.waiting_for_name)
async def edit_name_process(message: Message, state: FSMContext) -> None:
    """БАГ #15 ИСПРАВЛЕН: Обработать новое имя"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    # БАГ #15: Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass
    
    new_name = message.text.strip()
    
    if len(new_name) > 50:
        text = "❌ Имя слишком длинное. Максимум 50 символов.\nПопробуйте ещё раз:"
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=bot_msg_id,
                text=text,
                reply_markup=_make_cancel_keyboard()
            )
        except:
            pass
        return
    
    if len(new_name) < 1:
        text = "❌ Имя не может быть пустым.\nПопробуйте ещё раз:"
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=bot_msg_id,
                text=text,
                reply_markup=_make_cancel_keyboard()
            )
        except:
            pass
        return
    
    # Сохраняем в БД
    database.update_user_profile(message.from_user.id, display_name=new_name)
    
    await state.clear()
    
    # Проверяем статус регистрации ПОСЛЕ сохранения
    profile = database.get_user_profile(message.from_user.id)
    is_registered = profile.get('display_name') is not None
    has_photo = profile.get('photo_file_id') is not None
    
    # Возвращаемся в меню редактирования
    if is_registered:
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    # БАГ #15: Редактируем существующее сообщение
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=_make_edit_menu_keyboard(is_registered=is_registered, has_photo=has_photo),
            parse_mode="HTML"
        )
    except:
        pass


@router.callback_query(F.data == "profile:edit:bio")
async def edit_bio_start(call: CallbackQuery, state: FSMContext) -> None:
    """БАГ #15 ИСПРАВЛЕН: Начать редактирование описания"""
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
    
    # БАГ #15: Редактируем существующее сообщение
    try:
        msg = await call.message.edit_text(
            text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(bot_message_id=msg.message_id)
    except Exception:
        try:
            await call.message.delete()
        except:
            pass
        msg = await call.bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(bot_message_id=msg.message_id)
    
    await call.answer()


@router.message(EditProfileStates.waiting_for_bio)
async def edit_bio_process(message: Message, state: FSMContext) -> None:
    """БАГ #15 ИСПРАВЛЕН: Обработать новое описание"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    # БАГ #15: Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass
    
    new_bio = message.text.strip()
    
    if len(new_bio) > 500:
        text = "❌ Описание слишком длинное. Максимум 500 символов.\nПопробуйте ещё раз:"
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=bot_msg_id,
                text=text,
                reply_markup=_make_cancel_keyboard()
            )
        except:
            pass
        return
    
    # Сохраняем в БД
    database.update_user_profile(message.from_user.id, bio=new_bio)
    
    await state.clear()
    
    # Проверяем статус регистрации
    profile = database.get_user_profile(message.from_user.id)
    is_registered = profile.get('display_name') is not None
    has_photo = profile.get('photo_file_id') is not None
    
    # Возвращаемся в меню редактирования
    if is_registered:
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    # БАГ #15: Редактируем существующее сообщение
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=_make_edit_menu_keyboard(is_registered=is_registered, has_photo=has_photo),
            parse_mode="HTML"
        )
    except:
        pass


@router.callback_query(F.data == "profile:edit:photo")
async def edit_photo_start(call: CallbackQuery, state: FSMContext) -> None:
    """БАГ #10 + БАГ #15 ИСПРАВЛЕН: Начать редактирование фото"""
    await state.set_state(EditProfileStates.waiting_for_photo)
    
    # БАГ #10: Проверяем есть ли фото
    user_id = call.from_user.id
    profile = database.get_user_profile(user_id)
    has_photo = profile.get('photo_file_id') is not None if profile else False
    
    # БАГ #10: Динамический текст
    if has_photo:
        header_text = "📷 <b>ИЗМЕНИТЬ ФОТО</b>\n\n"
    else:
        header_text = "📷 <b>ДОБАВИТЬ ФОТО</b>\n\n"
    
    # БАГ #15: Редактируем существующее сообщение
    try:
        msg = await call.message.edit_text(
            header_text + "Отправьте новое фото:",
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(bot_message_id=msg.message_id)
    except Exception:
        try:
            await call.message.delete()
        except:
            pass
        msg = await call.bot.send_message(
            chat_id=call.message.chat.id,
            text=header_text + "Отправьте новое фото:",
            reply_markup=_make_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(bot_message_id=msg.message_id)
    
    await call.answer()


@router.message(EditProfileStates.waiting_for_photo, F.photo)
async def edit_photo_process(message: Message, state: FSMContext) -> None:
    """БАГ #15 ИСПРАВЛЕН: Обработать новое фото"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    # БАГ #15: Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass
    
    photo_file_id = message.photo[-1].file_id
    
    # Сохраняем в БД
    database.update_user_profile(message.from_user.id, photo_file_id=photo_file_id)
    
    await state.clear()
    
    # Проверяем статус регистрации
    profile = database.get_user_profile(message.from_user.id)
    is_registered = profile.get('display_name') is not None
    has_photo = profile.get('photo_file_id') is not None
    
    # Возвращаемся в меню редактирования
    if is_registered:
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\nВыберите что хотите изменить:"
    else:
        text = "📝 <b>СОЗДАНИЕ ПРОФИЛЯ</b>\n\nДобавьте информацию о себе:"
    
    # БАГ #15: Редактируем существующее сообщение
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=_make_edit_menu_keyboard(is_registered=is_registered, has_photo=has_photo),
            parse_mode="HTML"
        )
    except:
        pass


@router.message(EditProfileStates.waiting_for_photo)
async def edit_photo_invalid(message: Message, state: FSMContext) -> None:
    """БАГ #15 ИСПРАВЛЕН: Неправильный формат фото"""
    data = await state.get_data()
    bot_msg_id = data.get('bot_message_id')
    
    # БАГ #15: Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass
    
    text = "❌ Пожалуйста, отправьте фото.\nИли нажмите кнопку Отмена:"
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=_make_cancel_keyboard()
        )
    except:
        pass


@router.callback_query(F.data == "profile:delete:photo")
async def delete_photo_confirm(call: CallbackQuery, state: FSMContext) -> None:
    """БАГ #10 ИСПРАВЛЕН: Подтверждение удаления фото"""
    try:
        await call.message.edit_text(
            "🗑 <b>УДАЛИТЬ ФОТО?</b>\n\n"
            "Вы уверены, что хотите удалить фото профиля?",
            reply_markup=_make_delete_photo_confirm_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await call.message.delete()
        await call.bot.send_message(
            chat_id=call.message.chat.id,
            text="🗑 <b>УДАЛИТЬ ФОТО?</b>\n\n"
                 "Вы уверены, что хотите удалить фото профиля?",
            reply_markup=_make_delete_photo_confirm_keyboard(),
            parse_mode="HTML"
        )
    
    await call.answer()


@router.callback_query(F.data == "profile:delete:photo:confirm")
async def delete_photo_execute(call: CallbackQuery, state: FSMContext) -> None:
    """БАГ #10 ИСПРАВЛЕН: Выполнить удаление фото после подтверждения"""
    user_id = call.from_user.id
    
    # Удаляем фото из БД (устанавливаем NULL)
    database.update_user_profile(user_id, photo_file_id=None)
    
    await call.answer("✅ Фото удалено", show_alert=True)
    
    # БАГ #10 ИСПРАВЛЕН: Возвращаемся в меню редактирования
    await show_edit_menu(call, state)


@router.callback_query(F.data == "profile:edit:cancel")
async def edit_cancel(call: CallbackQuery, state: FSMContext) -> None:
    """Отменить редактирование"""
    await state.clear()
    
    # Показываем меню редактирования
    await show_edit_menu(call, state)