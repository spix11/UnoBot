"""
╔══════════════════════════════════════════════════════════════╗
║        🐍 PYTHON QUIZ BOT v5.0 — СУПЕР БОТ                  ║
║                                                              ║
║  Новое в v5.0:                                               ║
║  👥 Реферальная система (+бонусы за друзей)                  ║
║  🔔 Умные напоминания (бот пишет сам)                        ║
║  📱 Мини-игры (найди ошибку, угадай вывод)                   ║
║  🏟 Еженедельные турниры                                     ║
║  🎓 Мини-курсы по Python (структурированные уроки)           ║
║  🌍 Английский язык интерфейса                               ║
║  📊 Графики прогресса (текстовые)                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    LabeledPrice, PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ─────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ
# ─────────────────────────────────────────────────────────────

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise SystemExit("❌ Укажи BOT_TOKEN в .env файле")

STATS_FILE      = Path("stats.json")
TOURNAMENT_FILE = Path("tournament.json")

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
# FSM
# ─────────────────────────────────────────────────────────────

class QuizStates(StatesGroup):
    in_progress  = State()
    study_mode   = State()
    mini_game    = State()
    course_study = State()

# ─────────────────────────────────────────────────────────────
# ЛОКАЛИЗАЦИЯ (RU / EN)
# ─────────────────────────────────────────────────────────────

STRINGS = {
    "ru": {
        "welcome": "👋 Привет, <b>{name}</b>!",
        "menu": "🏠 Главное меню",
        "quiz": "🎯 Начать квиз",
        "study": "📝 Режим обучения",
        "daily": "📅 Вопрос дня",
        "shop": "🛒 Магазин",
        "leaderboard": "🏆 Лидеры",
        "profile": "👤 Профиль",
        "achievements": "🎖 Достижения",
        "minigames": "📱 Мини-игры",
        "courses": "🎓 Курсы",
        "tournament": "🏟 Турнир",
        "referral": "👥 Пригласить друга",
        "progress": "📊 Мой прогресс",
        "lang": "🌍 English",
        "correct": "✅ Правильно!",
        "wrong": "❌ Неверно.",
        "back": "🏠 Меню",
        "level": "Уровень",
        "xp": "XP",
        "streak": "Серия",
        "games": "Игр",
    },
    "en": {
        "welcome": "👋 Hello, <b>{name}</b>!",
        "menu": "🏠 Main menu",
        "quiz": "🎯 Start quiz",
        "study": "📝 Study mode",
        "daily": "📅 Daily question",
        "shop": "🛒 Shop",
        "leaderboard": "🏆 Leaderboard",
        "profile": "👤 Profile",
        "achievements": "🎖 Achievements",
        "minigames": "📱 Mini-games",
        "courses": "🎓 Courses",
        "tournament": "🏟 Tournament",
        "referral": "👥 Invite friend",
        "progress": "📊 My progress",
        "lang": "🌍 Русский",
        "correct": "✅ Correct!",
        "wrong": "❌ Wrong.",
        "back": "🏠 Menu",
        "level": "Level",
        "xp": "XP",
        "streak": "Streak",
        "games": "Games",
    },
}

def t(u: dict, key: str, **kwargs) -> str:
    lang = u.get("lang", "ru")
    s    = STRINGS.get(lang, STRINGS["ru"]).get(key, key)
    return s.format(**kwargs) if kwargs else s

# ─────────────────────────────────────────────────────────────
# СИСТЕМА УРОВНЕЙ
# ─────────────────────────────────────────────────────────────

LEVELS = [
    (0,    "🥚 Новичок",       "🥚 Newbie"),
    (50,   "🐣 Начинающий",    "🐣 Beginner"),
    (150,  "📖 Ученик",        "📖 Student"),
    (300,  "🔍 Исследователь", "🔍 Explorer"),
    (500,  "⚡ Знаток",        "⚡ Expert"),
    (800,  "🧠 Эксперт",       "🧠 Master"),
    (1200, "🏆 Мастер",        "🏆 Champion"),
    (2000, "🌟 Легенда",       "🌟 Legend"),
]

def get_level(xp: int, lang: str = "ru") -> tuple[int, str]:
    lv, name = 0, LEVELS[0][1 if lang == "ru" else 2]
    for i, row in enumerate(LEVELS):
        if xp >= row[0]:
            lv   = i
            name = row[1 if lang == "ru" else 2]
    return lv, name

def xp_bar(xp: int, w: int = 10) -> str:
    cur_req, next_req = 0, LEVELS[-1][0]
    for i, (req, *_) in enumerate(LEVELS):
        if xp >= req:
            cur_req  = req
            next_req = LEVELS[i+1][0] if i+1 < len(LEVELS) else req
    if next_req == cur_req:
        return "█" * w
    filled = int((xp - cur_req) / (next_req - cur_req) * w)
    return "█" * filled + "░" * (w - filled)

# ─────────────────────────────────────────────────────────────
# ДОСТИЖЕНИЯ
# ─────────────────────────────────────────────────────────────

ACHIEVEMENTS = {
    "first_quiz":     {"icon": "🎯", "name": "Первый шаг",       "name_en": "First step"},
    "perfect_5":      {"icon": "⭐", "name": "Идеал",             "name_en": "Perfect"},
    "streak_3":       {"icon": "🔥", "name": "3 дня подряд",      "name_en": "3-day streak"},
    "streak_7":       {"icon": "🏅", "name": "Неделя",            "name_en": "Weekly streak"},
    "all_categories": {"icon": "🗺️", "name": "Путешественник",   "name_en": "Explorer"},
    "level_5":        {"icon": "⚡", "name": "Знаток",            "name_en": "Expert"},
    "hundred_xp":     {"icon": "💯", "name": "100 XP",            "name_en": "100 XP"},
    "no_hints":       {"icon": "🧠", "name": "Своим умом",        "name_en": "No hints"},
    "vip_member":     {"icon": "💎", "name": "VIP",               "name_en": "VIP"},
    "referral_1":     {"icon": "👥", "name": "Первый реферал",    "name_en": "First referral"},
    "referral_5":     {"icon": "🤝", "name": "Популярный",        "name_en": "Popular"},
    "tournament_win": {"icon": "🏆", "name": "Победитель",        "name_en": "Champion"},
    "course_done":    {"icon": "🎓", "name": "Студент",           "name_en": "Graduate"},
    "minigame_10":    {"icon": "🕹️", "name": "Геймер",           "name_en": "Gamer"},
}

def check_achievements(u: dict) -> list[str]:
    earned  = set(u.get("achievements", []))
    new_ach = []
    def unlock(k):
        if k not in earned:
            new_ach.append(k)
            earned.add(k)
    if u.get("total_games", 0) >= 1:           unlock("first_quiz")
    if u.get("perfect_games", 0) >= 1:         unlock("perfect_5")
    if u.get("streak", 0) >= 3:                unlock("streak_3")
    if u.get("streak", 0) >= 7:                unlock("streak_7")
    if len(u.get("cats_played", [])) >= 6:     unlock("all_categories")
    if get_level(u.get("xp", 0))[0] >= 5:     unlock("level_5")
    if u.get("xp", 0) >= 100:                  unlock("hundred_xp")
    if u.get("no_hint_games", 0) >= 1:         unlock("no_hints")
    if u.get("is_premium", False):             unlock("vip_member")
    if u.get("referral_count", 0) >= 1:        unlock("referral_1")
    if u.get("referral_count", 0) >= 5:        unlock("referral_5")
    if u.get("tournament_wins", 0) >= 1:       unlock("tournament_win")
    if u.get("courses_done", 0) >= 1:          unlock("course_done")
    if u.get("minigames_played", 0) >= 10:     unlock("minigame_10")
    u["achievements"] = list(earned)
    return new_ach

# ─────────────────────────────────────────────────────────────
# МИНИ-ИГРЫ
# ─────────────────────────────────────────────────────────────

MINIGAMES_FIND_BUG = [
    {
        "code": "lst = [1, 2, 3]\nprint(lst[3])",
        "question": "🐛 Найди ошибку в коде:",
        "options": ["Ошибка в lst[3] — выход за пределы списка", "lst не определён", "print написан неверно", "Ошибок нет"],
        "correct": 0,
        "explanation": "Список из 3 элементов имеет индексы 0, 1, 2. Индекс 3 вызывает IndexError!",
    },
    {
        "code": "x = 5\nif x = 5:\n    print('yes')",
        "question": "🐛 Найди ошибку в коде:",
        "options": ["= вместо == в условии", "Отступ неверный", "print написан неверно", "Ошибок нет"],
        "correct": 0,
        "explanation": "В условии if нужно == (сравнение), а не = (присваивание)!",
    },
    {
        "code": "def greet(name)\n    print(f'Hello {name}')",
        "question": "🐛 Найди ошибку в коде:",
        "options": ["Нет двоеточия после def", "f-строка написана неверно", "Нет return", "Ошибок нет"],
        "correct": 0,
        "explanation": "После объявления функции def нужно двоеточие: def greet(name):",
    },
    {
        "code": "numbers = [1, 2, 3]\nfor num in numbers\n    print(num)",
        "question": "🐛 Найди ошибку в коде:",
        "options": ["Нет двоеточия после for", "numbers написан неверно", "print написан неверно", "Ошибок нет"],
        "correct": 0,
        "explanation": "После for ... in ... нужно двоеточие!",
    },
    {
        "code": "d = {'a': 1, 'b': 2}\nprint(d['c'])",
        "question": "🐛 Найди ошибку в коде:",
        "options": ["Ключ 'c' не существует в словаре", "Словарь создан неверно", "print написан неверно", "Ошибок нет"],
        "correct": 0,
        "explanation": "Ключа 'c' нет в словаре — будет KeyError! Используй d.get('c') для безопасного доступа.",
    },
]

MINIGAMES_GUESS_OUTPUT = [
    {
        "code": "print(2 ** 8)",
        "question": "💻 Что выведет код?",
        "options": ["16", "256", "64", "128"],
        "correct": 1,
        "explanation": "2 ** 8 = 2×2×2×2×2×2×2×2 = 256",
    },
    {
        "code": "lst = [1, 2, 3, 4, 5]\nprint(lst[-1])",
        "question": "💻 Что выведет код?",
        "options": ["1", "4", "5", "Error"],
        "correct": 2,
        "explanation": "Индекс -1 возвращает последний элемент списка.",
    },
    {
        "code": "print('hello' * 3)",
        "question": "💻 Что выведет код?",
        "options": ["hello3", "hellohellohello", "hello hello hello", "Error"],
        "correct": 1,
        "explanation": "Умножение строки на число повторяет её N раз.",
    },
    {
        "code": "x = 10\nx += 5\nx *= 2\nprint(x)",
        "question": "💻 Что выведет код?",
        "options": ["25", "30", "20", "15"],
        "correct": 1,
        "explanation": "x=10, x+=5 → x=15, x*=2 → x=30",
    },
    {
        "code": "print(bool('') == bool(0))",
        "question": "💻 Что выведет код?",
        "options": ["False", "True", "Error", "None"],
        "correct": 1,
        "explanation": "bool('') = False, bool(0) = False, False == False → True",
    },
    {
        "code": "lst = [3, 1, 4, 1, 5]\nprint(sorted(lst)[-1])",
        "question": "💻 Что выведет код?",
        "options": ["3", "4", "5", "1"],
        "correct": 2,
        "explanation": "sorted([3,1,4,1,5]) = [1,1,3,4,5], последний элемент = 5",
    },
]

# ─────────────────────────────────────────────────────────────
# МИНИ-КУРСЫ
# ─────────────────────────────────────────────────────────────

COURSES = {
    "python_basics": {
        "title": "🐍 Основы Python",
        "title_en": "🐍 Python Basics",
        "desc": "С нуля до первой программы",
        "lessons": [
            {
                "title": "Урок 1: Переменные",
                "content": (
                    "📖 <b>Переменные</b> — это контейнеры для хранения данных.\n\n"
                    "<pre>name = 'Аня'     # строка\n"
                    "age  = 16        # число\n"
                    "pi   = 3.14      # дробное\n"
                    "ok   = True      # булево</pre>\n\n"
                    "Python сам определяет тип переменной!\n"
                    "Имя переменной: буквы, цифры, _, но не начинается с цифры."
                ),
                "question": "Как правильно создать переменную?",
                "options": ["int x = 5", "x = 5", "var x = 5", "x := 5"],
                "correct": 1,
            },
            {
                "title": "Урок 2: Типы данных",
                "content": (
                    "📖 <b>Основные типы данных:</b>\n\n"
                    "<pre>type(42)       # int\n"
                    "type(3.14)     # float\n"
                    "type('hello')  # str\n"
                    "type(True)     # bool\n"
                    "type(None)     # NoneType</pre>\n\n"
                    "<b>Преобразование типов:</b>\n"
                    "<pre>int('42')    # → 42\n"
                    "str(42)      # → '42'\n"
                    "float('3.14')# → 3.14</pre>"
                ),
                "question": "Что вернёт type('hello')?",
                "options": ["int", "str", "text", "string"],
                "correct": 1,
            },
            {
                "title": "Урок 3: Условия",
                "content": (
                    "📖 <b>Условный оператор if:</b>\n\n"
                    "<pre>age = 18\n\n"
                    "if age >= 18:\n"
                    "    print('Взрослый')\n"
                    "elif age >= 14:\n"
                    "    print('Подросток')\n"
                    "else:\n"
                    "    print('Ребёнок')</pre>\n\n"
                    "<b>Операторы сравнения:</b>\n"
                    "<pre>==  !=  >  <  >=  <=</pre>"
                ),
                "question": "Что выведет код? age=15; if age>=18: print('A') else: print('B')",
                "options": ["A", "B", "15", "Error"],
                "correct": 1,
            },
            {
                "title": "Урок 4: Циклы",
                "content": (
                    "📖 <b>Цикл for:</b>\n"
                    "<pre>for i in range(3):\n"
                    "    print(i)  # 0 1 2</pre>\n\n"
                    "<b>Цикл while:</b>\n"
                    "<pre>n = 5\nwhile n > 0:\n"
                    "    print(n)\n"
                    "    n -= 1</pre>\n\n"
                    "<b>break и continue:</b>\n"
                    "<pre>for i in range(10):\n"
                    "    if i == 5: break    # стоп\n"
                    "    if i % 2: continue # пропуск</pre>"
                ),
                "question": "Сколько раз выполнится: for i in range(3): pass",
                "options": ["2", "3", "4", "0"],
                "correct": 1,
            },
            {
                "title": "Урок 5: Функции",
                "content": (
                    "📖 <b>Функции</b> — блоки кода многократного использования:\n\n"
                    "<pre>def greet(name, msg='Привет'):\n"
                    "    return f'{msg}, {name}!'\n\n"
                    "greet('Аня')        # Привет, Аня!\n"
                    "greet('Вася','Хэй') # Хэй, Вася!</pre>\n\n"
                    "<b>Lambda — функция в одну строку:</b>\n"
                    "<pre>sq = lambda x: x**2\n"
                    "sq(5)  # 25</pre>"
                ),
                "question": "Что вернёт функция без return?",
                "options": ["0", "''", "None", "Error"],
                "correct": 2,
            },
        ],
    },
    "data_structures": {
        "title": "📦 Структуры данных",
        "title_en": "📦 Data Structures",
        "desc": "Списки, словари, кортежи",
        "lessons": [
            {
                "title": "Урок 1: Списки",
                "content": (
                    "📖 <b>Список (list)</b> — упорядоченная изменяемая коллекция:\n\n"
                    "<pre>lst = [1, 2, 3, 'hello', True]\n\n"
                    "lst[0]        # 1\n"
                    "lst[-1]       # True\n"
                    "lst[1:3]      # [2, 3]\n"
                    "len(lst)      # 5\n\n"
                    "lst.append(4) # добавить\n"
                    "lst.pop()     # удалить последний\n"
                    "lst.sort()    # сортировать</pre>"
                ),
                "question": "Что вернёт [1,2,3][-1]?",
                "options": ["1", "2", "3", "Error"],
                "correct": 2,
            },
            {
                "title": "Урок 2: Словари",
                "content": (
                    "📖 <b>Словарь (dict)</b> — пары ключ:значение:\n\n"
                    "<pre>d = {'name': 'Python', 'ver': 3}\n\n"
                    "d['name']         # 'Python'\n"
                    "d.get('x', 0)     # 0 (нет ключа)\n"
                    "d['new'] = 42     # добавить\n"
                    "del d['ver']      # удалить\n\n"
                    "for k, v in d.items():\n"
                    "    print(k, v)</pre>"
                ),
                "question": "Как безопасно получить значение из словаря?",
                "options": ["d['key']", "d.get('key')", "d.fetch('key')", "d.find('key')"],
                "correct": 1,
            },
            {
                "title": "Урок 3: Кортежи и множества",
                "content": (
                    "📖 <b>Кортеж (tuple)</b> — неизменяемый список:\n"
                    "<pre>t = (1, 2, 3)\nt[0]  # 1\n# t[0] = 5  # ошибка!</pre>\n\n"
                    "<b>Множество (set)</b> — уникальные элементы:\n"
                    "<pre>s = {1, 2, 2, 3, 3}\nprint(s)  # {1, 2, 3}\n\n"
                    "s.add(4)\ns.remove(1)\n1 in s  # False</pre>"
                ),
                "question": "Что выведет: print({1,2,2,3,3})?",
                "options": ["{1,2,2,3,3}", "{1,2,3}", "[1,2,3]", "Error"],
                "correct": 1,
            },
        ],
    },
}

# ─────────────────────────────────────────────────────────────
# ВОПРОСЫ ДЛЯ КВИЗА
# ─────────────────────────────────────────────────────────────

QUESTIONS_DB: dict[str, list[dict]] = {
    "basics": [
        {"difficulty": "easy",
         "question": "🐍 Какой тип у <code>[]</code>?",
         "options": ["tuple","list","dict","set"], "correct": 1,
         "hint": "[] — литерал списка.",
         "explanation": "<b>[]</b> — это <b>list</b>.\n<pre>type([]) → list</pre>"},
        {"difficulty": "easy",
         "question": "🐍 Результат?\n\n<code>print(10 // 3)</code>",
         "options": ["3.33","3","4","1"], "correct": 1,
         "hint": "// — целочисленное деление.",
         "explanation": "<b>//</b> отбрасывает остаток:\n<pre>10 // 3 = 3</pre>"},
        {"difficulty": "medium",
         "question": "🐍 Что такое <code>None</code>?",
         "options": ["Ноль","Пустая строка","Отсутствие значения","False"], "correct": 2,
         "hint": "None — singleton.",
         "explanation": "<b>None</b> — специальный объект:\n<pre>bool(None) → False</pre>"},
        {"difficulty": "hard",
         "question": "🐍 Что выведет?\n\n<code>print(bool([]), bool([0]))</code>",
         "options": ["True True","False False","False True","True False"], "correct": 2,
         "hint": "Пустой список — False, список с элементом — True.",
         "explanation": "<pre>bool([]) → False\nbool([0]) → True (список непустой!)</pre>"},
    ],
    "loops": [
        {"difficulty": "easy",
         "question": "🔁 Что делает <code>break</code>?",
         "options": ["Пропуск итерации","Прерывает цикл","Перезапуск","Ошибка"], "correct": 1,
         "hint": "break — выход из цикла.",
         "explanation": "<b>break</b> — немедленный выход."},
        {"difficulty": "medium",
         "question": "🔁 Что выведет?\n\n<code>for i in range(2,10,3): print(i,end=' ')</code>",
         "options": ["2 5 8","2 4 6 8","3 6 9","2 3 4"], "correct": 0,
         "hint": "range(2,10,3) → 2,5,8",
         "explanation": "start=2, stop=10, step=3 → 2, 5, 8"},
        {"difficulty": "hard",
         "question": "🔁 Что выведет?\n\n<code>for i in range(3):\n    for j in range(3):\n        if i==j: print(i,end=' ')</code>",
         "options": ["0 1 2","0 0 1 1 2 2","0 1 2 3","Error"], "correct": 0,
         "hint": "Печатаем только когда i == j.",
         "explanation": "При i==j: 0,1,2"},
    ],
    "lists": [
        {"difficulty": "easy",
         "question": "📋 Добавить в конец списка?",
         "options": ["add()","push()","append()","insert()"], "correct": 2,
         "hint": "append — добавить.",
         "explanation": "<b>append(x)</b> — в конец."},
        {"difficulty": "medium",
         "question": "📋 Что вернёт?\n\n<code>'Python'[::-1]</code>",
         "options": ["'Python'","'nohtyP'","Error","list"], "correct": 1,
         "hint": "Шаг -1 разворачивает.",
         "explanation": "[::-1] — обратный порядок."},
        {"difficulty": "hard",
         "question": "📋 Что в a?\n\n<code>a=[1,2,3]\nb=a\nb.append(4)\nprint(a)</code>",
         "options": ["[1,2,3]","[1,2,3,4]","[4]","Error"], "correct": 1,
         "hint": "b=a — ссылка, не копия!",
         "explanation": "b=a не копирует! Используй a.copy()"},
    ],
    "functions": [
        {"difficulty": "easy",
         "question": "⚙️ Функция без return возвращает?",
         "options": ["0","''","False","None"], "correct": 3,
         "hint": "Специальное значение «ничего».",
         "explanation": "Без return → None"},
        {"difficulty": "medium",
         "question": "⚙️ Что делает <code>*args</code>?",
         "options": ["Умножает","Любое кол-во позиц. арг.","Именованные арг.","Ссылка"], "correct": 1,
         "hint": "*args → кортеж аргументов.",
         "explanation": "<b>*args</b> — любое кол-во аргументов."},
    ],
    "dicts": [
        {"difficulty": "easy",
         "question": "📦 Безопасный доступ к ключу?",
         "options": ["d['key']","d.get('key')","d.find('key')","d.fetch('key')"], "correct": 1,
         "hint": "get() не бросает KeyError.",
         "explanation": "get(key, default) — безопасно."},
        {"difficulty": "medium",
         "question": "📦 Что вернёт <code>d.items()</code>?",
         "options": ["Ключи","Значения","Пары (ключ,знач.)","Длину"], "correct": 2,
         "hint": "items — и ключи, и значения.",
         "explanation": "d.items() → пары (ключ, значение)."},
    ],
    "strings": [
        {"difficulty": "easy",
         "question": "🔤 Что делает <code>upper()</code>?",
         "options": ["Удаляет пробелы","Верхний регистр","Первая заглавная","Разворот"], "correct": 1,
         "hint": "upper — верхний регистр.",
         "explanation": "'hello'.upper() → 'HELLO'"},
        {"difficulty": "medium",
         "question": "🔤 Что выведет?\n\n<code>'hello world'.split()</code>",
         "options": ["['hello world']","['hello','world']","('hello','world')","Error"], "correct": 1,
         "hint": "split() делит по пробелам.",
         "explanation": "split() → список слов."},
    ],
}

CATEGORIES = {
    "basics":    {"label": "🐍 Основы",    "label_en": "🐍 Basics",    "emoji": "🐍"},
    "loops":     {"label": "🔁 Циклы",     "label_en": "🔁 Loops",     "emoji": "🔁"},
    "lists":     {"label": "📋 Списки",    "label_en": "📋 Lists",     "emoji": "📋"},
    "functions": {"label": "⚙️ Функции",   "label_en": "⚙️ Functions", "emoji": "⚙️"},
    "dicts":     {"label": "📦 Словари",   "label_en": "📦 Dicts",     "emoji": "📦"},
    "strings":   {"label": "🔤 Строки",    "label_en": "🔤 Strings",   "emoji": "🔤"},
}

DIFFICULTY_CONFIG = {
    "easy":   {"label": "🟢 Лёгкий",  "label_en": "🟢 Easy",   "xp": 5},
    "medium": {"label": "🟡 Средний", "label_en": "🟡 Medium",  "xp": 10},
    "hard":   {"label": "🔴 Сложный", "label_en": "🔴 Hard",    "xp": 20},
}

SHOP_ITEMS = {
    "premium_30": {"title": "👑 Premium 30 дней", "description": "VIP статус, безлимит подсказок", "stars": 100, "payload": "premium_30"},
    "hints_10":   {"title": "💡 10 подсказок",    "description": "Пакет подсказок без штрафа",    "stars": 25,  "payload": "hints_10"},
    "xp_boost":   {"title": "⚡ XP x2 на 7 дней", "description": "Двойной опыт на неделю",        "stars": 50,  "payload": "xp_boost"},
    "hard_access":{"title": "🔴 Hard вопросы",    "description": "Доступ к сложным вопросам",     "stars": 75,  "payload": "hard_access"},
}

# ─────────────────────────────────────────────────────────────
# СТАТИСТИКА
# ─────────────────────────────────────────────────────────────

def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_stats(stats: dict):
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

def get_user(stats: dict, uid: int, name: str) -> dict:
    key = str(uid)
    if key not in stats:
        stats[key] = {
            "username": name, "xp": 0, "total_games": 0,
            "total_correct": 0, "total_questions": 0,
            "best_score": 0, "perfect_games": 0, "no_hint_games": 0,
            "streak": 0, "last_play": "", "cats_played": [],
            "achievements": [], "daily_date": "", "daily_count": 0,
            "history": [], "total_purchases": 0, "total_stars_spent": 0,
            "is_premium": False, "premium_until": "",
            "hints_left": 3, "xp_boost_until": "", "hard_unlocked": False,
            "lang": "ru",
            # Новые поля v5.0
            "referral_code": str(uid)[-6:],
            "referral_count": 0,
            "referred_by": None,
            "tournament_wins": 0,
            "tournament_score": 0,
            "courses_done": 0,
            "courses_progress": {},
            "minigames_played": 0,
            "minigames_correct": 0,
            "last_reminder": "",
            "notifications": True,
            "weekly_xp": 0,
            "weekly_start": str(date.today()),
        }
    stats[key]["username"] = name
    return stats[key]

def is_premium(u: dict) -> bool:
    if not u.get("is_premium"):
        return False
    until = u.get("premium_until", "")
    return bool(until) and datetime.fromisoformat(until) > datetime.now()

def is_xp_boost(u: dict) -> bool:
    until = u.get("xp_boost_until", "")
    return bool(until) and datetime.fromisoformat(until) > datetime.now()

def update_streak(u: dict) -> int:
    today     = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    last      = u.get("last_play", "")
    bonus     = 0
    if last == today:
        pass
    elif last == yesterday:
        u["streak"] = u.get("streak", 0) + 1
        if u["streak"] > 1:
            bonus = 10
    else:
        u["streak"] = 1
    u["last_play"] = today
    return bonus

def apply_purchase(u: dict, payload: str) -> str:
    if payload == "premium_30":
        until = datetime.now() + timedelta(days=30)
        u["is_premium"]    = True
        u["premium_until"] = until.isoformat()
        u["hints_left"]    = 9999
        return f"👑 Premium до {until.strftime('%d.%m.%Y')}!"
    elif payload == "hints_10":
        u["hints_left"] = u.get("hints_left", 0) + 10
        return "💡 +10 подсказок!"
    elif payload == "xp_boost":
        until = datetime.now() + timedelta(days=7)
        u["xp_boost_until"] = until.isoformat()
        return f"⚡ XP x2 до {until.strftime('%d.%m.%Y')}!"
    elif payload == "hard_access":
        u["hard_unlocked"] = True
        return "🔴 Hard вопросы разблокированы!"
    return "✅ Готово!"

# ─────────────────────────────────────────────────────────────
# ТУРНИР
# ─────────────────────────────────────────────────────────────

def load_tournament() -> dict:
    if TOURNAMENT_FILE.exists():
        try:
            return json.loads(TOURNAMENT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Новый турнир
    monday = date.today() - timedelta(days=date.today().weekday())
    return {
        "week_start": str(monday),
        "scores": {},
        "last_winner": None,
    }

def save_tournament(t: dict):
    TOURNAMENT_FILE.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")

def get_tournament_week() -> str:
    monday = date.today() - timedelta(days=date.today().weekday())
    return str(monday)

def update_tournament_score(uid: int, username: str, xp_earned: int):
    t   = load_tournament()
    now = get_tournament_week()
    # Новая неделя — сбрасываем
    if t.get("week_start") != now:
        # Определяем победителя прошлой недели
        if t["scores"]:
            winner_id = max(t["scores"], key=lambda x: t["scores"][x]["xp"])
            t["last_winner"] = t["scores"][winner_id]["username"]
        t["week_start"] = now
        t["scores"]     = {}
    uid_str = str(uid)
    if uid_str not in t["scores"]:
        t["scores"][uid_str] = {"username": username, "xp": 0}
    t["scores"][uid_str]["xp"]       += xp_earned
    t["scores"][uid_str]["username"]  = username
    save_tournament(t)

def get_tournament_top(n: int = 5) -> list[dict]:
    t   = load_tournament()
    now = get_tournament_week()
    if t.get("week_start") != now:
        return []
    scores = t.get("scores", {})
    return sorted(
        [{"uid": k, **v} for k, v in scores.items()],
        key=lambda x: x["xp"], reverse=True
    )[:n]

# ─────────────────────────────────────────────────────────────
# ГРАФИКИ ПРОГРЕССА
# ─────────────────────────────────────────────────────────────

def build_progress_chart(u: dict, lang: str = "ru") -> str:
    history = u.get("history", [])
    if not history:
        return "📊 Нет данных для графика." if lang == "ru" else "📊 No data for chart."

    # Последние 7 игр
    last7 = history[-7:]

    lines  = []
    max_xp = max((h.get("xp", 0) for h in last7), default=1)

    lines.append("📊 <b>Прогресс (последние игры):</b>\n")
    for i, h in enumerate(last7, 1):
        xp   = h.get("xp", 0)
        sc   = h.get("score", 0)
        tot  = h.get("total", 1)
        cat  = CATEGORIES.get(h.get("cat", ""), {}).get("emoji", "🎯")
        bar_len = int(xp / max_xp * 10) if max_xp > 0 else 0
        bar  = "█" * bar_len + "░" * (10 - bar_len)
        pct  = int(sc / tot * 100)
        lines.append(f"{i}. {cat} <code>[{bar}]</code> {xp} XP ({pct}%)")

    # Недельная статистика
    total_xp  = sum(h.get("xp", 0) for h in last7)
    avg_score = sum(h.get("score", 0) / h.get("total", 1) for h in last7) / len(last7) * 100

    lines.append(f"\n✨ За последние игры: <b>{total_xp} XP</b>")
    lines.append(f"📈 Средний результат: <b>{avg_score:.0f}%</b>")
    lines.append(f"🔥 Серия: <b>{u.get('streak', 0)} дн.</b>")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────────────────────

def kb_main(u: dict):
    lang = u.get("lang", "ru")
    b    = InlineKeyboardBuilder()
    b.button(text=t(u,"quiz"),         callback_data="choose_cat")
    b.button(text=t(u,"study"),        callback_data="study_start")
    b.button(text=t(u,"minigames"),    callback_data="minigames_menu")
    b.button(text=t(u,"courses"),      callback_data="courses_menu")
    b.button(text=t(u,"daily"),        callback_data="daily")
    b.button(text=t(u,"tournament"),   callback_data="tournament")
    b.button(text=t(u,"shop"),         callback_data="shop")
    b.button(text=t(u,"leaderboard"),  callback_data="leaderboard")
    b.button(text=t(u,"profile"),      callback_data="profile")
    b.button(text=t(u,"achievements"), callback_data="achievements")
    b.button(text=t(u,"referral"),     callback_data="referral")
    b.button(text=t(u,"progress"),     callback_data="progress")
    b.button(text=t(u,"lang"),         callback_data="toggle_lang")
    b.adjust(2)
    return b.as_markup()

def kb_back(u: dict):
    b = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    b.button(text="🔄 Ещё раз" if u.get("lang","ru")=="ru" else "🔄 Again", callback_data="choose_cat")
    b.adjust(1)
    return b.as_markup()

def kb_categories(u: dict, prefix: str = "cat"):
    lang = u.get("lang", "ru")
    b    = InlineKeyboardBuilder()
    for k, m in CATEGORIES.items():
        label = m["label"] if lang == "ru" else m["label_en"]
        b.button(text=label, callback_data=f"{prefix}:{k}")
    rnd = "🎲 Случайная" if lang == "ru" else "🎲 Random"
    b.button(text=rnd, callback_data=f"{prefix}:random")
    b.button(text=t(u,"back"), callback_data="main_menu")
    b.adjust(2)
    return b.as_markup()

def kb_difficulty(u: dict, category: str):
    lang = u.get("lang", "ru")
    prem = is_premium(u)
    hard_ok = prem or u.get("hard_unlocked", False)
    b    = InlineKeyboardBuilder()
    for k, cfg in DIFFICULTY_CONFIG.items():
        label = cfg["label"] if lang == "ru" else cfg["label_en"]
        if k == "hard" and not hard_ok:
            b.button(text=f"🔒 Hard", callback_data="shop")
        else:
            b.button(text=label, callback_data=f"diff:{category}:{k}")
    b.button(text=t(u,"back"), callback_data="choose_cat")
    b.adjust(1)
    return b.as_markup()

def kb_quiz(u: dict, q_idx: int, questions: list):
    prem  = is_premium(u)
    hints = u.get("hints_left", 0)
    b     = InlineKeyboardBuilder()
    for i, opt in enumerate(questions[q_idx]["options"]):
        b.button(text=opt, callback_data=f"ans:{q_idx}:{i}")
    b.adjust(1)
    if prem or hints > 0:
        hl = "∞" if prem else str(hints)
        b.button(text=f"💡 Подсказка ({hl})", callback_data=f"hint:{q_idx}")
    else:
        b.button(text="💡 Купить подсказки →", callback_data="shop")
    b.button(text="🚪 Выйти", callback_data="quit_quiz")
    b.adjust(1)
    return b.as_markup()

def kb_minigame(options: list, game_idx: int):
    b = InlineKeyboardBuilder()
    for i, opt in enumerate(options):
        b.button(text=opt, callback_data=f"mg_ans:{game_idx}:{i}")
    b.adjust(1)
    return b.as_markup()

def kb_course(u: dict, course_key: str, lesson_idx: int, answered: bool = False):
    b = InlineKeyboardBuilder()
    course  = COURSES[course_key]
    lessons = course["lessons"]
    if not answered:
        for i, opt in enumerate(lessons[lesson_idx]["options"]):
            b.button(text=opt, callback_data=f"course_ans:{course_key}:{lesson_idx}:{i}")
        b.adjust(1)
    else:
        if lesson_idx + 1 < len(lessons):
            b.button(text="➡️ Следующий урок", callback_data=f"course_next:{course_key}:{lesson_idx+1}")
        else:
            b.button(text="🏁 Завершить курс", callback_data=f"course_done:{course_key}")
    b.button(text=t(u,"back"), callback_data="courses_menu")
    return b.as_markup()

# ─────────────────────────────────────────────────────────────
# УТИЛИТЫ
# ─────────────────────────────────────────────────────────────

def medal(p: int) -> str:
    return {1:"🥇",2:"🥈",3:"🥉"}.get(p, f"{p}.")

def fmt_q(q_idx: int, questions: list, category: str, difficulty: str, u: dict) -> str:
    lang  = u.get("lang", "ru")
    total = len(questions)
    bar   = "█" * q_idx + "░" * (total - q_idx)
    xp    = DIFFICULTY_CONFIG[difficulty]["xp"]
    cat   = CATEGORIES[category]["label"] if lang == "ru" else CATEGORIES[category]["label_en"]
    diff  = DIFFICULTY_CONFIG[difficulty]["label"] if lang == "ru" else DIFFICULTY_CONFIG[difficulty]["label_en"]
    return (
        f"<b>{cat}  {diff}</b>\n"
        f"{'Вопрос' if lang=='ru' else 'Question'} {q_idx+1}/{total}  +{xp} XP\n"
        f"<code>[{bar}]</code>\n\n"
        f"{questions[q_idx]['question']}"
    )

def get_daily_q() -> dict:
    all_q = [{**q, "category": k} for k, qs in QUESTIONS_DB.items() for q in qs]
    return random.Random(date.today().toordinal()).choice(all_q)

# ─────────────────────────────────────────────────────────────
# РОУТЕР
# ─────────────────────────────────────────────────────────────

router = Router()

# ── /start ──────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name  = message.from_user.first_name or "друг"
    stats = load_stats()
    uid   = message.from_user.id

    # Проверяем реферальный код
    args = message.text.split()
    if len(args) > 1:
        ref_code = args[1]
        # Ищем кого пригласили
        for other_uid, other_u in stats.items():
            if other_u.get("referral_code") == ref_code and other_uid != str(uid):
                u_inviter = other_u
                if str(uid) not in [str(uid)]:  # не сам себя
                    u_inviter["referral_count"] = u_inviter.get("referral_count", 0) + 1
                    u_inviter["xp"]             = u_inviter.get("xp", 0) + 50
                    u_inviter["hints_left"]     = u_inviter.get("hints_left", 0) + 2
                    check_achievements(u_inviter)
                    logger.info(f"Реферал: {uid} пришёл от {other_uid}")
                break

    u = get_user(stats, uid, name)
    save_stats(stats)

    xp      = u.get("xp", 0)
    lang    = u.get("lang", "ru")
    _, lv   = get_level(xp, lang)
    prem    = " 💎" if is_premium(u) else ""
    boost   = " ⚡" if is_xp_boost(u) else ""

    await message.answer(
        f"{t(u, 'welcome', name=name)}{prem}\n\n"
        f"┌──────────────────────────┐\n"
        f"│  🐍 Python Quiz Bot v5   │\n"
        f"└──────────────────────────┘\n\n"
        f"{t(u,'level')} {get_level(xp,lang)[0]}: <b>{lv}</b>  •  {t(u,'xp')}: <b>{xp}</b>{boost}",
        reply_markup=kb_main(u),
        parse_mode="HTML",
    )

# ── /ref — реферальная ссылка ────────────────────────────────

@router.message(Command("ref"))
async def cmd_ref(message: Message):
    stats = load_stats()
    u     = get_user(stats, message.from_user.id, message.from_user.first_name or "")
    bot   = await message.bot.get_me()
    code  = u.get("referral_code", str(message.from_user.id)[-6:])
    link  = f"https://t.me/{bot.username}?start={code}"
    lang  = u.get("lang", "ru")

    if lang == "ru":
        text = (
            f"👥 <b>Реферальная программа</b>\n\n"
            f"Твоя ссылка:\n<code>{link}</code>\n\n"
            f"За каждого приглашённого друга:\n"
            f"• Ты получаешь <b>+50 XP</b> и <b>+2 подсказки</b>\n"
            f"• Друг получает приветственный бонус\n\n"
            f"Приглашено друзей: <b>{u.get('referral_count', 0)}</b>"
        )
    else:
        text = (
            f"👥 <b>Referral Program</b>\n\n"
            f"Your link:\n<code>{link}</code>\n\n"
            f"For each invited friend:\n"
            f"• You get <b>+50 XP</b> and <b>+2 hints</b>\n"
            f"• Friend gets welcome bonus\n\n"
            f"Friends invited: <b>{u.get('referral_count', 0)}</b>"
        )
    b = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    await message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")

# ── Главное меню ─────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    await callback.message.edit_text(
        t(u, "menu"),
        reply_markup=kb_main(u),
        parse_mode="HTML",
    )
    await callback.answer()

# ── Переключение языка ───────────────────────────────────────

@router.callback_query(F.data == "toggle_lang")
async def toggle_lang(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    u["lang"] = "en" if u.get("lang", "ru") == "ru" else "ru"
    save_stats(stats)
    lang = u["lang"]
    msg  = "🌍 Language: <b>English</b>" if lang == "en" else "🌍 Язык: <b>Русский</b>"
    await callback.message.edit_text(msg, reply_markup=kb_main(u), parse_mode="HTML")
    await callback.answer()

# ── Реферальная система ──────────────────────────────────────

@router.callback_query(F.data == "referral")
async def referral_menu(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    bot   = await callback.bot.get_me()
    code  = u.get("referral_code", str(callback.from_user.id)[-6:])
    link  = f"https://t.me/{bot.username}?start={code}"
    lang  = u.get("lang", "ru")

    if lang == "ru":
        text = (
            f"👥 <b>Приглашай друзей!</b>\n\n"
            f"Ссылка:\n<code>{link}</code>\n\n"
            f"🎁 За каждого друга: <b>+50 XP</b> + <b>+2 подсказки</b>\n"
            f"👥 Приглашено: <b>{u.get('referral_count', 0)}</b>"
        )
    else:
        text = (
            f"👥 <b>Invite Friends!</b>\n\n"
            f"Link:\n<code>{link}</code>\n\n"
            f"🎁 Per friend: <b>+50 XP</b> + <b>+2 hints</b>\n"
            f"👥 Invited: <b>{u.get('referral_count', 0)}</b>"
        )

    b = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()

# ── МИНИ-ИГРЫ ────────────────────────────────────────────────

@router.callback_query(F.data == "minigames_menu")
async def minigames_menu(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    played = u.get("minigames_played", 0)
    correct = u.get("minigames_correct", 0)
    acc = f"{correct/played*100:.0f}%" if played > 0 else "—"

    b = InlineKeyboardBuilder()
    b.button(text="🐛 Найди ошибку",    callback_data="mg:bug")
    b.button(text="💻 Угадай вывод",    callback_data="mg:output")
    b.button(text=t(u,"back"),          callback_data="main_menu")
    b.adjust(1)

    text = (
        f"📱 <b>Мини-игры</b>\n\n"
        f"🎮 Сыграно: <b>{played}</b>  📈 Точность: <b>{acc}</b>\n\n"
        f"🐛 <b>Найди ошибку</b> — найди баг в коде\n"
        f"💻 <b>Угадай вывод</b> — что выведет программа?"
    ) if lang == "ru" else (
        f"📱 <b>Mini-games</b>\n\n"
        f"🎮 Played: <b>{played}</b>  📈 Accuracy: <b>{acc}</b>\n\n"
        f"🐛 <b>Find the bug</b> — find the bug in code\n"
        f"💻 <b>Guess output</b> — what does the program print?"
    )

    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("mg:"))
async def start_minigame(callback: CallbackQuery, state: FSMContext):
    game_type = callback.data.split(":")[1]
    stats     = load_stats()
    u         = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")

    if game_type == "bug":
        games = MINIGAMES_FIND_BUG
    else:
        games = MINIGAMES_GUESS_OUTPUT

    game = random.choice(games)
    idx  = games.index(game)

    await state.set_state(QuizStates.mini_game)
    await state.update_data(game_type=game_type, game_idx=idx)

    text = f"{game['question']}\n\n<pre>{game['code']}</pre>"
    await callback.message.edit_text(
        text,
        reply_markup=kb_minigame(game["options"], idx),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(QuizStates.mini_game, F.data.startswith("mg_ans:"))
async def minigame_answer(callback: CallbackQuery, state: FSMContext):
    _, g_idx_str, opt_str = callback.data.split(":")
    g_idx      = int(g_idx_str)
    opt        = int(opt_str)
    data       = await state.get_data()
    game_type  = data.get("game_type", "bug")
    games      = MINIGAMES_FIND_BUG if game_type == "bug" else MINIGAMES_GUESS_OUTPUT
    game       = games[g_idx % len(games)]
    is_correct = opt == game["correct"]

    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    u["minigames_played"] = u.get("minigames_played", 0) + 1
    if is_correct:
        u["minigames_correct"] = u.get("minigames_correct", 0) + 1
        u["xp"]                = u.get("xp", 0) + 5
    new_ach = check_achievements(u)
    save_stats(stats)

    correct_text = game["options"][game["correct"]]
    fb = t(u, "correct") if is_correct else f"{t(u, 'wrong')} {correct_text}"

    b = InlineKeyboardBuilder()
    b.button(text="🔄 Ещё" if u.get("lang","ru")=="ru" else "🔄 Again", callback_data=f"mg:{game_type}")
    b.button(text=t(u,"back"), callback_data="minigames_menu")
    b.adjust(1)

    ach_text = ""
    if new_ach:
        icons    = " ".join(ACHIEVEMENTS[a]["icon"] for a in new_ach)
        ach_text = f"\n\n🎖 {icons}"

    await state.clear()
    await callback.message.edit_text(
        f"{game['question']}\n\n<pre>{game['code']}</pre>\n\n"
        f"{'─'*20}\n{fb}\n\n"
        f"📖 {game['explanation']}{ach_text}",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer("✅" if is_correct else "❌")

# ── КУРСЫ ────────────────────────────────────────────────────

@router.callback_query(F.data == "courses_menu")
async def courses_menu(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")

    b = InlineKeyboardBuilder()
    for key, course in COURSES.items():
        title    = course["title"] if lang == "ru" else course["title_en"]
        progress = u.get("courses_progress", {}).get(key, {})
        done     = progress.get("done", False)
        cur      = progress.get("lesson", 0)
        total    = len(course["lessons"])
        status   = "✅" if done else f"{cur}/{total}"
        b.button(text=f"{title} {status}", callback_data=f"course:{key}")
    b.button(text=t(u,"back"), callback_data="main_menu")
    b.adjust(1)

    title = "🎓 <b>Курсы по Python</b>" if lang == "ru" else "🎓 <b>Python Courses</b>"
    desc  = "Структурированные уроки с теорией и практикой" if lang == "ru" else "Structured lessons with theory and practice"

    await callback.message.edit_text(
        f"{title}\n\n{desc}",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("course:"))
async def start_course(callback: CallbackQuery, state: FSMContext):
    course_key = callback.data.split(":")[1]
    stats      = load_stats()
    u          = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang       = u.get("lang", "ru")

    progress = u.get("courses_progress", {}).get(course_key, {})
    lesson_idx = progress.get("lesson", 0)
    course     = COURSES[course_key]
    lessons    = course["lessons"]

    if lesson_idx >= len(lessons) or progress.get("done"):
        lesson_idx = 0

    await state.set_state(QuizStates.course_study)
    await state.update_data(course_key=course_key, lesson_idx=lesson_idx)

    lesson = lessons[lesson_idx]
    title  = course["title"] if lang == "ru" else course["title_en"]

    await callback.message.edit_text(
        f"🎓 <b>{title}</b>\n"
        f"{'Урок' if lang=='ru' else 'Lesson'} {lesson_idx+1}/{len(lessons)}\n\n"
        f"<b>{lesson['title']}</b>\n\n"
        f"{lesson['content']}\n\n"
        f"{'─'*20}\n"
        f"<b>{'Вопрос' if lang=='ru' else 'Question'}:</b> {lesson['question']}",
        reply_markup=kb_course(u, course_key, lesson_idx),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(QuizStates.course_study, F.data.startswith("course_ans:"))
async def course_answer(callback: CallbackQuery, state: FSMContext):
    parts      = callback.data.split(":")
    course_key = parts[1]
    lesson_idx = int(parts[2])
    opt        = int(parts[3])
    course     = COURSES[course_key]
    lesson     = course["lessons"][lesson_idx]
    is_correct = opt == lesson["correct"]
    stats      = load_stats()
    u          = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang       = u.get("lang", "ru")

    if is_correct:
        u["xp"] = u.get("xp", 0) + 10
    # Сохраняем прогресс
    if "courses_progress" not in u:
        u["courses_progress"] = {}
    u["courses_progress"][course_key] = {"lesson": lesson_idx + 1, "done": False}
    save_stats(stats)

    correct_text = lesson["options"][lesson["correct"]]
    fb = t(u, "correct") if is_correct else f"{t(u,'wrong')} <b>{correct_text}</b>"
    title = course["title"] if lang == "ru" else course["title_en"]

    await callback.message.edit_text(
        f"🎓 <b>{title}</b>\n"
        f"{'Урок' if lang=='ru' else 'Lesson'} {lesson_idx+1}/{len(course['lessons'])}\n\n"
        f"<b>{lesson['title']}</b>\n\n"
        f"{lesson['content']}\n\n"
        f"{'─'*20}\n{fb}",
        reply_markup=kb_course(u, course_key, lesson_idx, answered=True),
        parse_mode="HTML",
    )
    await callback.answer("✅" if is_correct else "❌")

@router.callback_query(QuizStates.course_study, F.data.startswith("course_next:"))
async def course_next(callback: CallbackQuery, state: FSMContext):
    parts      = callback.data.split(":")
    course_key = parts[1]
    lesson_idx = int(parts[2])
    course     = COURSES[course_key]
    lessons    = course["lessons"]
    stats      = load_stats()
    u          = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang       = u.get("lang", "ru")
    title      = course["title"] if lang == "ru" else course["title_en"]
    lesson     = lessons[lesson_idx]

    await state.update_data(lesson_idx=lesson_idx)
    await callback.message.edit_text(
        f"🎓 <b>{title}</b>\n"
        f"{'Урок' if lang=='ru' else 'Lesson'} {lesson_idx+1}/{len(lessons)}\n\n"
        f"<b>{lesson['title']}</b>\n\n"
        f"{lesson['content']}\n\n"
        f"{'─'*20}\n"
        f"<b>{'Вопрос' if lang=='ru' else 'Question'}:</b> {lesson['question']}",
        reply_markup=kb_course(u, course_key, lesson_idx),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("course_done:"))
async def course_done(callback: CallbackQuery, state: FSMContext):
    course_key = callback.data.split(":")[1]
    stats      = load_stats()
    u          = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang       = u.get("lang", "ru")

    if "courses_progress" not in u:
        u["courses_progress"] = {}
    u["courses_progress"][course_key] = {"lesson": len(COURSES[course_key]["lessons"]), "done": True}
    u["courses_done"] = u.get("courses_done", 0) + 1
    u["xp"]           = u.get("xp", 0) + 50
    new_ach           = check_achievements(u)
    save_stats(stats)

    await state.clear()
    title    = COURSES[course_key]["title"] if lang == "ru" else COURSES[course_key]["title_en"]
    ach_text = ""
    if new_ach:
        icons    = " ".join(ACHIEVEMENTS[a]["icon"] for a in new_ach)
        ach_text = f"\n\n🎖 {icons}"

    b = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="courses_menu")

    msg = (
        f"🏁 <b>Курс завершён!</b>\n\n{title}\n\n"
        f"✨ +50 XP за прохождение курса!{ach_text}"
    ) if lang == "ru" else (
        f"🏁 <b>Course completed!</b>\n\n{title}\n\n"
        f"✨ +50 XP for completing the course!{ach_text}"
    )

    await callback.message.edit_text(msg, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()

# ── ТУРНИР ───────────────────────────────────────────────────

@router.callback_query(F.data == "tournament")
async def tournament_view(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    top   = get_tournament_top()
    t_data = load_tournament()

    # Дни до конца недели
    today  = date.today()
    sunday = today + timedelta(days=(6 - today.weekday()))
    days_left = (sunday - today).days + 1

    lines = []
    uid_str = str(callback.from_user.id)
    my_pos  = None
    for i, l in enumerate(top, 1):
        mark = " ←" if l["uid"] == uid_str else ""
        lines.append(f"{medal(i)} <b>{l['username']}</b> — ✨{l['xp']} XP{mark}")
        if l["uid"] == uid_str:
            my_pos = i

    last_w = f"\n\n🏆 Победитель прошлой недели: <b>{t_data.get('last_winner','—')}</b>" if t_data.get("last_winner") else ""

    text = (
        f"🏟 <b>Недельный турнир</b>\n"
        f"До конца недели: <b>{days_left} дн.</b>\n\n"
        + ("\n".join(lines) if lines else "Пока нет участников")
        + (f"\n\nТвоя позиция: <b>{my_pos}</b>" if my_pos else "")
        + last_w
        + "\n\n<i>Победитель получает бесплатный Premium на 7 дней!</i>"
    ) if lang == "ru" else (
        f"🏟 <b>Weekly Tournament</b>\n"
        f"Days left: <b>{days_left}</b>\n\n"
        + ("\n".join(lines) if lines else "No participants yet")
        + (f"\n\nYour position: <b>{my_pos}</b>" if my_pos else "")
        + last_w
        + "\n\n<i>Winner gets free Premium for 7 days!</i>"
    )

    b = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()

# ── ПРОГРЕСС ─────────────────────────────────────────────────

@router.callback_query(F.data == "progress")
async def show_progress(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    chart = build_progress_chart(u, u.get("lang", "ru"))
    b     = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    await callback.message.edit_text(chart, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()

# ── КВИЗ ─────────────────────────────────────────────────────

@router.callback_query(F.data == "choose_cat")
async def choose_cat(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    title = "🎯 <b>Выбери категорию:</b>" if lang == "ru" else "🎯 <b>Choose category:</b>"
    await callback.message.edit_text(title, reply_markup=kb_categories(u), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("cat:"))
async def choose_diff(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split(":")[1]
    if cat == "random":
        cat = random.choice(list(QUESTIONS_DB.keys()))
    await state.update_data(category=cat)
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    cat_label = CATEGORIES[cat]["label"] if lang == "ru" else CATEGORIES[cat]["label_en"]
    title = f"<b>{cat_label}</b>\n\n{'Выбери сложность:' if lang=='ru' else 'Choose difficulty:'}"
    await callback.message.edit_text(title, reply_markup=kb_difficulty(u, cat), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("diff:"))
async def start_quiz(callback: CallbackQuery, state: FSMContext):
    _, cat, diff = callback.data.split(":")
    all_q     = QUESTIONS_DB[cat]
    filtered  = [q for q in all_q if q.get("difficulty") == diff] or all_q
    questions = random.sample(filtered, min(len(filtered), 5))
    stats     = load_stats()
    u         = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")

    await state.set_state(QuizStates.in_progress)
    await state.update_data(
        cat=cat, diff=diff, questions=questions,
        idx=0, score=0, any_hint=False, used_hint=False, answered=False,
    )

    await callback.message.edit_text(
        fmt_q(0, questions, cat, diff, u),
        reply_markup=kb_quiz(u, 0, questions),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(QuizStates.in_progress, F.data == "quit_quiz")
async def quit_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    await callback.message.edit_text(
        "🚪 Вышел из квиза." if u.get("lang","ru")=="ru" else "🚪 Left the quiz.",
        reply_markup=kb_back(u), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(QuizStates.in_progress, F.data.startswith("hint:"))
async def show_hint(callback: CallbackQuery, state: FSMContext):
    data      = await state.get_data()
    q_idx     = int(callback.data.split(":")[1])
    questions = data["questions"]
    cat, diff = data["cat"], data["diff"]
    stats     = load_stats()
    u         = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    prem      = is_premium(u)

    if not prem:
        if u.get("hints_left", 0) <= 0:
            await callback.answer("Подсказки закончились! 🛒", show_alert=True)
            return
        u["hints_left"] -= 1
        save_stats(stats)

    await state.update_data(used_hint=True, any_hint=True)
    await callback.message.edit_text(
        f"{fmt_q(q_idx, questions, cat, diff, u)}\n\n"
        f"💡 <b>Подсказка:</b> {questions[q_idx]['hint']}",
        reply_markup=kb_quiz(u, q_idx, questions),
        parse_mode="HTML",
    )
    await callback.answer("💡")

@router.callback_query(QuizStates.in_progress, F.data.startswith("ans:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("answered"):
        await callback.answer("Уже ответил!")
        return

    _, qs, os_ = callback.data.split(":")
    q_idx, opt = int(qs), int(os_)
    questions  = data["questions"]
    cat, diff  = data["cat"], data["diff"]
    q          = questions[q_idx]
    any_hint   = data.get("any_hint", False)
    is_correct = opt == q["correct"]
    new_score  = data["score"] + (1 if is_correct else 0)

    await state.update_data(score=new_score, answered=True, used_hint=False)
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")

    correct_text = q["options"][q["correct"]]
    fb = t(u,"correct") if is_correct else f"{t(u,'wrong')} <b>{correct_text}</b>"
    fb += f"\n💡 {q['hint']}"

    next_idx = q_idx + 1
    total    = len(questions)

    if next_idx < total:
        await state.update_data(idx=next_idx, answered=False, used_hint=False, any_hint=False)
        await callback.message.edit_text(
            f"{fmt_q(q_idx, questions, cat, diff, u)}\n\n{'─'*22}\n{fb}\n{'─'*22}\n\n"
            f"{fmt_q(next_idx, questions, cat, diff, u)}",
            reply_markup=kb_quiz(u, next_idx, questions),
            parse_mode="HTML",
        )
        await callback.answer("✅" if is_correct else "❌")
    else:
        # Финал
        name     = callback.from_user.first_name or "Игрок"
        base_xp  = DIFFICULTY_CONFIG[diff]["xp"] * new_score
        earned   = int(base_xp * (2 if is_xp_boost(u) else 1))
        perfect  = new_score == total and not any_hint
        if perfect:
            earned += 30
            u["perfect_games"] = u.get("perfect_games", 0) + 1
        if not any_hint:
            u["no_hint_games"] = u.get("no_hint_games", 0) + 1

        bonus_streak = update_streak(u)
        earned += bonus_streak

        u["xp"]             = u.get("xp", 0) + earned
        u["total_games"]    = u.get("total_games", 0) + 1
        u["total_correct"]  = u.get("total_correct", 0) + new_score
        u["total_questions"]= u.get("total_questions", 0) + total
        u["best_score"]     = max(u.get("best_score", 0), new_score)
        u["weekly_xp"]      = u.get("weekly_xp", 0) + earned
        cats = u.get("cats_played", [])
        if cat not in cats: cats.append(cat)
        u["cats_played"] = cats
        u["history"].append({"date": str(date.today()), "cat": cat, "diff": diff, "score": new_score, "total": total, "xp": earned})
        u["history"] = u["history"][-20:]

        new_ach = check_achievements(u)
        save_stats(stats)

        # Обновляем турнир
        update_tournament_score(callback.from_user.id, name, earned)

        lang   = u.get("lang", "ru")
        _, lv  = get_level(u["xp"], lang)
        bar    = xp_bar(u["xp"])
        streak = u.get("streak", 0)
        stars  = "⭐" * new_score + "☆" * (total - new_score)

        ach_text = ""
        if new_ach:
            icons    = " ".join(ACHIEVEMENTS[a]["icon"] for a in new_ach)
            names    = ", ".join(ACHIEVEMENTS[a]["name" if lang=="ru" else "name_en"] for a in new_ach)
            ach_text = f"\n\n🎖 <b>{'Новые достижения' if lang=='ru' else 'New achievements'}!</b>\n{icons} {names}"

        result_text = (
            f"🏁 <b>{'Квиз завершён' if lang=='ru' else 'Quiz done'}!</b>\n\n"
            f"🎯 {new_score}/{total}  {stars}\n"
            f"✨ +{earned} XP"
            + (f"  🔥{streak}" if streak > 1 else "") + f"\n\n"
            f"{lv}  <code>[{bar}]</code>  {u['xp']} XP\n\n"
            + ach_text
        )

        await state.clear()
        await callback.message.edit_text(result_text, reply_markup=kb_back(u), parse_mode="HTML")
        await callback.answer()

@router.message(QuizStates.in_progress)
async def quiz_guard(message: Message):
    await message.answer("⚠️ Нажимай на кнопки! 👆")

# ── РЕЖИМ ОБУЧЕНИЯ ───────────────────────────────────────────

@router.callback_query(F.data == "study_start")
async def study_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    title = "📝 <b>Режим обучения</b>\n\nВыбери тему:" if lang == "ru" else "📝 <b>Study mode</b>\n\nChoose topic:"
    await callback.message.edit_text(title, reply_markup=kb_categories(u, "st_cat"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("st_cat:"))
async def study_begin(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split(":")[1]
    if cat == "random": cat = random.choice(list(QUESTIONS_DB.keys()))
    qs  = random.sample(QUESTIONS_DB[cat], min(len(QUESTIONS_DB[cat]), 5))
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    cat_label = CATEGORIES[cat]["label"] if lang == "ru" else CATEGORIES[cat]["label_en"]

    await state.set_state(QuizStates.study_mode)
    await state.update_data(cat=cat, questions=qs, idx=0)
    await callback.message.edit_text(
        f"📝 <b>{cat_label}</b>\n{'Вопрос' if lang=='ru' else 'Question'} 1/{len(qs)}\n\n{qs[0]['question']}",
        reply_markup=_kb_study(u, 0, qs), parse_mode="HTML",
    )
    await callback.answer()

def _kb_study(u, q_idx, questions, answered=False):
    b = InlineKeyboardBuilder()
    if not answered:
        for i, opt in enumerate(questions[q_idx]["options"]):
            b.button(text=opt, callback_data=f"st_ans:{q_idx}:{i}")
        b.adjust(1)
    else:
        if q_idx + 1 < len(questions):
            b.button(text="➡️", callback_data=f"st_next:{q_idx+1}")
        else:
            b.button(text="🏁", callback_data="main_menu")
    b.button(text=t(u,"back"), callback_data="main_menu")
    return b.as_markup()

@router.callback_query(QuizStates.study_mode, F.data.startswith("st_ans:"))
async def study_ans(callback: CallbackQuery, state: FSMContext):
    data       = await state.get_data()
    q_idx, opt = int(callback.data.split(":")[1]), int(callback.data.split(":")[2])
    qs, cat    = data["questions"], data["cat"]
    q          = qs[q_idx]
    is_correct = opt == q["correct"]
    stats      = load_stats()
    u          = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang       = u.get("lang", "ru")
    cat_label  = CATEGORIES[cat]["label"] if lang == "ru" else CATEGORIES[cat]["label_en"]
    ct         = q["options"][q["correct"]]
    fb = t(u,"correct") if is_correct else f"{t(u,'wrong')} <b>{ct}</b>"
    await callback.message.edit_text(
        f"📝 <b>{cat_label}</b>\n{'Вопрос' if lang=='ru' else 'Question'} {q_idx+1}/{len(qs)}\n\n"
        f"{q['question']}\n\n{'─'*20}\n{fb}\n\n📖 {q['explanation']}",
        reply_markup=_kb_study(u, q_idx, qs, answered=True), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(QuizStates.study_mode, F.data.startswith("st_next:"))
async def study_next(callback: CallbackQuery, state: FSMContext):
    data      = await state.get_data()
    nxt       = int(callback.data.split(":")[1])
    qs, cat   = data["questions"], data["cat"]
    stats     = load_stats()
    u         = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang      = u.get("lang", "ru")
    cat_label = CATEGORIES[cat]["label"] if lang == "ru" else CATEGORIES[cat]["label_en"]
    await state.update_data(idx=nxt)
    await callback.message.edit_text(
        f"📝 <b>{cat_label}</b>\n{'Вопрос' if lang=='ru' else 'Question'} {nxt+1}/{len(qs)}\n\n{qs[nxt]['question']}",
        reply_markup=_kb_study(u, nxt, qs), parse_mode="HTML",
    )
    await callback.answer()

# ── ВОПРОС ДНЯ ───────────────────────────────────────────────

@router.callback_query(F.data == "daily")
async def daily(callback: CallbackQuery, state: FSMContext):
    q     = get_daily_q()
    today = str(date.today())
    data  = await state.get_data()
    done  = data.get("daily_date") == today
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    cat   = CATEGORIES.get(q["category"], {}).get("label" if lang == "ru" else "label_en", "")
    b     = InlineKeyboardBuilder()

    if not done:
        await state.update_data(daily_q=q)
        for i, opt in enumerate(q["options"]):
            b.button(text=opt, callback_data=f"daily_a:{i}")
        b.adjust(1)
    else:
        ct = q["options"][q["correct"]]
        b.button(text=t(u,"back"), callback_data="main_menu")
        await callback.message.edit_text(
            f"📅 <b>{'Вопрос дня' if lang=='ru' else 'Daily question'} — {today}</b>\n{cat}\n\n{q['question']}\n\n"
            f"{'✅ Уже отвечал! Ответ:' if lang=='ru' else '✅ Already answered! Answer:'} <b>{ct}</b>",
            reply_markup=b.as_markup(), parse_mode="HTML",
        )
        await callback.answer()
        return

    b.button(text=t(u,"back"), callback_data="main_menu")
    await callback.message.edit_text(
        f"📅 <b>{'Вопрос дня' if lang=='ru' else 'Daily question'} — {today}</b>\n{cat}  •  +15 XP\n\n{q['question']}",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("daily_a:"))
async def daily_ans(callback: CallbackQuery, state: FSMContext):
    data  = await state.get_data()
    q     = data.get("daily_q") or get_daily_q()
    opt   = int(callback.data.split(":")[1])
    today = str(date.today())
    ok    = opt == q["correct"]
    await state.update_data(daily_date=today)
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    if ok:
        bonus = int(15 * (2 if is_xp_boost(u) else 1))
        u["xp"] = u.get("xp", 0) + bonus
        update_tournament_score(callback.from_user.id, callback.from_user.first_name or "", bonus)
    u["daily_count"] = u.get("daily_count", 0) + 1
    save_stats(stats)
    ct = q["options"][q["correct"]]
    fb = (f"✅ +15 XP!\n💡 {q['hint']}" if ok else f"❌ {'Ответ' if lang=='ru' else 'Answer'}: <b>{ct}</b>\n💡 {q['hint']}")
    b  = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    await callback.message.edit_text(
        f"📅 {today}\n\n{q['question']}\n\n{'─'*20}\n{fb}",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer("✅" if ok else "❌")

# ── МАГАЗИН ──────────────────────────────────────────────────

@router.callback_query(F.data == "shop")
async def show_shop(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang  = u.get("lang", "ru")
    prem  = is_premium(u)
    hints = "∞" if prem else str(u.get("hints_left", 0))
    b     = InlineKeyboardBuilder()
    for key, item in SHOP_ITEMS.items():
        b.button(text=f"{item['title']} — ⭐{item['stars']}", callback_data=f"buy:{key}")
    b.button(text=t(u,"back"), callback_data="main_menu")
    b.adjust(1)
    title = "🛒 <b>Магазин</b>" if lang == "ru" else "🛒 <b>Shop</b>"
    await callback.message.edit_text(
        f"{title}\n\n💡 {'Подсказок' if lang=='ru' else 'Hints'}: <b>{hints}</b>\n\n"
        + "\n".join(f"{i['title']}\n<i>{i['description']}</i> — ⭐{i['stars']}\n" for i in SHOP_ITEMS.values()),
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("buy:"))
async def buy_item(callback: CallbackQuery, bot: Bot):
    key  = callback.data.split(":")[1]
    item = SHOP_ITEMS.get(key)
    if not item:
        await callback.answer("Не найдено!")
        return
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=item["title"],
        description=item["description"],
        payload=item["payload"],
        currency="XTR",
        prices=[LabeledPrice(label=item["title"], amount=item["stars"])],
    )
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def payment_success(message: Message, bot: Bot):
    payment = message.successful_payment
    payload = payment.invoice_payload
    stars   = payment.total_amount
    uid     = message.from_user.id
    stats   = load_stats()
    u       = get_user(stats, uid, message.from_user.first_name or "")
    u["total_purchases"]   = u.get("total_purchases", 0) + 1
    u["total_stars_spent"] = u.get("total_stars_spent", 0) + stars
    result_msg = apply_purchase(u, payload)
    new_ach    = check_achievements(u)
    save_stats(stats)
    ach_text = ""
    if new_ach:
        icons    = " ".join(ACHIEVEMENTS[a]["icon"] for a in new_ach)
        ach_text = f"\n\n🎖 {icons}"
    await message.answer(
        f"✅ <b>Оплата прошла!</b>\n\n⭐ {stars} Stars\n\n{result_msg}{ach_text}",
        reply_markup=kb_back(u), parse_mode="HTML",
    )
    if ADMIN_ID:
        try:
            item_name = next((i["title"] for i in SHOP_ITEMS.values() if i["payload"] == payload), payload)
            await bot.send_message(ADMIN_ID, f"💰 <b>Покупка!</b>\n👤 {u['username']} ({uid})\n🛒 {item_name}\n⭐ {stars}", parse_mode="HTML")
        except Exception:
            pass

# ── ПРОФИЛЬ ──────────────────────────────────────────────────

@router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    stats = load_stats()
    name  = callback.from_user.first_name or "Игрок"
    u     = get_user(stats, callback.from_user.id, name)
    lang  = u.get("lang", "ru")
    xp    = u.get("xp", 0)
    lv_n, lv = get_level(xp, lang)[0], get_level(xp, lang)[1]
    bar   = xp_bar(xp)
    prem  = is_premium(u)
    boost = is_xp_boost(u)
    games = u.get("total_games", 0)
    cor   = u.get("total_correct", 0)
    tot_q = u.get("total_questions", 0)
    avg   = f"{cor/tot_q*100:.0f}%" if tot_q else "—"
    streak = u.get("streak", 0)
    hints  = "∞" if prem else str(u.get("hints_left", 0))
    refs   = u.get("referral_count", 0)
    courses_done = u.get("courses_done", 0)
    mg_played    = u.get("minigames_played", 0)

    status = []
    if prem:
        until = datetime.fromisoformat(u["premium_until"]).strftime("%d.%m.%Y")
        status.append(f"👑 Premium до {until}")
    if boost:
        until = datetime.fromisoformat(u["xp_boost_until"]).strftime("%d.%m.%Y")
        status.append(f"⚡ XP x2 до {until}")
    st_str = "\n".join(status) + "\n\n" if status else ""

    hist_lines = []
    for h in reversed(u.get("history", [])[-3:]):
        cat  = CATEGORIES.get(h.get("cat",""), {}).get("emoji","🎯")
        diff = DIFFICULTY_CONFIG.get(h.get("diff","easy"), {}).get("label","")
        hist_lines.append(f"  {cat} {h['score']}/{h['total']} {diff} +{h.get('xp',0)} XP")

    await callback.message.edit_text(
        f"👤 <b>{name}</b>{' 💎' if prem else ''}\n\n"
        f"{st_str}"
        f"{'─'*22}\n"
        f"🏅 {t(u,'level')} {lv_n}: <b>{lv}</b>\n"
        f"✨ {t(u,'xp')}: <b>{xp}</b>\n"
        f"<code>[{bar}]</code>\n\n"
        f"🔥 {t(u,'streak')}: <b>{streak}</b>\n"
        f"🎮 {t(u,'games')}: <b>{games}</b>  📈 <b>{avg}</b>\n"
        f"💡 {'Подсказок' if lang=='ru' else 'Hints'}: <b>{hints}</b>\n"
        f"👥 {'Рефералов' if lang=='ru' else 'Referrals'}: <b>{refs}</b>\n"
        f"🎓 {'Курсов' if lang=='ru' else 'Courses'}: <b>{courses_done}</b>\n"
        f"📱 {'Мини-игр' if lang=='ru' else 'Mini-games'}: <b>{mg_played}</b>\n"
        + (f"\n📊 <b>{'Последние игры' if lang=='ru' else 'Recent games'}:</b>\n" + "\n".join(hist_lines) if hist_lines else ""),
        reply_markup=kb_back(u), parse_mode="HTML",
    )
    await callback.answer()

# ── ДОСТИЖЕНИЯ ───────────────────────────────────────────────

@router.callback_query(F.data == "achievements")
async def achievements(callback: CallbackQuery):
    stats  = load_stats()
    u      = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang   = u.get("lang", "ru")
    earned = set(u.get("achievements", []))
    lines  = [
        f"{a['icon']} <b>{a['name' if lang=='ru' else 'name_en']}</b>"
        if k in earned else
        f"🔒 <i>{a['name' if lang=='ru' else 'name_en']}</i>"
        for k, a in ACHIEVEMENTS.items()
    ]
    b = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    title = "🎖 <b>Достижения</b>" if lang == "ru" else "🎖 <b>Achievements</b>"
    await callback.message.edit_text(
        f"{title}  {len(earned)}/{len(ACHIEVEMENTS)}\n\n" + "\n".join(lines),
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

# ── ЛИДЕРБОРД ────────────────────────────────────────────────

@router.callback_query(F.data == "leaderboard")
async def leaderboard(callback: CallbackQuery):
    stats   = load_stats()
    u       = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    lang    = u.get("lang", "ru")
    leaders = sorted(
        [{"name": v["username"], "xp": v.get("xp",0), "lv": get_level(v.get("xp",0), lang)[1],
          "games": v.get("total_games",0), "streak": v.get("streak",0), "prem": is_premium(v)}
         for v in stats.values() if v.get("total_questions",0) > 0],
        key=lambda x: x["xp"], reverse=True
    )[:10]

    if not leaders:
        b = InlineKeyboardBuilder()
        b.button(text=t(u,"back"), callback_data="main_menu")
        await callback.message.edit_text("🏆 Пусто!" if lang == "ru" else "🏆 Empty!", reply_markup=b.as_markup())
        await callback.answer()
        return

    lines = []
    for i, l in enumerate(leaders, 1):
        badge  = " 💎" if l["prem"] else ""
        streak = f"  🔥{l['streak']}" if l["streak"] > 1 else ""
        lines.append(f"{medal(i)} <b>{l['name']}</b>{badge}  {l['lv']}\n   ✨{l['xp']} XP  🎮{l['games']}{streak}")

    b = InlineKeyboardBuilder()
    b.button(text=t(u,"back"), callback_data="main_menu")
    title = "🏆 <b>Таблица лидеров</b>" if lang == "ru" else "🏆 <b>Leaderboard</b>"
    await callback.message.edit_text(
        f"{title}\n\n" + "\n\n".join(lines),
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

# ── АДМИН ────────────────────────────────────────────────────

def is_admin(uid: int) -> bool:
    return ADMIN_ID != 0 and uid == ADMIN_ID

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔")
        return
    stats        = load_stats()
    users        = len(stats)
    total_stars  = sum(u.get("total_stars_spent", 0) for u in stats.values())
    total_games  = sum(u.get("total_games", 0) for u in stats.values())
    premium_cnt  = sum(1 for u in stats.values() if is_premium(u))
    purchases    = sum(u.get("total_purchases", 0) for u in stats.values())
    refs         = sum(u.get("referral_count", 0) for u in stats.values())
    top_t        = get_tournament_top(3)
    t_str        = "\n".join(f"{medal(i+1)} {l['username']} — {l['xp']} XP" for i, l in enumerate(top_t))

    b = InlineKeyboardBuilder()
    b.button(text="👥 Пользователи", callback_data="admin_users")
    b.button(text="📊 Продажи",      callback_data="admin_sales")
    b.adjust(1)

    await message.answer(
        f"🔧 <b>Админ-панель v5.0</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"💎 Premium активных: <b>{premium_cnt}</b>\n"
        f"🎮 Всего игр: <b>{total_games}</b>\n"
        f"💰 Покупок: <b>{purchases}</b>  ⭐{total_stars} Stars\n"
        f"👥 Рефералов: <b>{refs}</b>\n\n"
        f"🏟 Топ турнира:\n{t_str if t_str else '—'}",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )

@router.message(Command("giveprem"))
async def give_premium(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        await message.answer("⛔")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /giveprem USER_ID дней")
        return
    try:
        target_id = int(parts[1])
        days      = int(parts[2])
    except ValueError:
        await message.answer("Неверный формат.")
        return
    stats = load_stats()
    uid   = str(target_id)
    if uid not in stats:
        await message.answer(f"Пользователь {target_id} не найден.")
        return
    u           = stats[uid]
    until       = datetime.now() + timedelta(days=days)
    u["is_premium"]    = True
    u["premium_until"] = until.isoformat()
    u["hints_left"]    = 9999
    check_achievements(u)
    save_stats(stats)
    await message.answer(f"✅ Premium выдан {u['username']} ({target_id}) до {until.strftime('%d.%m.%Y')}")
    try:
        await bot.send_message(target_id, f"🎁 <b>Тебе выдан Premium на {days} дней!</b>\n👑 До {until.strftime('%d.%m.%Y')}", parse_mode="HTML")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
# УМНЫЕ НАПОМИНАНИЯ (фоновая задача)
# ─────────────────────────────────────────────────────────────

async def send_reminders(bot: Bot):
    """Раз в час проверяет кто давно не заходил и отправляет напоминание."""
    while True:
        await asyncio.sleep(3600)  # каждый час
        try:
            stats = load_stats()
            today = str(date.today())
            yesterday = str(date.today() - timedelta(days=1))

            for uid_str, u in stats.items():
                if not u.get("notifications", True):
                    continue
                last_play = u.get("last_play", "")
                last_reminder = u.get("last_reminder", "")
                streak = u.get("streak", 0)
                lang   = u.get("lang", "ru")

                # Не напоминали сегодня
                if last_reminder == today:
                    continue

                # Играл вчера но не сегодня — серия под угрозой
                if last_play == yesterday and streak >= 2:
                    try:
                        msg = (
                            f"🔥 Твоя серия <b>{streak} дней</b> под угрозой!\n\n"
                            f"Зайди и ответь хотя бы на вопрос дня — не потеряй прогресс!"
                        ) if lang == "ru" else (
                            f"🔥 Your <b>{streak}-day streak</b> is at risk!\n\n"
                            f"Answer at least the daily question to keep it!"
                        )
                        b = InlineKeyboardBuilder()
                        b.button(text="📅 Вопрос дня" if lang=="ru" else "📅 Daily", callback_data="daily")
                        await bot.send_message(int(uid_str), msg, reply_markup=b.as_markup(), parse_mode="HTML")
                        u["last_reminder"] = today
                        logger.info(f"Напоминание отправлено: {uid_str}")
                    except Exception:
                        pass

                # Не заходил 3+ дней
                elif last_play and last_play < yesterday:
                    try:
                        days_ago = (date.today() - date.fromisoformat(last_play)).days
                        if days_ago >= 3 and last_reminder != today:
                            msg = (
                                f"👋 Привет! Ты не заходил уже <b>{days_ago} дней</b>.\n\n"
                                f"Новые вопросы ждут тебя! 🐍"
                            ) if lang == "ru" else (
                                f"👋 Hi! You haven't played for <b>{days_ago} days</b>.\n\n"
                                f"New questions are waiting! 🐍"
                            )
                            b = InlineKeyboardBuilder()
                            b.button(text="🎯 Начать" if lang=="ru" else "🎯 Start", callback_data="choose_cat")
                            await bot.send_message(int(uid_str), msg, reply_markup=b.as_markup(), parse_mode="HTML")
                            u["last_reminder"] = today
                    except Exception:
                        pass

            save_stats(stats)
        except Exception as e:
            logger.error(f"Ошибка напоминаний: {e}")

# ─────────────────────────────────────────────────────────────
# ЕЖЕНЕДЕЛЬНЫЙ СБРОС ТУРНИРА
# ─────────────────────────────────────────────────────────────

async def weekly_tournament_reset(bot: Bot):
    """Каждое воскресенье в 23:00 подводит итоги турнира."""
    while True:
        now = datetime.now()
        # Следующее воскресенье 23:00
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 23:
            days_until_sunday = 7
        next_reset = now.replace(hour=23, minute=0, second=0) + timedelta(days=days_until_sunday)
        wait_secs  = (next_reset - now).total_seconds()
        await asyncio.sleep(wait_secs)

        try:
            t_data = load_tournament()
            if t_data.get("scores"):
                winner_id  = max(t_data["scores"], key=lambda x: t_data["scores"][x]["xp"])
                winner     = t_data["scores"][winner_id]
                winner_xp  = winner["xp"]

                # Даём победителю бесплатный Premium на 7 дней
                stats = load_stats()
                if winner_id in stats:
                    u     = stats[winner_id]
                    until = datetime.now() + timedelta(days=7)
                    u["is_premium"]     = True
                    u["premium_until"]  = until.isoformat()
                    u["hints_left"]     = 9999
                    u["tournament_wins"] = u.get("tournament_wins", 0) + 1
                    check_achievements(u)
                    save_stats(stats)

                    try:
                        await bot.send_message(
                            int(winner_id),
                            f"🏆 <b>Ты победил в недельном турнире!</b>\n\n"
                            f"✨ Набрано XP: <b>{winner_xp}</b>\n"
                            f"🎁 Награда: <b>Premium на 7 дней!</b>",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

                t_data["last_winner"] = winner["username"]
                t_data["week_start"]  = get_tournament_week()
                t_data["scores"]      = {}
                save_tournament(t_data)
                logger.info(f"Турнир сброшен. Победитель: {winner['username']}")
        except Exception as e:
            logger.error(f"Ошибка турнира: {e}")

# ─────────────────────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────────────────────

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Python Quiz Bot v5.0 запущен!")

    # Запускаем фоновые задачи
    asyncio.create_task(send_reminders(bot))
    asyncio.create_task(weekly_tournament_reset(bot))

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
