import sqlite3

DATABASE_NAME = 'poputchik.db'

print("🔧 Миграция: Добавление колонок card_chat_id и card_message_id в таблицу requests")

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# Проверяем, есть ли уже эти колонки
cursor.execute("PRAGMA table_info(requests)")
columns = [column[1] for column in cursor.fetchall()]

if 'card_chat_id' not in columns:
    print("✅ Добавляем колонку card_chat_id...")
    cursor.execute("ALTER TABLE requests ADD COLUMN card_chat_id INTEGER")
    print("✅ Колонка card_chat_id добавлена")
else:
    print("⚠️ Колонка card_chat_id уже существует")

if 'card_message_id' not in columns:
    print("✅ Добавляем колонку card_message_id...")
    cursor.execute("ALTER TABLE requests ADD COLUMN card_message_id INTEGER")
    print("✅ Колонка card_message_id добавлена")
else:
    print("⚠️ Колонка card_message_id уже существует")

conn.commit()
conn.close()

print("🎉 Миграция завершена успешно!")