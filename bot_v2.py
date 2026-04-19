"""
╔══════════════════════════════════════════════════════════════╗
║        🐍 PYTHON QUIZ BOT v2.0 — улучшенная версия          ║
║                                                              ║
║  Новое в v2.0:                                               ║
║  ✅ Категории квиза (Циклы, Функции, Списки и др.)           ║
║  ✅ Подсказки во время квиза (за -1 очко)                    ║
║  ✅ Таблица лидеров (топ-5 игроков)                          ║
║  ✅ Ежедневный вопрос дня                                    ║
║  ✅ Сохранение статистики в JSON-файл                        ║
║  ✅ Красивое оформление сообщений                            ║
║  ✅ Больше вопросов по всем темам                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import os
import random
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ─────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ
# ─────────────────────────────────────────────────────────────

load_dotenv()

# Вставь токен сюда напрямую (для быстрого теста):
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# BOT_TOKEN = "ваш_токен_сюда"

if not BOT_TOKEN:
    raise SystemExit(
        "\n❌ Токен не найден!\n"
        "Создайте файл .env и напишите: BOT_TOKEN=ваш_токен\n"
    )

# Файл для сохранения статистики всех пользователей
STATS_FILE = Path("stats.json")

# ─────────────────────────────────────────────────────────────
# ЛОГИРОВАНИЕ
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# FSM — СОСТОЯНИЯ
# ─────────────────────────────────────────────────────────────

class QuizStates(StatesGroup):
    choosing_category = State()   # пользователь выбирает категорию
    in_progress       = State()   # проходит квиз

# ─────────────────────────────────────────────────────────────
# БАЗА ВОПРОСОВ ПО КАТЕГОРИЯМ
# ─────────────────────────────────────────────────────────────

QUESTIONS_DB: dict[str, list[dict]] = {

    "loops": [
        {
            "question": "🔁 Сколько раз выполнится цикл?\n\n<code>for i in range(2, 10, 3):\n    pass</code>",
            "options": ["2", "3", "4", "8"],
            "correct": 1,
            "hint": "range(2, 10, 3) → 2, 5, 8 — всего 3 значения.",
        },
        {
            "question": "🔁 Что выведет код?\n\n<code>i = 0\nwhile i &lt; 3:\n    i += 1\nprint(i)</code>",
            "options": ["0", "2", "3", "4"],
            "correct": 2,
            "hint": "Цикл while выполняется пока i < 3, на выходе i = 3.",
        },
        {
            "question": "🔁 Что делает <code>break</code> в цикле?",
            "options": [
                "Пропускает текущую итерацию",
                "Полностью прерывает цикл",
                "Перезапускает цикл",
                "Выводит ошибку",
            ],
            "correct": 1,
            "hint": "break — выход из цикла. continue — пропуск итерации.",
        },
        {
            "question": "🔁 Что выведет код?\n\n<code>for i in range(5):\n    if i == 3:\n        continue\n    print(i, end=' ')</code>",
            "options": ["0 1 2 3 4", "0 1 2 4", "1 2 4 5", "0 1 2"],
            "correct": 1,
            "hint": "continue пропускает i=3, остальные значения выводятся.",
        },
        {
            "question": "🔁 Каков результат?\n\n<code>s = 0\nfor i in range(1, 5):\n    s += i\nprint(s)</code>",
            "options": ["6", "10", "15", "4"],
            "correct": 1,
            "hint": "1+2+3+4 = 10. range(1,5) это 1,2,3,4.",
        },
    ],

    "lists": [
        {
            "question": "📋 Что выведет код?\n\n<code>lst = [1, 2, 3]\nlst.append(4)\nprint(len(lst))</code>",
            "options": ["3", "4", "5", "Error"],
            "correct": 1,
            "hint": "append добавляет элемент в конец, длина становится 4.",
        },
        {
            "question": "📋 Что вернёт выражение?\n\n<code>'Python'[::-1]</code>",
            "options": ["'Python'", "'nohtyP'", "['P','y','t','h','o','n']", "Error"],
            "correct": 1,
            "hint": "Срез [::-1] разворачивает последовательность.",
        },
        {
            "question": "📋 Какой метод удаляет последний элемент списка?",
            "options": ["remove()", "delete()", "pop()", "clear()"],
            "correct": 2,
            "hint": "pop() без аргументов удаляет и возвращает последний элемент.",
        },
        {
            "question": "📋 Что выведет код?\n\n<code>a = [1, 2, 3]\nb = a\nb.append(4)\nprint(len(a))</code>",
            "options": ["3", "4", "2", "Error"],
            "correct": 1,
            "hint": "b = a — не копия! Обе переменные указывают на один список.",
        },
        {
            "question": "📋 Результат list comprehension?\n\n<code>[x**2 for x in range(4)]</code>",
            "options": ["[1, 4, 9, 16]", "[0, 1, 4, 9]", "[0, 2, 4, 6]", "[1, 2, 3, 4]"],
            "correct": 1,
            "hint": "range(4) → 0,1,2,3. Квадраты: 0,1,4,9.",
        },
    ],

    "functions": [
        {
            "question": "⚙️ Что делает ключевое слово <code>lambda</code>?",
            "options": [
                "Создаёт класс",
                "Создаёт анонимную функцию",
                "Импортирует модуль",
                "Объявляет переменную",
            ],
            "correct": 1,
            "hint": "lambda x: x*2 — то же что def f(x): return x*2, в одну строку.",
        },
        {
            "question": "⚙️ Что выведет код?\n\n<code>def f(x, y=10):\n    return x + y\nprint(f(5))</code>",
            "options": ["5", "10", "15", "Error"],
            "correct": 2,
            "hint": "y=10 — значение по умолчанию. f(5) → 5 + 10 = 15.",
        },
        {
            "question": "⚙️ Что означает <code>*args</code> в функции?",
            "options": [
                "Умножение аргументов",
                "Произвольное кол-во позиционных аргументов",
                "Именованные аргументы",
                "Ссылка на функцию",
            ],
            "correct": 1,
            "hint": "*args собирает любое количество позиционных аргументов в кортеж.",
        },
        {
            "question": "⚙️ Что вернёт функция?\n\n<code>def f():\n    pass\nprint(f())</code>",
            "options": ["0", "''", "False", "None"],
            "correct": 3,
            "hint": "Функция без return возвращает None.",
        },
        {
            "question": "⚙️ Что выведет код?\n\n<code>def double(lst):\n    return [x*2 for x in lst]\nprint(double([1, 2, 3]))</code>",
            "options": ["[1, 2, 3]", "[2, 4, 6]", "[1, 4, 9]", "Error"],
            "correct": 1,
            "hint": "List comprehension умножает каждый элемент на 2.",
        },
    ],

    "dicts": [
        {
            "question": "📦 Что выведет код?\n\n<code>d = {'a': 1}\nprint(d.get('b', 0))</code>",
            "options": ["None", "KeyError", "0", "''"],
            "correct": 2,
            "hint": "dict.get(key, default) возвращает default если ключ не найден.",
        },
        {
            "question": "📦 Как проверить, есть ли ключ в словаре?",
            "options": ["d.has('key')", "'key' in d", "d.contains('key')", "d.find('key')"],
            "correct": 1,
            "hint": "Оператор in работает для проверки ключей в словаре.",
        },
        {
            "question": "📦 Что вернёт <code>d.items()</code>?",
            "options": [
                "Список ключей",
                "Список значений",
                "Пары (ключ, значение)",
                "Длину словаря",
            ],
            "correct": 2,
            "hint": "items() возвращает view с парами (ключ, значение).",
        },
        {
            "question": "📦 Что выведет код?\n\n<code>d = {1: 'a', 2: 'b'}\nd[1] = 'z'\nprint(d[1])</code>",
            "options": ["'a'", "'z'", "Error", "None"],
            "correct": 1,
            "hint": "Присваивание по существующему ключу обновляет значение.",
        },
    ],

    "strings": [
        {
            "question": "🔤 Что выведет код?\n\n<code>s = 'hello'\nprint(s.upper())</code>",
            "options": ["'hello'", "'HELLO'", "'Hello'", "Error"],
            "correct": 1,
            "hint": "upper() переводит все символы в верхний регистр.",
        },
        {
            "question": "🔤 Каков результат?\n\n<code>print(len('Python'))</code>",
            "options": ["5", "6", "7", "Error"],
            "correct": 1,
            "hint": "В слове 'Python' 6 символов: P-y-t-h-o-n.",
        },
        {
            "question": "🔤 Что делает <code>split()</code>?",
            "options": [
                "Разбивает строку в список",
                "Соединяет список в строку",
                "Удаляет пробелы",
                "Переворачивает строку",
            ],
            "correct": 0,
            "hint": "'a b c'.split() → ['a', 'b', 'c']. Обратное — join().",
        },
        {
            "question": "🔤 Что вернёт выражение?\n\n<code>'python'.capitalize()</code>",
            "options": ["'PYTHON'", "'Python'", "'python'", "Error"],
            "correct": 1,
            "hint": "capitalize() делает первую букву заглавной, остальные строчными.",
        },
    ],

    "basics": [
        {
            "question": "🐍 Какой тип у значения <code>[]</code>?",
            "options": ["tuple", "list", "dict", "set"],
            "correct": 1,
            "hint": "[] — литерал пустого списка. () — кортеж, {} — словарь или множество.",
        },
        {
            "question": "🐍 Каков результат?\n\n<code>print(10 // 3)</code>",
            "options": ["3.33", "3", "4", "1"],
            "correct": 1,
            "hint": "// — целочисленное деление (без остатка). % — остаток.",
        },
        {
            "question": "🐍 Что такое <code>None</code> в Python?",
            "options": ["Ноль", "Пустая строка", "Отсутствие значения", "False"],
            "correct": 2,
            "hint": "None — специальный объект, обозначающий отсутствие значения.",
        },
        {
            "question": "🐍 Какой оператор проверяет равенство?",
            "options": ["=", "==", "===", ":="],
            "correct": 1,
            "hint": "= это присваивание, == это сравнение на равенство.",
        },
        {
            "question": "🐍 Что выведет код?\n\n<code>x = 5\nprint(type(x).__name__)</code>",
            "options": ["'number'", "'int'", "'integer'", "'float'"],
            "correct": 1,
            "hint": "type(5) → <class 'int'>, __name__ возвращает 'int'.",
        },
    ],
}

# Мета-информация о категориях
CATEGORIES: dict[str, dict] = {
    "basics":    {"label": "🐍 Основы Python",  "emoji": "🐍"},
    "loops":     {"label": "🔁 Циклы",           "emoji": "🔁"},
    "lists":     {"label": "📋 Списки",           "emoji": "📋"},
    "functions": {"label": "⚙️ Функции",          "emoji": "⚙️"},
    "dicts":     {"label": "📦 Словари",          "emoji": "📦"},
    "strings":   {"label": "🔤 Строки",           "emoji": "🔤"},
}

# ─────────────────────────────────────────────────────────────
# ШПАРГАЛКИ
# ─────────────────────────────────────────────────────────────

CHEATSHEETS: dict[str, dict] = {
    "loops": {
        "title": "🔁 Циклы",
        "text": (
            "<b>for</b> — перебор элементов:\n"
            "<pre>for i in range(5):\n    print(i)  # 0 1 2 3 4</pre>\n\n"
            "<b>while</b> — пока условие истинно:\n"
            "<pre>n = 3\nwhile n > 0:\n    n -= 1</pre>\n\n"
            "<b>break / continue / else:</b>\n"
            "<pre>for i in range(10):\n"
            "    if i == 5: break\n"
            "    if i % 2 == 0: continue\n"
            "else:\n    print('завершён')</pre>"
        ),
    },
    "lists": {
        "title": "📋 Списки",
        "text": (
            "<b>Основные операции:</b>\n"
            "<pre>lst = [1, 2, 3]\n"
            "lst.append(4)    # добавить в конец\n"
            "lst.insert(0, 0) # вставить по индексу\n"
            "lst.pop()        # удалить последний\n"
            "lst.remove(2)    # удалить по значению\n"
            "lst.sort()       # сортировка</pre>\n\n"
            "<b>Срезы:</b>\n"
            "<pre>lst[1:3]   # элементы 1 и 2\n"
            "lst[::-1]  # разворот\n"
            "lst[::2]   # каждый второй</pre>\n\n"
            "<b>List comprehension:</b>\n"
            "<pre>[x**2 for x in range(6) if x % 2 == 0]\n# [0, 4, 16]</pre>"
        ),
    },
    "functions": {
        "title": "⚙️ Функции",
        "text": (
            "<b>Определение:</b>\n"
            "<pre>def greet(name, msg='Привет'):\n"
            "    return f'{msg}, {name}!'\n\n"
            "greet('Аня')           # Привет, Аня!\n"
            "greet('Вася', 'Хэй')  # Хэй, Вася!</pre>\n\n"
            "<b>*args и **kwargs:</b>\n"
            "<pre>def info(*args, **kwargs):\n"
            "    print(args, kwargs)\n\n"
            "info(1, 2, x=3)  # (1, 2) {'x': 3}</pre>\n\n"
            "<b>Lambda:</b>\n"
            "<pre>sq = lambda x: x ** 2\n"
            "list(map(sq, [1,2,3]))  # [1, 4, 9]</pre>"
        ),
    },
    "dicts": {
        "title": "📦 Словари",
        "text": (
            "<b>Создание и доступ:</b>\n"
            "<pre>d = {'name': 'Python', 'ver': 3}\n"
            "d['name']         # 'Python'\n"
            "d.get('age', 0)   # 0 (без KeyError)\n"
            "d['new'] = 42     # добавить ключ\n"
            "del d['ver']      # удалить ключ</pre>\n\n"
            "<b>Перебор:</b>\n"
            "<pre>for k, v in d.items():\n"
            "    print(f'{k}: {v}')</pre>\n\n"
            "<b>Dict comprehension:</b>\n"
            "<pre>{x: x**2 for x in range(5)}\n# {0:0, 1:1, 2:4, 3:9, 4:16}</pre>"
        ),
    },
    "strings": {
        "title": "🔤 Строки",
        "text": (
            "<b>Полезные методы:</b>\n"
            "<pre>s = '  Hello, World!  '\n"
            "s.strip()              # убрать пробелы\n"
            "s.lower() / s.upper()  # регистр\n"
            "s.replace('o', '0')    # замена\n"
            "s.split(', ')          # ['Hello', 'World!']\n"
            "', '.join(['a','b'])   # 'a, b'\n"
            "s.startswith('Hello')  # True</pre>\n\n"
            "<b>f-строки:</b>\n"
            "<pre>name, age = 'Аня', 16\n"
            "f'Мне {age} лет, я {name}'\n\n"
            "pi = 3.14159\n"
            "f'{pi:.2f}'  # '3.14'</pre>"
        ),
    },
    "basics": {
        "title": "🐍 Основы Python",
        "text": (
            "<b>Типы данных:</b>\n"
            "<pre>int    → 42\n"
            "float  → 3.14\n"
            "str    → 'hello'\n"
            "bool   → True / False\n"
            "list   → [1, 2, 3]\n"
            "tuple  → (1, 2, 3)\n"
            "dict   → {'key': 'val'}\n"
            "None   → отсутствие значения</pre>\n\n"
            "<b>Операторы:</b>\n"
            "<pre>+  -  *  /   # арифметика\n"
            "//  %  **       # целое деление, остаток, степень\n"
            "==  !=  >  <    # сравнение\n"
            "and  or  not    # логика\n"
            "in   not in     # проверка вхождения</pre>"
        ),
    },
}

# ─────────────────────────────────────────────────────────────
# РАБОТА СО СТАТИСТИКОЙ (JSON-файл)
# ─────────────────────────────────────────────────────────────

def load_stats() -> dict:
    """Загружает статистику из файла. Если файла нет — возвращает пустой словарь."""
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_stats(stats: dict) -> None:
    """Сохраняет статистику в JSON-файл."""
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def update_user_stats(user_id: int, username: str, score: int, total: int, category: str) -> None:
    """Обновляет статистику пользователя после квиза."""
    stats = load_stats()
    uid = str(user_id)

    if uid not in stats:
        stats[uid] = {
            "username": username,
            "total_games": 0,
            "total_correct": 0,
            "total_questions": 0,
            "best_score": 0,
            "history": [],
        }

    u = stats[uid]
    u["username"]        = username  # обновляем имя на актуальное
    u["total_games"]    += 1
    u["total_correct"]  += score
    u["total_questions"] += total
    u["best_score"]      = max(u["best_score"], score)
    u["history"].append({
        "date": str(date.today()),
        "category": category,
        "score": score,
        "total": total,
    })
    # Храним только последние 20 игр
    u["history"] = u["history"][-20:]

    save_stats(stats)


def get_leaderboard() -> list[dict]:
    """Возвращает топ-5 игроков по проценту правильных ответов."""
    stats = load_stats()
    leaders = []
    for uid, u in stats.items():
        if u["total_questions"] > 0:
            pct = u["total_correct"] / u["total_questions"] * 100
            leaders.append({
                "username": u["username"],
                "pct": pct,
                "total_games": u["total_games"],
                "best_score": u["best_score"],
            })
    return sorted(leaders, key=lambda x: x["pct"], reverse=True)[:5]


# ─────────────────────────────────────────────────────────────
# ЕЖЕДНЕВНЫЙ ВОПРОС ДНЯ
# ─────────────────────────────────────────────────────────────

def get_daily_question() -> dict:
    """
    Возвращает вопрос дня. Каждый день — новый вопрос,
    но для одного дня он одинаковый для всех пользователей.
    """
    all_questions = []
    for category, questions in QUESTIONS_DB.items():
        for q in questions:
            all_questions.append({**q, "category": category})

    # Используем порядковый номер дня года как seed для random
    day_seed = date.today().toordinal()
    rng = random.Random(day_seed)
    q = rng.choice(all_questions)
    return q


# ─────────────────────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────────────────────

def kb_main_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Начать квиз",        callback_data="choose_category")
    b.button(text="📚 Шпаргалки",          callback_data="cheatsheets")
    b.button(text="📅 Вопрос дня",         callback_data="daily_question")
    b.button(text="🏆 Таблица лидеров",    callback_data="leaderboard")
    b.button(text="📊 Моя статистика",     callback_data="my_stats")
    b.adjust(1)
    return b.as_markup()


def kb_categories():
    b = InlineKeyboardBuilder()
    for key, meta in CATEGORIES.items():
        b.button(text=meta["label"], callback_data=f"cat:{key}")
    b.button(text="🎲 Случайная категория", callback_data="cat:random")
    b.button(text="🏠 Главное меню",        callback_data="back_to_main")
    b.adjust(2)
    return b.as_markup()


def kb_quiz_options(q_idx: int, questions: list, used_hint: bool = False):
    """Варианты ответа + кнопка подсказки."""
    b = InlineKeyboardBuilder()
    for i, opt in enumerate(questions[q_idx]["options"]):
        b.button(text=opt, callback_data=f"answer:{q_idx}:{i}")
    b.adjust(1)
    if not used_hint:
        b.button(text="💡 Подсказка (-1 очко)", callback_data=f"hint:{q_idx}")
    b.button(text="🚪 Выйти из квиза", callback_data="quit_quiz")
    b.adjust(1)
    return b.as_markup()


def kb_cheatsheets():
    b = InlineKeyboardBuilder()
    for key, sheet in CHEATSHEETS.items():
        b.button(text=sheet["title"], callback_data=f"sheet:{key}")
    b.button(text="🏠 Главное меню", callback_data="back_to_main")
    b.adjust(2)
    return b.as_markup()


def kb_back():
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Главное меню",      callback_data="back_to_main")
    b.button(text="🔄 Пройти снова",      callback_data="choose_category")
    b.adjust(1)
    return b.as_markup()


def kb_daily_answer(q_idx: int, options: list, answered: bool = False):
    """Клавиатура для вопроса дня."""
    b = InlineKeyboardBuilder()
    if not answered:
        for i, opt in enumerate(options):
            b.button(text=opt, callback_data=f"daily_answer:{q_idx}:{i}")
        b.adjust(1)
    b.button(text="🏠 Главное меню", callback_data="back_to_main")
    return b.as_markup()


# ─────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────────────────

def format_question_text(q_idx: int, questions: list, category: str, penalty: int = 0) -> str:
    """Форматирует красивый текст вопроса с прогресс-баром."""
    total    = len(questions)
    q        = questions[q_idx]
    cat_meta = CATEGORIES.get(category, {})
    filled   = "█" * (q_idx) + "░" * (total - q_idx)

    penalty_str = f"  ⚠️ Штраф: -{penalty} очк." if penalty > 0 else ""

    return (
        f"<b>{cat_meta.get('label', 'Квиз')}</b>\n"
        f"Вопрос {q_idx + 1} из {total}{penalty_str}\n"
        f"<code>[{filled}]</code>\n\n"
        f"{q['question']}"
    )


def result_comment(score: int, total: int) -> str:
    r = score / total if total > 0 else 0
    if r == 1.0: return "🏆 Идеально! Ты настоящий знаток Python!"
    if r >= 0.8: return "🎉 Отлично! Очень хороший результат!"
    if r >= 0.6: return "👍 Неплохо! Есть куда расти."
    if r >= 0.4: return "📖 Стоит повторить материал."
    return "💪 Не сдавайся! Читай шпаргалки и пробуй снова."


def medal(pos: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}.")


# ─────────────────────────────────────────────────────────────
# РОУТЕР И ХЕНДЛЕРЫ
# ─────────────────────────────────────────────────────────────

router = Router()


# ── /start ──────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = message.from_user.first_name or "друг"
    logger.info(f"[START] user={message.from_user.id} ({name})")

    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        "┌─────────────────────────┐\n"
        "│  🐍 Python Quiz Bot v2  │\n"
        "└─────────────────────────┘\n\n"
        "Я помогу тебе подготовиться к урокам информатики!\n\n"
        "🎯 <b>Квиз</b> — проверь знания по категориям\n"
        "📚 <b>Шпаргалки</b> — быстро вспомни тему\n"
        "📅 <b>Вопрос дня</b> — один вопрос каждый день\n"
        "🏆 <b>Лидеры</b> — сравни себя с другими\n"
        "📊 <b>Статистика</b> — следи за прогрессом",
        reply_markup=kb_main_menu(),
        parse_mode="HTML",
    )


# ── Главное меню ─────────────────────────────────────────────

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыбери, что хочешь сделать:",
        reply_markup=kb_main_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Выбор категории ──────────────────────────────────────────

@router.callback_query(F.data == "choose_category")
async def choose_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    counts = {k: len(v) for k, v in QUESTIONS_DB.items()}

    text = "🎯 <b>Выбери категорию квиза</b>\n\n"
    for key, meta in CATEGORIES.items():
        text += f"{meta['label']} — {counts[key]} вопросов\n"
    text += "\n🎲 Или выбери случайную категорию!"

    await callback.message.edit_text(text, reply_markup=kb_categories(), parse_mode="HTML")
    await callback.answer()


# ── Старт квиза ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("cat:"))
async def start_quiz(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]

    if category == "random":
        category = random.choice(list(QUESTIONS_DB.keys()))

    questions = QUESTIONS_DB[category].copy()
    random.shuffle(questions)  # перемешиваем вопросы каждый раз

    await state.set_state(QuizStates.in_progress)
    await state.update_data(
        category=category,
        questions=questions,
        current_index=0,
        score=0,
        penalty=0,
        answered=False,
        used_hint=False,
    )

    logger.info(f"[QUIZ] user={callback.from_user.id} category={category}")

    await callback.message.edit_text(
        text=format_question_text(0, questions, category),
        reply_markup=kb_quiz_options(0, questions),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Выход из квиза ───────────────────────────────────────────

@router.callback_query(QuizStates.in_progress, F.data == "quit_quiz")
async def quit_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🚪 Ты вышел из квиза.\n\nВозвращайся когда будешь готов! 💪",
        reply_markup=kb_back(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Подсказка ────────────────────────────────────────────────

@router.callback_query(QuizStates.in_progress, F.data.startswith("hint:"))
async def show_hint(callback: CallbackQuery, state: FSMContext):
    data      = await state.get_data()
    q_idx     = int(callback.data.split(":")[1])
    questions = data["questions"]
    category  = data["category"]
    penalty   = data.get("penalty", 0) + 1

    await state.update_data(penalty=penalty, used_hint=True)

    hint_text = questions[q_idx]["hint"]

    await callback.message.edit_text(
        text=(
            f"{format_question_text(q_idx, questions, category, penalty)}\n\n"
            f"{'─' * 20}\n"
            f"💡 <b>Подсказка:</b> {hint_text}\n"
            f"<i>(−1 очко за подсказку)</i>"
        ),
        reply_markup=kb_quiz_options(q_idx, questions, used_hint=True),
        parse_mode="HTML",
    )
    await callback.answer("💡 Подсказка показана!")


# ── Ответ на вопрос ──────────────────────────────────────────

@router.callback_query(QuizStates.in_progress, F.data.startswith("answer:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if data.get("answered"):
        await callback.answer("Ты уже ответил!", show_alert=False)
        return

    _, q_str, opt_str = callback.data.split(":")
    q_idx     = int(q_str)
    opt_idx   = int(opt_str)
    questions = data["questions"]
    category  = data["category"]
    question  = questions[q_idx]
    penalty   = data.get("penalty", 0)

    is_correct   = (opt_idx == question["correct"])
    score_gained = max(0, 1 - penalty) if is_correct else 0  # 0 если была подсказка и ответ правильный с штрафом
    # Проще: +1 если верно и нет подсказки, +0 если верно но была подсказка (penalty=1), -0 если неверно
    if is_correct and penalty == 0:
        score_gained = 1
    elif is_correct and penalty > 0:
        score_gained = 0  # угадал, но с подсказкой — очков не даём
    else:
        score_gained = 0

    new_score = data["score"] + score_gained

    await state.update_data(score=new_score, answered=True)

    correct_text = question["options"][question["correct"]]
    if is_correct and penalty == 0:
        feedback = f"✅ <b>Правильно! +1 очко</b>\n💡 {question['hint']}"
    elif is_correct and penalty > 0:
        feedback = f"✅ <b>Правильно, но с подсказкой — очков нет</b>\n💡 {question['hint']}"
    else:
        feedback = (
            f"❌ <b>Неправильно.</b>\n"
            f"Правильный ответ: <b>{correct_text}</b>\n"
            f"💡 {question['hint']}"
        )

    logger.info(f"[ANSWER] user={callback.from_user.id} q={q_idx+1} correct={is_correct}")

    next_idx = q_idx + 1
    total    = len(questions)

    await state.update_data(penalty=0, used_hint=False)  # сброс штрафа для следующего вопроса

    if next_idx < total:
        await state.update_data(current_index=next_idx, answered=False)
        await callback.message.edit_text(
            text=(
                f"{format_question_text(q_idx, questions, category)}\n\n"
                f"{'─' * 22}\n"
                f"{feedback}\n\n"
                f"{'─' * 22}\n"
                f"{format_question_text(next_idx, questions, category)}"
            ),
            reply_markup=kb_quiz_options(next_idx, questions),
            parse_mode="HTML",
        )
        await callback.answer("✅ Верно!" if is_correct else "❌ Мимо!")
    else:
        # ── Финал ──
        username = callback.from_user.first_name or "Игрок"
        update_user_stats(callback.from_user.id, username, new_score, total, category)

        stars = "⭐" * new_score + "☆" * (total - new_score)
        cat_label = CATEGORIES[category]["label"]

        # Загружаем историю для FSM-статистики
        fsm_data    = await state.get_data()
        history     = fsm_data.get("history", [])
        history.append({"score": new_score, "total": total, "category": category})
        await state.clear()
        await state.update_data(history=history)

        logger.info(f"[FINISH] user={callback.from_user.id} score={new_score}/{total}")

        await callback.message.edit_text(
            text=(
                f"🏁 <b>Квиз завершён!</b>\n\n"
                f"📂 Категория: {cat_label}\n\n"
                f"{format_question_text(q_idx, questions, category)}\n\n"
                f"{'─' * 22}\n"
                f"{feedback}\n\n"
                f"{'═' * 22}\n"
                f"🎯 Результат: <b>{new_score} из {total}</b>\n"
                f"{stars}\n\n"
                f"{result_comment(new_score, total)}\n\n"
                f"<i>Статистика сохранена 💾</i>"
            ),
            reply_markup=kb_back(),
            parse_mode="HTML",
        )
        await callback.answer()


# ── Защита от текста во время квиза ─────────────────────────

@router.message(QuizStates.in_progress)
async def quiz_guard(message: Message):
    await message.answer(
        "⚠️ Во время квиза нажимай на кнопки с вариантами ответа!\n"
        "Вернись к вопросу выше 👆"
    )


# ── Шпаргалки ────────────────────────────────────────────────

@router.callback_query(F.data == "cheatsheets")
async def show_cheatsheets_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 <b>Шпаргалки по Python</b>\n\nВыбери тему:",
        reply_markup=kb_cheatsheets(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sheet:"))
async def show_cheatsheet(callback: CallbackQuery):
    key   = callback.data.split(":")[1]
    sheet = CHEATSHEETS.get(key)
    if not sheet:
        await callback.answer("Не найдено!", show_alert=True)
        return
    await callback.message.edit_text(
        f"<b>{sheet['title']}</b>\n\n{sheet['text']}",
        reply_markup=kb_cheatsheets(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Вопрос дня ───────────────────────────────────────────────

@router.callback_query(F.data == "daily_question")
async def daily_question(callback: CallbackQuery, state: FSMContext):
    q         = get_daily_question()
    today_str = str(date.today())

    # Проверяем, отвечал ли уже сегодня
    data           = await state.get_data()
    daily_answered = data.get("daily_date") == today_str

    cat_label = CATEGORIES.get(q["category"], {}).get("label", "")
    text = (
        f"📅 <b>Вопрос дня — {today_str}</b>\n"
        f"Тема: {cat_label}\n\n"
        f"{q['question']}"
    )

    if daily_answered:
        correct_text = q["options"][q["correct"]]
        text += f"\n\n{'─'*20}\n✅ Ты уже отвечал сегодня!\nПравильный ответ: <b>{correct_text}</b>"
        await callback.message.edit_text(
            text,
            reply_markup=kb_daily_answer(0, q["options"], answered=True),
            parse_mode="HTML",
        )
    else:
        # Сохраняем вопрос дня в state для обработки ответа
        await state.update_data(daily_q=q)
        await callback.message.edit_text(
            text,
            reply_markup=kb_daily_answer(0, q["options"]),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("daily_answer:"))
async def handle_daily_answer(callback: CallbackQuery, state: FSMContext):
    data       = await state.get_data()
    today_str  = str(date.today())
    q          = data.get("daily_q") or get_daily_question()
    opt_idx    = int(callback.data.split(":")[2])
    is_correct = opt_idx == q["correct"]
    correct_text = q["options"][q["correct"]]

    await state.update_data(daily_date=today_str)

    feedback = (
        f"✅ <b>Правильно!</b>\n💡 {q['hint']}"
        if is_correct else
        f"❌ <b>Неверно.</b>\nПравильный ответ: <b>{correct_text}</b>\n💡 {q['hint']}"
    )

    cat_label = CATEGORIES.get(q["category"], {}).get("label", "")
    await callback.message.edit_text(
        f"📅 <b>Вопрос дня — {today_str}</b>\n"
        f"Тема: {cat_label}\n\n"
        f"{q['question']}\n\n"
        f"{'─'*20}\n{feedback}",
        reply_markup=kb_daily_answer(0, q["options"], answered=True),
        parse_mode="HTML",
    )
    await callback.answer("✅ Верно!" if is_correct else "❌ Мимо!")


# ── Таблица лидеров ──────────────────────────────────────────

@router.callback_query(F.data == "leaderboard")
async def show_leaderboard(callback: CallbackQuery):
    leaders = get_leaderboard()

    if not leaders:
        await callback.message.edit_text(
            "🏆 <b>Таблица лидеров</b>\n\n"
            "Пока никто не проходил квиз.\nБудь первым! 🎯",
            reply_markup=kb_back(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = "🏆 <b>Таблица лидеров</b>\n\n"
    for i, leader in enumerate(leaders, 1):
        text += (
            f"{medal(i)} <b>{leader['username']}</b>\n"
            f"   📈 Точность: {leader['pct']:.0f}%  "
            f"🎮 Игр: {leader['total_games']}\n"
        )

    text += "\n<i>Рейтинг считается по % правильных ответов</i>"

    await callback.message.edit_text(text, reply_markup=kb_back(), parse_mode="HTML")
    await callback.answer()


# ── Моя статистика ───────────────────────────────────────────

@router.callback_query(F.data == "my_stats")
async def show_stats(callback: CallbackQuery, state: FSMContext):
    stats = load_stats()
    uid   = str(callback.from_user.id)

    if uid not in stats or stats[uid]["total_games"] == 0:
        await callback.message.edit_text(
            "📊 <b>Твоя статистика</b>\n\n"
            "Ты ещё не проходил квиз.\nНажми «Начать квиз»! 🎯",
            reply_markup=kb_main_menu(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    u        = stats[uid]
    games    = u["total_games"]
    correct  = u["total_correct"]
    total_q  = u["total_questions"]
    best     = u["best_score"]
    avg_pct  = correct / total_q * 100 if total_q > 0 else 0

    # Последние 5 игр
    last5 = u["history"][-5:]
    hist_lines = []
    for h in reversed(last5):
        cat = CATEGORIES.get(h["category"], {}).get("emoji", "🎯")
        stars = "⭐" * h["score"] + "☆" * (h["total"] - h["score"])
        hist_lines.append(f"  {cat} {h['score']}/{h['total']} {stars} <i>{h['date']}</i>")

    await callback.message.edit_text(
        f"📊 <b>Твоя статистика</b>\n\n"
        f"🎮 Игр сыграно: <b>{games}</b>\n"
        f"✅ Всего верных: <b>{correct}</b> из <b>{total_q}</b>\n"
        f"📈 Средний результат: <b>{avg_pct:.0f}%</b>\n"
        f"🏆 Лучший счёт: <b>{best}</b>\n\n"
        f"<b>Последние игры:</b>\n" + "\n".join(hist_lines),
        reply_markup=kb_main_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────────────────────

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Python Quiz Bot v2.0 запущен! Ctrl+C для остановки.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен.")


if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
