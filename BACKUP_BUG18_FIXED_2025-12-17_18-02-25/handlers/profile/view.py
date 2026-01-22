# file: handlers/profile/view.py
"""
Просмотр профиля пользователя.
Показывает фото, имя, описание, статистику.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database
import logging

router = Router(name="profile_view")


def _make_profile_keyboard(is_registered: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура профиля"""
    if is_registered:
        # ЗАРЕГИСТРИРОВАННЫЙ - все кнопки
        buttons = [
            [InlineKeyboardButton(text="✏️ Редактировать профиль", callback_data="profile:edit")],
            [InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data="profile:delete")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    else:
        # НЕЗАРЕГИСТРИРОВАННЫЙ - без кнопки "Удалить аккаунт"
        buttons = [
            [InlineKeyboardButton(text="✏️ Редактировать профиль", callback_data="profile:edit")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery, state: FSMContext) -> None:
    """Показать профиль пользователя"""
    user_id = call.from_user.id
    
    # БАГ #15: Добавлено логирование для отладки
    logging.info(f"🔍 БАГ #15: Открытие профиля user_id={user_id}")
    
    user = database.get_user_by_id(user_id)
    
    if not user:
        await call.answer("❌ Профиль не найден", show_alert=True)
        return
    
    # БАГ #15: Получаем СВЕЖИЕ данные напрямую из БД
    profile = database.get_user_profile(user_id)
    
    if not profile:
        await call.answer("❌ Ошибка получения профиля", show_alert=True)
        return
    
    # ПРОВЕРКА РЕГИСТРАЦИИ: есть ли display_name
    is_registered = profile.get('display_name') is not None
    
    display_name = profile.get('display_name') or "Имя не указано"
    bio = profile.get('bio') or "Описание не указано"
    routes_count = profile.get('routes_count', 0)
    photo_file_id = profile.get('photo_file_id')
    
    # БАГ #15: Логируем счётчик
    logging.info(f"🔍 БАГ #15: routes_count={routes_count}")
    
    if not is_registered:
        # НЕЗАРЕГИСТРИРОВАННЫЙ ПРОФИЛЬ
        text = (
            f"👤 <b>СОЗДАТЬ ПРОФИЛЬ</b>\n\n"
            f"🆔 Имя: {display_name}\n"
            f"⭐ Рейтинг: Пока нет отзывов\n"
            f"🚗 Маршрутов создано: {routes_count}\n"
            f"💬 Описание: {bio}"
        )
    else:
        # ЗАРЕГИСТРИРОВАННЫЙ ПРОФИЛЬ
        text = (
            f"👤 <b>ПРОФИЛЬ</b>\n\n"
            f"🆔 Имя: {display_name}\n"
            f"⭐ Рейтинг: Пока нет отзывов\n"
            f"🚗 Маршрутов создано: {routes_count}\n"
            f"💬 Описание: {bio}"
        )
    
    # БАГ #15: УПРОЩЁННАЯ логика без двойных окон
    if photo_file_id:
        # Есть фото
        if call.message.photo:
            # Текущее сообщение - фото, редактируем подпись
            try:
                await call.message.edit_caption(
                    caption=text,
                    reply_markup=_make_profile_keyboard(is_registered=is_registered),
                    parse_mode="HTML"
                )
            except Exception as e:
                # Если редактирование не удалось - НЕ удаляем, просто логируем
                logging.error(f"❌ БАГ #15: Не удалось отредактировать caption: {e}")
                # Оставляем как есть, НЕ создаём новое окно
        else:
            # Текущее сообщение - текст, ЗАМЕНЯЕМ на фото
            try:
                await call.message.edit_text(text="⏳")  # Placeholder
                await call.message.delete()
                await call.bot.send_photo(
                    chat_id=call.message.chat.id,
                    photo=photo_file_id,
                    caption=text,
                    reply_markup=_make_profile_keyboard(is_registered=is_registered),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"❌ БАГ #15: Ошибка при замене на фото: {e}")
    else:
        # Нет фото
        if call.message.photo:
            # Текущее сообщение - фото, ЗАМЕНЯЕМ на текст
            try:
                await call.message.delete()
                await call.bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    reply_markup=_make_profile_keyboard(is_registered=is_registered),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"❌ БАГ #15: Ошибка при замене на текст: {e}")
        else:
            # Текущее сообщение - текст, редактируем
            try:
                await call.message.edit_text(
                    text=text,
                    reply_markup=_make_profile_keyboard(is_registered=is_registered),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"❌ БАГ #15: Не удалось отредактировать текст: {e}")
                # Оставляем как есть
    
    await call.answer()