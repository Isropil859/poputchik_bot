from aiogram import Router, F
from aiogram.types import Message
from handlers.menu import get_main_menu_keyboard

router = Router()

@router.message(F.text == "◀️ Назад")
async def back_to_menu(message: Message):
    """Возврат в главное меню"""
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard()
    )

def register_handlers(dp):
    """Регистрация обработчиков навигации"""
    dp.include_router(router)