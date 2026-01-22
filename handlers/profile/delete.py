# file: handlers/profile/delete.py
"""
Удаление (деактивация) аккаунта с подтверждением.
БАГ #9: Добавлены уведомления пассажирам при удалении профиля водителя
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database
import logging

router = Router(name="profile_delete")
logger = logging.getLogger(__name__)


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
    """БАГ #9 ИСПРАВЛЕН: Выполнить удаление аккаунта с уведомлениями пассажирам"""
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
    
    # БАГ #9: ПЕРЕД удалением профиля уведомляем пассажиров
    try:
        # Получаем ВСЕ маршруты водителя
        driver_routes = database.get_user_routes(user_id)
        
        if driver_routes:
            logger.info(f"БАГ #9: Найдено {len(driver_routes)} маршрутов водителя {user_id}")
            
            # Для каждого маршрута ищем accepted заявки
            for route in driver_routes:
                route_id = route.get('id')
                
                # Получаем ВСЕ заявки на маршрут
                requests = database.get_route_requests(route_id)
                
                if requests:
                    logger.info(f"БАГ #9: Маршрут {route_id} имеет {len(requests)} заявок")
                    
                    # Фильтруем только accepted заявки
                    accepted_requests = [r for r in requests if r.get('status') == 'accepted']
                    
                    if accepted_requests:
                        logger.info(f"БАГ #9: Найдено {len(accepted_requests)} принятых заявок")
                        
                        # Для каждой принятой заявки отправляем уведомление пассажиру
                        for request in accepted_requests:
                            passenger_id = request.get('passenger_id')
                            
                            if passenger_id:
                                try:
                                    # Формируем уведомление
                                    from_loc = route.get('from_location', '—')
                                    to_loc = route.get('to_location', '—')
                                    date_dmy = route.get('date_dmy', '—')
                                    time_hm = route.get('time_hm', '—')
                                    
                                    notification_text = (
                                        f"⚠️ <b>ПОЕЗДКА ОТМЕНЕНА!</b>\n\n"
                                        f"Водитель удалил свой профиль.\n\n"
                                        f"📍 Маршрут: {from_loc} → {to_loc}\n"
                                        f"📅 Дата: {date_dmy}\n"
                                        f"🕐 Время: {time_hm}\n\n"
                                        f"❌ Эта поездка больше не состоится.\n"
                                        f"Найдите другой маршрут в разделе 'Найти маршруты'."
                                    )
                                    
                                    # Отправляем уведомление пассажиру
                                    await call.bot.send_message(
                                        chat_id=passenger_id,
                                        text=notification_text,
                                        parse_mode="HTML"
                                    )
                                    
                                    logger.info(f"✅ БАГ #9: Уведомление отправлено пассажиру {passenger_id}")
                                    
                                except Exception as e:
                                    logger.error(f"❌ БАГ #9: Ошибка отправки уведомления пассажиру {passenger_id}: {e}")
    except Exception as e:
        logger.error(f"❌ БАГ #9: Ошибка при уведомлении пассажиров: {e}")
    
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