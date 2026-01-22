import sqlite3
from datetime import datetime

def clear_routes_and_requests():
    """Удаляет все маршруты, заявки, чаты и сообщения. Пользователи остаются!"""
    
    conn = sqlite3.connect('poputchik.db')
    cursor = conn.cursor()
    
    print("🔍 Проверяем что будет удалено...")
    
    # Считаем что удалим
    cursor.execute('SELECT COUNT(*) FROM routes')
    routes_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM requests')
    requests_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM chats')
    chats_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM messages')
    messages_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    
    print(f"\n📊 В базе данных:")
    print(f"   👥 Пользователей: {users_count} (НЕ БУДУТ УДАЛЕНЫ)")
    print(f"   🚗 Маршрутов: {routes_count} (БУДУТ УДАЛЕНЫ)")
    print(f"   📝 Заявок: {requests_count} (БУДУТ УДАЛЕНЫ)")
    print(f"   💬 Чатов: {chats_count} (БУДУТ УДАЛЕНЫ)")
    print(f"   📨 Сообщений: {messages_count} (БУДУТ УДАЛЕНЫ)")
    
    # Подтверждение
    answer = input(f"\n⚠️  УДАЛИТЬ {routes_count} маршрутов и {requests_count} заявок? (да/нет): ")
    
    if answer.lower() != 'да':
        print("❌ Отменено. Ничего не удалено.")
        conn.close()
        return
    
    # Удаляем
    print("\n🗑️  Удаляем...")
    
    cursor.execute('DELETE FROM messages')
    print(f"   ✅ Удалено сообщений: {messages_count}")
    
    cursor.execute('DELETE FROM chats')
    print(f"   ✅ Удалено чатов: {chats_count}")
    
    cursor.execute('DELETE FROM requests')
    print(f"   ✅ Удалено заявок: {requests_count}")
    
    cursor.execute('DELETE FROM routes')
    print(f"   ✅ Удалено маршрутов: {routes_count}")
    
    conn.commit()
    
    # Проверяем что осталось
    cursor.execute('SELECT COUNT(*) FROM users')
    users_left = cursor.fetchone()[0]
    
    print(f"\n✅ ГОТОВО!")
    print(f"   👥 Пользователей осталось: {users_left}")
    print(f"   🚗 Маршрутов осталось: 0")
    print(f"   📝 Заявок осталось: 0")
    
    conn.close()

if __name__ == "__main__":
    clear_routes_and_requests()