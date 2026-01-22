# coding: utf-8
"""
Скрипт для обновления старых карточек с новыми URL-кнопками
"""
import asyncio
import sqlite3
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

DATABASE_NAME = 'poputchik.db'

# Читаем токен из .env файла вручную
def get_bot_token():
    """Читаем BOT_TOKEN из .env файла"""
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    token = line.split('=', 1)[1].strip()
                    # Убираем кавычки если есть
                    token = token.strip('"').strip("'")
                    return token
    except Exception as e:
        print(f"❌ Ошибка чтения .env: {e}")
    return None

BOT_TOKEN = get_bot_token()

if not BOT_TOKEN:
    print("❌ ОШИБКА: Не найден BOT_TOKEN в файле .env!")
    print("Проверьте что в .env есть строка: BOT_TOKEN=ваш_токен")
    exit(1)

print(f"✅ Токен найден: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:]}")

def _format_route_card(route: dict, passenger_id: int = None, status: str = None) -> str:
    """Форматирование карточки маршрута"""
    from_location = route.get('from_location', '—')
    to_location = route.get('to_location', '—')
    date_dmy = route.get('date_dmy', '—')
    time_hm = route.get('time_hm', '—')
    price = route.get('price', 0)
    seats = route.get('seats', 0)
    comment = route.get('comment', '')

    card = f"• {date_dmy}г. {time_hm} — {from_location} → {to_location} | цена: {price}₽ | мест: {seats}"

    if comment:
        card += f"\n💬 {comment}"

    if status:
        if status == 'pending':
            card += "\n\n⏳ <b>Заявка отправлена</b>"
        elif status == 'rejected':
            card += "\n\n❌ <b>Заявка отклонена</b>"
        elif status == 'accepted':
            card += "\n\n✅ <b>Заявка принята!</b>"

    return card

def _make_route_card_keyboard(route_id: int, driver_username: str = None) -> InlineKeyboardMarkup:
    """Клавиатура с URL-кнопкой чата"""
    buttons = []
    
    buttons.append(InlineKeyboardButton(
        text="👋 Откликнуться",
        callback_data=f"rs:card:reply:{route_id}"
    ))
    
    if driver_username:
        buttons.append(InlineKeyboardButton(
            text="💬 Чат",
            url=f"https://t.me/{driver_username}"
        ))
    else:
        buttons.append(InlineKeyboardButton(
            text="💬 Чат",
            callback_data=f"route:chat:error:{route_id}"
        ))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

async def update_all_cards():
    """Обновить все карточки с новыми URL-кнопками"""
    bot = Bot(token=BOT_TOKEN)
    
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Получаем все заявки с карточками
    cursor.execute('''
        SELECT r.id, r.route_id, r.passenger_id, r.status, r.card_chat_id, r.card_message_id,
               rt.from_location, rt.to_location, rt.date_dmy, rt.time_hm, rt.price, rt.seats, rt.comment, rt.user_id,
               u.tg_username as driver_username
        FROM requests r
        JOIN routes rt ON r.route_id = rt.id
        JOIN users u ON rt.user_id = u.user_id
        WHERE r.card_chat_id IS NOT NULL AND r.card_message_id IS NOT NULL
    ''')
    
    requests = cursor.fetchall()
    conn.close()
    
    print(f"🔍 Найдено карточек: {len(requests)}")
    
    updated = 0
    failed = 0
    
    for req in requests:
        try:
            route = {
                'id': req['route_id'],
                'from_location': req['from_location'],
                'to_location': req['to_location'],
                'date_dmy': req['date_dmy'],
                'time_hm': req['time_hm'],
                'price': req['price'],
                'seats': req['seats'],
                'comment': req['comment']
            }
            
            card_text = _format_route_card(route, req['passenger_id'], req['status'])
            kb = _make_route_card_keyboard(req['route_id'], req['driver_username'])
            
            await bot.edit_message_text(
                chat_id=req['card_chat_id'],
                message_id=req['card_message_id'],
                text=card_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            
            updated += 1
            print(f"✅ {updated}/{len(requests)}: маршрут {req['route_id']}")
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed += 1
            print(f"❌ Ошибка маршрут {req['route_id']}: {e}")
    
    await bot.session.close()
    
    print(f"\n🎉 Готово!")
    print(f"✅ Обновлено: {updated}")
    print(f"❌ Ошибок: {failed}")

if __name__ == "__main__":
    print("🚀 Обновляем старые карточки...")
    asyncio.run(update_all_cards())