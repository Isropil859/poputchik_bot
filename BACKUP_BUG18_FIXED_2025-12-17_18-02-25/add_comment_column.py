import sqlite3

conn = sqlite3.connect('poputchik.db')
cursor = conn.cursor()

# Проверяем есть ли уже колонка
cursor.execute("PRAGMA table_info(routes)")
columns = [col[1] for col in cursor.fetchall()]

if 'comment' not in columns:
    print("Добавляем колонку comment...")
    cursor.execute("ALTER TABLE routes ADD COLUMN comment TEXT DEFAULT ''")
    conn.commit()
    print("✅ Колонка comment добавлена!")
else:
    print("✅ Колонка comment уже есть!")

conn.close()