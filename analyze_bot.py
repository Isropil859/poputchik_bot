"""
Скрипт для автоматического анализа структуры бота и создания карты
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Set

class BotAnalyzer:
    def __init__(self, handlers_path: str):
        self.handlers_path = Path(handlers_path)
        self.handlers = []
        self.states = []
        self.keyboards = []
        self.callback_patterns = set()
        
    def analyze(self):
        """Главная функция анализа"""
        print("🔍 Начинаю анализ бота...")
        
        # Сканируем все .py файлы
        py_files = list(self.handlers_path.rglob("*.py"))
        py_files = [f for f in py_files if "__pycache__" not in str(f) and "__init__" not in str(f)]
        
        print(f"📁 Найдено файлов: {len(py_files)}")
        
        for file_path in py_files:
            self._analyze_file(file_path)
        
        print(f"✅ Найдено обработчиков: {len(self.handlers)}")
        print(f"✅ Найдено FSM состояний: {len(self.states)}")
        print(f"✅ Найдено клавиатур: {len(self.keyboards)}")
        print(f"✅ Найдено callback паттернов: {len(self.callback_patterns)}")
        
    def _analyze_file(self, file_path: Path):
        """Анализ одного файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            relative_path = file_path.relative_to(self.handlers_path.parent)
            
            # Ищем callback_query обработчики
            self._find_callback_handlers(content, lines, relative_path)
            
            # Ищем message обработчики
            self._find_message_handlers(content, lines, relative_path)
            
            # Ищем FSM состояния
            self._find_states(content, lines, relative_path)
            
            # Ищем клавиатуры
            self._find_keyboards(content, lines, relative_path)
            
        except Exception as e:
            print(f"⚠️ Ошибка при анализе {file_path}: {e}")
    
    def _find_callback_handlers(self, content: str, lines: List[str], file_path: Path):
        """Находит все callback_query обработчики"""
        pattern = r'@router\.callback_query\(F\.data\s*==\s*["\']([^"\']+)["\']\)'
        pattern_startswith = r'@router\.callback_query\(F\.data\.startswith\(["\']([^"\']+)["\']\)\)'
        
        for match in re.finditer(pattern, content):
            callback_data = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            func_name = self._get_function_name(lines, line_num)
            
            self.handlers.append({
                'type': 'callback',
                'pattern': callback_data,
                'file': str(file_path),
                'line': line_num,
                'function': func_name,
                'exact_match': True
            })
            self.callback_patterns.add(callback_data)
        
        for match in re.finditer(pattern_startswith, content):
            callback_data = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            func_name = self._get_function_name(lines, line_num)
            
            self.handlers.append({
                'type': 'callback',
                'pattern': callback_data + '*',
                'file': str(file_path),
                'line': line_num,
                'function': func_name,
                'exact_match': False
            })
            self.callback_patterns.add(callback_data)
    
    def _find_message_handlers(self, content: str, lines: List[str], file_path: Path):
        """Находит все message обработчики"""
        pattern = r'@router\.message\(([^)]+)\)'
        
        for match in re.finditer(pattern, content):
            state_info = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            func_name = self._get_function_name(lines, line_num)
            
            self.handlers.append({
                'type': 'message',
                'pattern': state_info,
                'file': str(file_path),
                'line': line_num,
                'function': func_name
            })
    
    def _find_states(self, content: str, lines: List[str], file_path: Path):
        """Находит все FSM состояния"""
        # Ищем class XxxStatesGroup
        class_pattern = r'class\s+(\w+)\(StatesGroup\):'
        
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            # Находим все состояния в этом классе
            class_start = match.end()
            class_content = content[class_start:]
            
            # Ищем следующий class или конец файла
            next_class = re.search(r'\nclass\s+', class_content)
            if next_class:
                class_content = class_content[:next_class.start()]
            
            # Находим все State()
            state_pattern = r'(\w+)\s*=\s*State\(\)'
            for state_match in re.finditer(state_pattern, class_content):
                state_name = state_match.group(1)
                self.states.append({
                    'class': class_name,
                    'state': state_name,
                    'full_name': f"{class_name}.{state_name}",
                    'file': str(file_path),
                    'line': line_num
                })
    
    def _find_keyboards(self, content: str, lines: List[str], file_path: Path):
        """Находит все функции создания клавиатур"""
        pattern = r'def\s+(get_\w+_keyboard|_kb_\w+)\('
        
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            # Находим кнопки в этой функции
            func_start = match.end()
            func_content = content[func_start:]
            
            # Ищем следующую функцию
            next_func = re.search(r'\ndef\s+', func_content)
            if next_func:
                func_content = func_content[:next_func.start()]
            
            # Находим все InlineKeyboardButton
            button_pattern = r'InlineKeyboardButton\(text=["\']([^"\']+)["\'],\s*callback_data=["\']([^"\']+)["\']\)'
            buttons = []
            
            for btn_match in re.finditer(button_pattern, func_content):
                btn_text = btn_match.group(1)
                btn_callback = btn_match.group(2)
                buttons.append({
                    'text': btn_text,
                    'callback': btn_callback
                })
                self.callback_patterns.add(btn_callback)
            
            self.keyboards.append({
                'function': func_name,
                'file': str(file_path),
                'line': line_num,
                'buttons': buttons
            })
    
    def _get_function_name(self, lines: List[str], decorator_line: int) -> str:
        """Находит имя функции после декоратора"""
        for i in range(decorator_line, min(decorator_line + 5, len(lines))):
            line = lines[i].strip()
            match = re.match(r'(?:async\s+)?def\s+(\w+)\(', line)
            if match:
                return match.group(1)
        return "unknown"
    
    def generate_map(self) -> str:
        """Генерирует карту бота в Markdown"""
        md = "# 🗺️ КАРТА БОТА \"ПОПУТЧИК\"\n\n"
        md += f"**Дата создания:** {self._get_current_date()}\n\n"
        md += "---\n\n"
        
        # Оглавление
        md += "## 📋 ОГЛАВЛЕНИЕ\n\n"
        md += "1. [Обработчики callback_query](#обработчики-callback_query)\n"
        md += "2. [Обработчики message](#обработчики-message)\n"
        md += "3. [FSM Состояния](#fsm-состояния)\n"
        md += "4. [Клавиатуры](#клавиатуры)\n"
        md += "5. [Навигационная карта](#навигационная-карта)\n\n"
        md += "---\n\n"
        
        # 1. Callback handlers
        md += "## 🔘 Обработчики callback_query\n\n"
        md += "Все обработчики нажатий на inline кнопки:\n\n"
        
        callback_handlers = [h for h in self.handlers if h['type'] == 'callback']
        callback_handlers.sort(key=lambda x: x['pattern'])
        
        for handler in callback_handlers:
            md += f"### `{handler['pattern']}`\n\n"
            md += f"- **Файл:** `{handler['file']}` (строка {handler['line']})\n"
            md += f"- **Функция:** `{handler['function']}()`\n"
            md += f"- **Тип:** {'Точное совпадение' if handler.get('exact_match') else 'Начинается с'}\n\n"
        
        md += "---\n\n"
        
        # 2. Message handlers
        md += "## 💬 Обработчики message\n\n"
        md += "Все обработчики текстовых сообщений:\n\n"
        
        message_handlers = [h for h in self.handlers if h['type'] == 'message']
        
        for handler in message_handlers:
            md += f"### `{handler['function']}()`\n\n"
            md += f"- **Файл:** `{handler['file']}` (строка {handler['line']})\n"
            md += f"- **Состояние:** `{handler['pattern']}`\n\n"
        
        md += "---\n\n"
        
        # 3. FSM States
        md += "## 🔄 FSM Состояния\n\n"
        md += "Все состояния (пошаговые мастера):\n\n"
        
        # Группируем по классам
        states_by_class = {}
        for state in self.states:
            class_name = state['class']
            if class_name not in states_by_class:
                states_by_class[class_name] = []
            states_by_class[class_name].append(state)
        
        for class_name, states in states_by_class.items():
            md += f"### `{class_name}`\n\n"
            md += f"**Файл:** `{states[0]['file']}`\n\n"
            md += "**Состояния:**\n\n"
            for state in states:
                md += f"- `{state['state']}` → `{state['full_name']}`\n"
            md += "\n"
        
        md += "---\n\n"
        
        # 4. Keyboards
        md += "## ⌨️ Клавиатуры\n\n"
        md += "Все функции создания клавиатур:\n\n"
        
        for kb in self.keyboards:
            md += f"### `{kb['function']}()`\n\n"
            md += f"**Файл:** `{kb['file']}` (строка {kb['line']})\n\n"
            
            if kb['buttons']:
                md += "**Кнопки:**\n\n"
                for btn in kb['buttons']:
                    md += f"- `{btn['text']}` → `{btn['callback']}`\n"
            else:
                md += "*Кнопки не обнаружены автоматически*\n"
            md += "\n"
        
        md += "---\n\n"
        
        # 5. Navigation Map
        md += "## 🗺️ Навигационная карта\n\n"
        md += "Карта переходов между разделами:\n\n"
        md += "```\n"
        md += self._generate_navigation_tree()
        md += "```\n\n"
        
        return md
    
    def _generate_navigation_tree(self) -> str:
        """Генерирует дерево навигации"""
        tree = "🏠 ГЛАВНОЕ МЕНЮ (/start, main_menu)\n"
        tree += "│\n"
        tree += "├─ 🔍 Найти маршрут (search_route)\n"
        tree += "│  └─ ...\n"
        tree += "│\n"
        tree += "├─ 🚗 Создать маршрут (create_route)\n"
        tree += "│  ├─ Откуда? (RouteCreate.waiting_for_from)\n"
        tree += "│  ├─ Куда? (RouteCreate.waiting_for_to)\n"
        tree += "│  ├─ Дата (RouteCreate.waiting_for_date)\n"
        tree += "│  ├─ Время (RouteCreate.waiting_for_time)\n"
        tree += "│  ├─ Цена (RouteCreate.waiting_for_price)\n"
        tree += "│  ├─ Места (RouteCreate.waiting_for_seats)\n"
        tree += "│  ├─ Комментарий (RouteCreate.waiting_for_comment)\n"
        tree += "│  └─ Подтверждение (RouteCreate.confirm)\n"
        tree += "│\n"
        tree += "├─ 🧳 Мои поездки (my_trips)\n"
        tree += "│  └─ ...\n"
        tree += "│\n"
        tree += "├─ 🗺️ Мои маршруты (my_routes)\n"
        tree += "│  ├─ Детали (myroutes:details:ID)\n"
        tree += "│  ├─ Редактирование (myroutes:edit:ID)\n"
        tree += "│  ├─ Отмена (myroutes:cancel:ID)\n"
        tree += "│  └─ Восстановление (myroutes:restore:ID)\n"
        tree += "│\n"
        tree += "└─ 👤 Профиль (profile)\n"
        tree += "   ├─ Просмотр\n"
        tree += "   ├─ Редактирование\n"
        tree += "   └─ Удаление\n"
        
        return tree
    
    def _get_current_date(self) -> str:
        """Возвращает текущую дату"""
        from datetime import datetime
        return datetime.now().strftime("%d.%m.%Y %H:%M")
    
    def save_map(self, output_file: str):
        """Сохраняет карту в файл"""
        map_content = self.generate_map()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(map_content)
        
        print(f"\n✅ Карта сохранена в: {output_file}")
        print(f"📊 Размер файла: {len(map_content)} символов")

def main():
    # Путь к handlers
    handlers_path = Path(__file__).parent / "handlers"
    
    print("=" * 60)
    print("🤖 АНАЛИЗАТОР БОТА \"ПОПУТЧИК\"")
    print("=" * 60)
    print()
    
    # Создаём анализатор
    analyzer = BotAnalyzer(handlers_path)
    
    # Анализируем
    analyzer.analyze()
    
    print()
    print("=" * 60)
    print("📝 ГЕНЕРАЦИЯ КАРТЫ")
    print("=" * 60)
    
    # Сохраняем карту
    output_file = Path(__file__).parent / "КАРТА_БОТА_ЧЕРНОВИК.md"
    analyzer.save_map(output_file)
    
    print()
    print("=" * 60)
    print("✅ АНАЛИЗ ЗАВЕРШЁН!")
    print("=" * 60)
    print()
    print("📄 Следующий шаг:")
    print("   1. Открой файл КАРТА_БОТА_ЧЕРНОВИК.md")
    print("   2. Проверь содержимое")
    print("   3. Дополни детали вручную")
    print("   4. Переименуй в КАРТА_БОТА.md")
    print()

if __name__ == "__main__":
    main()