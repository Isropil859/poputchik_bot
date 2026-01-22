import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import database
from dotenv import load_dotenv
import os

# Загружаем переменные из .env
load_dotenv()

# Импортируем обработчики
from handlers import menu, navigation, route_create, reply_system
from handlers.routes_list import search_handler
from handlers.my_routes import list_handler as my_routes_list
from handlers.my_routes import details_handler, cancel_handler, edit_handler
from handlers.my_trips import my_trips_handler
from handlers.profile import view as profile_view
from handlers.profile import edit as profile_edit
from handlers.profile import delete as profile_delete

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализация бота
    TOKEN = "8270928147:AAEz1zbYarSM_PFe7v3V6gmZ2-6TBjkh8lA"
    bot = Bot(token=TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Инициализация БД
    database.init_db()
    
    # Регистрация роутеров
    dp.include_router(menu.router)
    dp.include_router(navigation.router)
    dp.include_router(route_create.router)
    dp.include_router(reply_system.router)
    
    # Мои поездки - ПЕРЕМЕСТИЛИ ВЫШЕ search_handler!
    dp.include_router(my_trips_handler.router)
    
    # Поиск маршрутов
    dp.include_router(search_handler.router)
    
    # Мои маршруты
    dp.include_router(my_routes_list.router)
    dp.include_router(details_handler.router)
    dp.include_router(cancel_handler.router)
    dp.include_router(edit_handler.router)
    
    # Профиль
    dp.include_router(profile_view.router)
    dp.include_router(profile_edit.router)
    dp.include_router(profile_delete.router)
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())