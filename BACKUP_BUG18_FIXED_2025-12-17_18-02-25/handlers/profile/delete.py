# file: handlers/profile/delete.py
"""
Удаление (деактивация) аккаунта с подтверждением.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database

router = Router(name="profile_delete")


def _make_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    buttons = [
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data="profile:delete:confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "profile:delete")
async def delete_account_confirm(call: CallbackQuery, state: FSMContext) -> None:
    """Показать подтверждение удаления"""
    user_id = call.from_user.id
    
    # Проверяем активен ли профиль
    user = database.get_user_by_id(user_id)
    
    if not user:
        await call.answer("❌ Профиль не найден", show_alert=True)
        return
    
    is_active = user.get('is_active', 0) == 1
    
    if not is_active:
        # Профиль уже удалён
        await call.answer("⚠️ Профиль уже удалён", show_alert=True)
        return
    
    # Удаляем текущее сообщение (может быть фото)
    try:
        await call.message.delete()
    except Exception:
        pass
    
    # Отправляем новое текстовое сообщение
    await call.bot.send_message(
        chat_id=call.message.chat.id,
        text="❗ <b>ВНИМАНИЕ</b>\n\n"
             "Вы действительно хотите удалить аккаунт?\n\n"
             "⚠️ После удаления:\n"
             "• Ваши активные маршруты будут удалены\n"
             "• Вы не сможете создавать новые маршруты\n"
             "• Ваш профиль будет очищен\n\n"
             "Для создания нового профиля нажмите /start",
        reply_markup=_make_confirm_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "profile:delete:confirm")
async def delete_account_execute(call: CallbackQuery, state: FSMContext) -> None:
    """Выполнить удаление аккаунта"""
    user_id = call.from_user.id
    
    # Проверяем активен ли профиль ещё раз
    user = database.get_user_by_id(user_id)
    
    if not user:
        await call.answer("❌ Профиль не найден", show_alert=True)
        return
    
    is_active = user.get('is_active', 0) == 1
    
    if not is_active:
        # Профиль уже удалён
        await call.answer("⚠️ Профиль уже удалён", show_alert=True)
        return
    
    # Деактивируем пользователя
    database.delete_user(user_id)
    
    # Очищаем состояние
    await state.clear()
    
    # Показываем сообщение
    try:
        await call.message.edit_text(
            "🚫 <b>АККАУНТ УДАЛЁН</b>\n\n"
            "Ваш аккаунт был успешно деактивирован.\n\n"
            "Нажмите /start чтобы создать новый профиль.",
            parse_mode="HTML"
        )
    except Exception:
        await call.message.delete()
        await call.bot.send_message(
            chat_id=call.message.chat.id,
            text="🚫 <b>АККАУНТ УДАЛЁН</b>\n\n"
                 "Ваш аккаунт был успешно деактивирован.\n\n"
                 "Нажмите /start чтобы создать новый профиль.",
            parse_mode="HTML"
        )
    
    await call.answer("✅ Аккаунт удалён")