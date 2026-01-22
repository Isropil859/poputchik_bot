import sqlite3
from datetime import datetime
import logging
import re

DATABASE_NAME = 'poputchik.db'

def is_valid_telegram_username(username):
    """Проверка что username валидный (латиница, цифры, подчёркивание)"""
    if not username or username == "Пользователь":
        return False
    # Username должен содержать только латинские буквы, цифры, подчёркивание
    # и начинаться с буквы
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$'
    return bool(re.match(pattern, username))

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            tg_username TEXT,
            created_at TEXT,
            display_name TEXT,
            photo_file_id TEXT,
            bio TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_location TEXT,
            to_location TEXT,
            date_dmy TEXT,
            time_hm TEXT,
            price INTEGER,
            seats INTEGER,
            comment TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER,
            passenger_id INTEGER,
            status TEXT DEFAULT 'pending',
            card_chat_id INTEGER,
            card_message_id INTEGER,
            created_at TEXT,
            FOREIGN KEY (route_id) REFERENCES routes (id),
            FOREIGN KEY (passenger_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            driver_id INTEGER,
            passenger_id INTEGER,
            created_at TEXT,
            FOREIGN KEY (request_id) REFERENCES requests (id),
            FOREIGN KEY (driver_id) REFERENCES users (user_id),
            FOREIGN KEY (passenger_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            sender_id INTEGER,
            message_text TEXT,
            created_at TEXT,
            FOREIGN KEY (chat_id) REFERENCES chats (id),
            FOREIGN KEY (sender_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("База данных инициализирована")

def get_user_by_id(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(user_id, username):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    
    cursor.execute('SELECT is_active FROM users WHERE user_id = ?', (user_id,))
    existing = cursor.fetchone()
    
    if existing:
        is_active = existing[0]
        
        if is_active == 0:
            cursor.execute('''
                UPDATE users 
                SET is_active = 1, 
                    tg_username = ?, 
                    display_name = NULL, 
                    photo_file_id = NULL, 
                    bio = NULL,
                    created_at = ?
                WHERE user_id = ?
            ''', (username, created_at, user_id))
            logging.info(f"Создан пользователь: {user_id}")
        else:
            cursor.execute('''
                UPDATE users 
                SET tg_username = ?
                WHERE user_id = ?
            ''', (username, user_id))
    else:
        cursor.execute('''
            INSERT INTO users (user_id, tg_username, created_at, display_name, is_active)
            VALUES (?, ?, ?, NULL, 1)
        ''', (user_id, username, created_at))
        logging.info(f"Создан пользователь: {user_id}")
    
    conn.commit()
    conn.close()

def create_route(user_id, from_loc, to_loc, date_dmy, time_hm, price, seats, comment):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO routes (user_id, from_location, to_location, date_dmy, time_hm, 
                           price, seats, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, from_loc, to_loc, date_dmy, time_hm, price, seats, comment, created_at))
    conn.commit()
    route_id = cursor.lastrowid
    conn.close()
    logging.info(f"Создан маршрут: {route_id}")
    return route_id

def search_routes(from_loc=None, to_loc=None):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM routes WHERE is_active = 1 ORDER BY created_at ASC')
    all_routes = cursor.fetchall()
    conn.close()
    
    filtered_routes = []
    for route in all_routes:
        match = True
        
        if from_loc:
            if from_loc.lower() not in route['from_location'].lower():
                match = False
        
        if to_loc:
            if to_loc.lower() not in route['to_location'].lower():
                match = False
        
        if match:
            filtered_routes.append(dict(route))
    
    return filtered_routes

def get_route_by_id(route_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM routes WHERE id = ?', (route_id,))
    route = cursor.fetchone()
    conn.close()
    return dict(route) if route else None

def get_user_routes(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM routes 
        WHERE user_id = ? AND is_active = 1 
        ORDER BY created_at ASC
    ''', (user_id,))
    routes = cursor.fetchall()
    conn.close()
    return [dict(row) for row in routes]

def create_request(route_id, passenger_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    
    cursor.execute('''
        SELECT id FROM requests 
        WHERE route_id = ? AND passenger_id = ? AND status != 'cancelled'
    ''', (route_id, passenger_id))
    
    if cursor.fetchone():
        conn.close()
        return None
    
    cursor.execute('''
        INSERT INTO requests (route_id, passenger_id, created_at)
        VALUES (?, ?, ?)
    ''', (route_id, passenger_id, created_at))
    conn.commit()
    request_id = cursor.lastrowid
    conn.close()
    logging.info(f"Создана заявка: {request_id}")
    return request_id

def get_route_requests(route_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, u.tg_username, u.display_name 
        FROM requests r
        JOIN users u ON r.passenger_id = u.user_id
        WHERE r.route_id = ?
        ORDER BY r.created_at DESC
    ''', (route_id,))
    requests = cursor.fetchall()
    conn.close()
    return [dict(row) for row in requests]

def update_request_status(request_id, status):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE requests SET status = ? WHERE id = ?', (status, request_id))
    conn.commit()
    conn.close()
    logging.info(f"Заявка {request_id} → {status}")

def get_request_by_id(request_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()
    conn.close()
    return dict(request) if request else None

def get_user_trips(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            req.id as request_id,
            req.status,
            req.created_at as request_created_at,
            r.id as route_id,
            r.from_location,
            r.to_location,
            r.date_dmy,
            r.time_hm,
            r.price,
            r.seats,
            r.comment,
            r.is_active,
            r.user_id as driver_id
        FROM requests req
        JOIN routes r ON req.route_id = r.id
        WHERE req.passenger_id = ?
        ORDER BY req.created_at ASC
    ''', (user_id,))
    trips = cursor.fetchall()
    conn.close()
    return [dict(row) for row in trips]

def cancel_trip_request(request_id, user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT passenger_id FROM requests WHERE id = ?
    ''', (request_id,))
    result = cursor.fetchone()
    
    if not result or result[0] != user_id:
        conn.close()
        return False
    
    cursor.execute('''
        UPDATE requests SET status = 'cancelled' WHERE id = ?
    ''', (request_id,))
    conn.commit()
    conn.close()
    logging.info(f"Заявка {request_id} отменена пассажиром {user_id}")
    return True

def cancel_route(route_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE routes SET is_active = 0 WHERE id = ?', (route_id,))
    conn.commit()
    conn.close()
    logging.info(f"Маршрут {route_id} отменён")

def update_route(route_id, **kwargs):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    updates = []
    values = []
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        values.append(value)
    
    values.append(route_id)
    query = f"UPDATE routes SET {', '.join(updates)} WHERE id = ?"
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    logging.info(f"Маршрут {route_id} обновлён")

def create_chat(request_id, driver_id, passenger_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    
    cursor.execute('''
        SELECT id FROM chats WHERE request_id = ?
    ''', (request_id,))
    
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing[0]
    
    cursor.execute('''
        INSERT INTO chats (request_id, driver_id, passenger_id, created_at)
        VALUES (?, ?, ?, ?)
    ''', (request_id, driver_id, passenger_id, created_at))
    conn.commit()
    chat_id = cursor.lastrowid
    conn.close()
    logging.info(f"Создан чат: {chat_id}")
    return chat_id

def get_chat_by_request(request_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM chats WHERE request_id = ?', (request_id,))
    chat = cursor.fetchone()
    conn.close()
    return dict(chat) if chat else None

def save_message(chat_id, sender_id, message_text):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO messages (chat_id, sender_id, message_text, created_at)
        VALUES (?, ?, ?, ?)
    ''', (chat_id, sender_id, message_text, created_at))
    conn.commit()
    conn.close()

def get_chat_messages(chat_id):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM messages 
        WHERE chat_id = ? 
        ORDER BY created_at ASC
    ''', (chat_id,))
    messages = cursor.fetchall()
    conn.close()
    return [dict(row) for row in messages]

def get_user_profile(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return None
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM routes WHERE user_id = ? AND is_active = 1', (user_id,))
    routes_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM requests WHERE passenger_id = ?', (user_id,))
    trips_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'user_id': user['user_id'],
        'display_name': user['display_name'],
        'bio': user['bio'],
        'photo_file_id': user['photo_file_id'],
        'routes_count': routes_count,
        'trips_count': trips_count
    }

def update_user_profile(user_id, **kwargs):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    updates = []
    values = []
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        values.append(value)
    
    values.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    logging.info(f"Профиль {user_id} обновлён")

def delete_user(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_active = 0 WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM routes WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    logging.info(f"Пользователь {user_id} деактивирован, маршруты удалены")

def get_passenger_request_status(route_id, passenger_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT status FROM requests 
        WHERE route_id = ? AND passenger_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (route_id, passenger_id))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_request_card_info(request_id, card_chat_id, card_message_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE requests 
        SET card_chat_id = ?, card_message_id = ? 
        WHERE id = ?
    ''', (card_chat_id, card_message_id, request_id))
    conn.commit()
    conn.close()